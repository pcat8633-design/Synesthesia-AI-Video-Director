import os
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

def generate_video_for_shot(shot_id, resolution, vocal_mode, pm, style=None):
    row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id).upper()].tolist()
    if not row_idx:
        yield None, "Error: Shot not found in timeline."
        return

    row = pm.df.loc[row_idx[0]]
    vid_prompt = str(row.get('Video_Prompt', ''))

    if row.get('Type') == "Vocal" and vocal_mode == "Use Singer/Band Description":
        settings = pm.load_project_settings()
        perf_desc = settings.get("performance_desc", "")
        if perf_desc:
            vid_prompt = perf_desc

    if pd.isna(vid_prompt) or not vid_prompt.strip():
        yield None, "Error: Missing Video Prompt."
        return

    negative_prompt = config.DEFAULT_NEGATIVE_PROMPT
    style_data = next((s for s in config.STYLES if s["name"] == style), None) if style and style != "None" else None
    if style_data:
        vid_prompt = style_data["prompt"].replace("{prompt}", vid_prompt)
        negative_prompt = config.DEFAULT_NEGATIVE_PROMPT + ", " + style_data["negative_prompt"]

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
        pm.save_data()
        yield local_path, "Done"
    else:
        pm.df.at[row_idx[0], 'Status'] = 'Error'
        pm.save_data()
        yield None, "Error: Completed but no valid video path returned."

def advanced_batch_video_generation(mode, target_versions, resolution, vocal_mode, style, pm):
    if pm.is_generating:
        yield [], None, "❌ Error: A generation process is already actively running.", []
        return

    pm.stop_video_generation = False
    pm.is_generating = True

    try:
        if pm.current_project: pm.load_project(pm.current_project)

        df = pm.df
        if df.empty:
            yield [], None, "No shots found.", []
            return

        current_gallery = get_project_videos(pm)
        yield current_gallery, None, f"🚀 Starting video generation ({mode})...", [item[0] for item in current_gallery]

        if mode == "Generate all Action Shots":
            shot_ids = df[df['Type'] == 'Action']['Shot_ID'].tolist()
        elif mode == "Generate all Vocal Shots":
            shot_ids = df[df['Type'] == 'Vocal']['Shot_ID'].tolist()
        elif mode == "Generate Remaining Shots":
            shot_ids = [
                sid for sid in df['Shot_ID'].tolist()
                if get_video_count_for_shot(sid, current_gallery) < target_versions
            ]
        else:
            shot_ids = df['Shot_ID'].tolist()

        for shot_id in shot_ids:
            if pm.stop_video_generation: break

            matching = df[df['Shot_ID'] == shot_id]
            if matching.empty:
                yield current_gallery, None, f"⚠️ Skipped {shot_id}: Not found in DataFrame.", [item[0] for item in current_gallery]
                continue
            row = matching.iloc[0]

            if mode == "Regenerate all Shots":
                vid_dir = pm.get_path("videos")
                if os.path.exists(vid_dir):
                    for f in glob.glob(os.path.join(vid_dir, f"{shot_id}_*.mp4")):
                        try: os.remove(f)
                        except Exception: pass
                current_gallery = get_project_videos(pm)

            if pd.isna(row.get('Video_Prompt')) or not str(row.get('Video_Prompt')).strip():
                yield current_gallery, None, f"⚠️ Skipped {shot_id}: Missing Video Prompt.", [item[0] for item in current_gallery]
                continue

            current_count = get_video_count_for_shot(shot_id, current_gallery)

            while current_count < target_versions:
                if pm.stop_video_generation: break

                new_vid_path = None
                vid_generator = generate_video_for_shot(shot_id, resolution, vocal_mode, pm, style)

                for path, msg in vid_generator:
                    if pm.stop_video_generation: break
                    if path is None:
                        yield current_gallery, None, f"⏳ {shot_id} (Ver {current_count + 1}/{target_versions}): {msg}", [item[0] for item in current_gallery]
                    else:
                        new_vid_path = path

                if pm.stop_video_generation: break

                if new_vid_path:
                    current_gallery = get_project_videos(pm)
                    current_count += 1
                    yield current_gallery, new_vid_path, f"✅ Finished {shot_id}", [item[0] for item in current_gallery]
                else:
                    yield current_gallery, None, f"❌ Failed to generate video for {shot_id}.", [item[0] for item in current_gallery]
                    break

        if pm.stop_video_generation:
            yield current_gallery, None, "🛑 Generation Stopped by User.", [item[0] for item in current_gallery]
        else:
            yield current_gallery, None, "🎉 Batch Video Generation Complete.", [item[0] for item in current_gallery]
    finally:
        sync_video_directory(pm)
        pm.is_generating = False
