import os
import re
import glob
import time
import shutil
import subprocess
import threading

import requests
import pandas as pd
from pydub import AudioSegment

import config
from models import sync_video_directory

# Global cache for ffprobe frame counts to speed up preview loading in Tab 3
FRAME_COUNT_CACHE = {}

_zimage_url_cache = None  # Cached after first successful discovery


def resolve_style_data(style_name, pm):
    """Resolve style data from name, respecting per-project overrides and Custom style."""
    if not style_name or style_name == "None":
        return None
    settings = pm.load_project_settings()
    if style_name == "Custom":
        p = settings.get("custom_style_prompt", "")
        n = settings.get("custom_style_negative", "")
        return {"name": "Custom", "prompt": p, "negative_prompt": n} if p else None
    overrides = settings.get("style_overrides", {})
    if style_name in overrides:
        base = next((s for s in config.STYLES if s["name"] == style_name), {})
        return {
            "name": style_name,
            "prompt": overrides[style_name].get("prompt", base.get("prompt", "{prompt}")),
            "negative_prompt": overrides[style_name].get("negative_prompt", base.get("negative_prompt", "")),
        }
    return next((s for s in config.STYLES if s["name"] == style_name), None)


def apply_character_bibles(prompt, character_bibles):
    """Replace the first occurrence of each character's name with 'name (description)'.
    Subsequent occurrences within the same prompt are left as the plain name,
    preventing the description from appearing more than once per prompt."""
    for name, description in character_bibles.items():
        pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE | re.UNICODE)
        replacement = f"{name} ({description})"
        prompt = pattern.sub(replacement, prompt, count=1)
    return prompt

# ==========================================
# LOGIC: VIDEO GENERATION (LTX)
# ==========================================

def get_project_renders(pm):
    """Get list of rendered final videos with thumbnails for gallery display."""
    if not pm.current_project:
        return [], []

    renders_dir = pm.get_path("renders")
    if not os.path.exists(renders_dir):
        return [], []

    files = sorted(glob.glob(os.path.join(renders_dir, "*.mp4")), key=os.path.getmtime, reverse=True)
    if not files:
        return [], []

    gallery_data = []
    render_paths = []
    for f in files:
        fname = os.path.basename(f)
        render_paths.append(f)
        try:
            thumb_path = os.path.join(renders_dir, f"thumb_{fname}.jpg")
            if not os.path.exists(thumb_path):
                subprocess.run(
                    ["ffmpeg", "-y", "-i", f, "-ss", "1", "-vframes", "1", "-q:v", "5", thumb_path],
                    capture_output=True, timeout=10
                )
            if os.path.exists(thumb_path):
                gallery_data.append((thumb_path, fname))
            else:
                gallery_data.append((None, fname))
        except Exception:
            gallery_data.append((None, fname))

    return gallery_data, render_paths

def get_project_videos(pm, project_name=None):
    proj = project_name if project_name else pm.current_project
    if not proj: return []

    vid_dir = os.path.join(pm.base_dir, proj, "videos")
    if not os.path.exists(vid_dir): return []

    files = glob.glob(os.path.join(vid_dir, "*.mp4"))

    def sort_key(filepath):
        fname = os.path.basename(filepath)
        parts = fname.split("_")
        shot_id = parts[0].upper() if len(parts) > 0 else fname
        return (shot_id, filepath)

    files = sorted(files, key=sort_key)
    gallery_data = []

    for f in files:
        fname = os.path.basename(f)
        parts = fname.split("_")
        caption = f"{parts[0]}" if len(parts) >= 2 else fname

        if f in FRAME_COUNT_CACHE:
            caption = FRAME_COUNT_CACHE[f]
        else:
            try:
                cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-count_frames", "-show_entries", "stream=nb_read_frames",
                    "-of", "default=nokey=1:noprint_wrappers=1", f
                ]
                output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
                if output and output.isdigit():
                    caption = f"{caption} ({output} frames)"
                    FRAME_COUNT_CACHE[f] = caption
                else:
                    caption = f"{caption} (Error reading frames)"
                    FRAME_COUNT_CACHE[f] = caption
            except Exception:
                caption = f"{caption} (Error)"
                FRAME_COUNT_CACHE[f] = caption

        gallery_data.append((f, caption))

    return gallery_data

def delete_video_file(path, project_name, pm):
    if not path or not os.path.exists(path):
        return get_project_videos(pm, project_name), None
    try:
        os.remove(path)
        if path in FRAME_COUNT_CACHE:
            del FRAME_COUNT_CACHE[path]
        sync_video_directory(pm)
    except Exception as e:
        print(f"Error deleting file: {e}")
    return get_project_videos(pm, project_name), None

def get_video_count_for_shot(shot_id, vid_list):
    count = 0
    for path, caption in vid_list:
        if os.path.basename(path).upper().startswith(f"{str(shot_id).upper()}_"):
            count += 1
    return count

def _discover_zimage_url():
    """Discover the Z-Image endpoint URL via the LTX Desktop OpenAPI schema.
    Queries /openapi.json at the host root, finds the route whose requestBody
    references GenerateImageRequest, and returns the full URL.
    Caches the result after first success. Returns None on failure."""
    global _zimage_url_cache
    if _zimage_url_cache:
        return _zimage_url_cache

    # Extract host root: strip trailing /api or /api/ from LTX_BASE_URL
    base = config.LTX_BASE_URL.rstrip('/')
    host = base[:-4] if base.endswith('/api') else base  # e.g. http://127.0.0.1:8000

    try:
        resp = requests.get(f"{host}/openapi.json", timeout=5)
        resp.raise_for_status()
        schema = resp.json()
        for path, methods in schema.get("paths", {}).items():
            if "post" in methods:
                req_ref = str(methods["post"].get("requestBody", {}))
                if "GenerateImageRequest" in req_ref:
                    _zimage_url_cache = f"{host}{path}"
                    print(f"🔍 Z-Image endpoint discovered: {_zimage_url_cache}")
                    return _zimage_url_cache
    except Exception as e:
        print(f"⚠️ Z-Image endpoint discovery failed: {e}")

    return None


def generate_zimage_first_frame(prompt, shot_id, pm):
    """Call Z-image endpoint, save result to first_frames/, yield string progress updates,
    and yield a final (path, error) tuple as the last item."""
    payload = {
        "prompt": prompt,
        "width": config.Z_IMAGE_WIDTH,
        "height": config.Z_IMAGE_HEIGHT,
        "numSteps": 4,
        "numImages": 1,
    }
    result_container = {}

    def worker():
        url = _discover_zimage_url()
        if not url:
            result_container['error'] = "Could not discover Z-Image endpoint from LTX Desktop OpenAPI schema."
            return
        try:
            resp = requests.post(url, json=payload)
            resp.raise_for_status()
            result_container['response'] = resp.json()
        except requests.exceptions.RequestException as e:
            err_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                err_msg += f" - {e.response.text}"
            result_container['error'] = err_msg

    t = threading.Thread(target=worker)
    t.start()

    while t.is_alive():
        time.sleep(1)
        try:
            prog_resp = requests.get(f"{config.LTX_BASE_URL}/generation/progress", timeout=2)
            if prog_resp.status_code == 200:
                data = prog_resp.json()
                yield f"Z-Image: {data.get('status')} | {data.get('phase')} | {data.get('progress')}%"
        except requests.exceptions.RequestException:
            pass

    t.join()

    if 'error' in result_container:
        yield (None, result_container['error'])
        return

    image_paths = result_container['response'].get('image_paths') or []
    if not image_paths or not os.path.exists(image_paths[0]):
        yield (None, "No image path returned.")
        return

    frames_dir = pm.get_path("first_frames")
    os.makedirs(frames_dir, exist_ok=True)
    save_name = f"{shot_id}_frame_v{int(time.time())}.png"
    local_path = os.path.join(frames_dir, save_name)
    shutil.copy(image_paths[0], local_path)
    print(f"🖼️ Z-Image first frame saved: {local_path}")
    yield (local_path, None)


def generate_video_for_shot(shot_id, resolution, vocal_mode, pm, style=None, director=None, generation_mode="LTX-Native"):
    row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id).upper()].tolist()
    if not row_idx:
        yield None, "Error: Shot not found in timeline."
        return

    row = pm.df.loc[row_idx[0]]
    vid_prompt_raw = row.get('Video_Prompt', '')
    vid_prompt = "" if pd.isna(vid_prompt_raw) else str(vid_prompt_raw).strip()

    if row.get('Type') == "Vocal" and vocal_mode == "Use Singer/Band Description":
        settings = pm.load_project_settings()
        perf_desc = settings.get("performance_desc", "")
        if perf_desc:
            vid_prompt = perf_desc

    if not vid_prompt:
        yield None, "Error: Missing Video Prompt."
        return

    # Inject character bible descriptions (first occurrence of each name only)
    if pm.character_bibles:
        vid_prompt = apply_character_bibles(vid_prompt, pm.character_bibles)

    negative_prompt = config.DEFAULT_NEGATIVE_PROMPT
    style_data = resolve_style_data(style, pm)
    if style_data:
        vid_prompt = style_data["prompt"].replace("{prompt}", vid_prompt)
        negative_prompt = config.DEFAULT_NEGATIVE_PROMPT + ", " + style_data["negative_prompt"]

    if director and director != "None":
        effective_director = director
        if director == "Custom":
            settings = pm.load_project_settings()
            effective_director = settings.get("custom_director", "")
        if effective_director:
            vid_prompt += f". This video was directed by {effective_director}."

    print(f"\n🎬 === START VIDEO GENERATION (LTX) ===")
    print(f"🎬 Shot ID: {shot_id} | Type: {row['Type']}")
    if style_data:
        print(f"🎨 Style: {style}")
    print(f"🎬 Video Prompt:\n{vid_prompt}\n=================================\n")

    payload = {
        "prompt": vid_prompt,
        "negativePrompt": negative_prompt,
        "model": "pro",
        "resolution": resolution,
        "aspectRatio": "16:9",
        "duration": str(row['Duration']),
        "fps": "24",
        "cameraMotion": "none",
        "audio": "false"
    }

    # --- Z-Image first frame conditioning ---
    if generation_mode == "Z-Image First Frame":
        print(f"🖼️ === GENERATING Z-IMAGE FIRST FRAME ===")
        frame_path, frame_err = None, "Unknown"
        for item in generate_zimage_first_frame(vid_prompt, shot_id, pm):
            if isinstance(item, tuple):
                frame_path, frame_err = item
            else:
                yield None, item
        if frame_err:
            yield None, f"Error: Z-Image failed: {frame_err}"
            return
        payload["imagePath"] = os.path.abspath(frame_path)

    if row['Type'] == "Vocal":
        vocals_path = pm.get_asset_path_if_exists("vocals.mp3")
        if not vocals_path:
            vocals_path = pm.get_asset_path_if_exists("full_song.mp3")
        if not vocals_path:
            yield None, "Error: Missing audio file for vocal shot. Upload a vocals or full song file."
            return

        try:
            audio = AudioSegment.from_file(vocals_path)
            start_ms = round(float(row['Start_Time']) * 1000)
            end_ms = round(float(row['End_Time']) * 1000)

            chunk = audio[start_ms : end_ms]

            expected_len_ms = end_ms - start_ms
            if len(chunk) < expected_len_ms:
                deficit = expected_len_ms - len(chunk)
                silence_pad = AudioSegment.silent(duration=deficit)
                chunk = chunk + silence_pad

            chunk_path = os.path.join(pm.get_path("audio_chunks"), f"{shot_id}_audio.mp3")
            chunk.export(chunk_path, format="mp3")

            payload["audio"] = "true"
            payload["audioPath"] = os.path.abspath(chunk_path)

        except Exception as e:
            print(f"❌ AUDIO ERROR for {shot_id}: {e}")
            yield None, f"Error processing audio: {str(e)}"
            return

    result_container = {}

    def worker():
        try:
            resp = requests.post(f"{config.LTX_BASE_URL}/generate", json=payload)
            resp.raise_for_status()
            result_container['response'] = resp.json()
        except requests.exceptions.RequestException as e:
            err_msg = str(e)
            if e.response is not None:
                err_msg += f" - {e.response.text}"
            result_container['error'] = err_msg

    t = threading.Thread(target=worker)
    t.start()

    while t.is_alive():
        time.sleep(1)
        try:
            prog_resp = requests.get(f"{config.LTX_BASE_URL}/generation/progress", timeout=2)
            if prog_resp.status_code == 200:
                data = prog_resp.json()
                status_text = f"LTX Progress - Status: {data.get('status')} | Phase: {data.get('phase')} | {data.get('progress')}%"
                yield None, status_text
        except requests.exceptions.RequestException:
            pass

    t.join()

    if 'error' in result_container:
        print(f"❌ GENERATION FAILED: {result_container['error']}")
        pm.df.at[row_idx[0], 'Status'] = 'Error'
        pm.save_data()
        yield None, f"Error: {result_container['error']}"
        return

    video_path = result_container['response'].get('video_path')
    if video_path and os.path.exists(video_path):
        slug = config.style_to_slug(style) if style and style != "None" else None
        save_name = (
            f"{shot_id}_vid_{slug}_v{int(time.time())}.mp4" if slug
            else f"{shot_id}_vid_v{int(time.time())}.mp4"
        )
        local_path = os.path.join(pm.get_path("videos"), save_name)
        shutil.copy(video_path, local_path)

        pm.df.at[row_idx[0], 'Video_Path'] = local_path
        pm.df.at[row_idx[0], 'Status'] = 'Done'
        pm.df.at[row_idx[0], 'Render_Resolution'] = resolution
        pm.save_data()
        yield local_path, "Done"
    else:
        pm.df.at[row_idx[0], 'Status'] = 'Error'
        pm.save_data()
        yield None, "Error: Completed but no valid video path returned."

