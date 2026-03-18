import os
import glob

import pandas as pd
from moviepy.editor import VideoFileClip, AudioFileClip, ColorClip, concatenate_videoclips

import config
from utils import format_time

# ==========================================
# LOGIC: VIDEO ASSEMBLY
# ==========================================

def assemble_video(full_song_path, resolution, pm, fallback_mode=False, style_filter=None):
    df = pm.df
    clips = []
    clips_to_close = []
    if df.empty: return "No shots to assemble."

    df = df.sort_values(by="Start_Time")
    expected_cursor = 0.0

    # Resolve the style slug to use for filtering (None = no filter = use Video_Path)
    filter_slug = None
    filter_no_style = False
    if style_filter and style_filter not in (None, "All Styles"):
        if style_filter == "No Style":
            filter_no_style = True
        else:
            filter_slug = config.style_to_slug(style_filter)

    def pick_vid_path(row):
        if filter_slug is not None or filter_no_style:
            all_paths = [p.strip() for p in str(row.get("All_Video_Paths", "")).split(",") if p.strip()]
            if filter_no_style:
                matching = [p for p in all_paths if config.slug_from_filename(os.path.basename(p)) is None]
            else:
                matching = [p for p in all_paths if config.slug_from_filename(os.path.basename(p)) == filter_slug]
            return matching[0] if matching else None
        return row.get('Video_Path')

    # Detect target resolution from the first available video clip
    # LTX output resolution varies (multiples of 32, differs with/without audio)
    target_size = None
    for _, r in df.iterrows():
        vp = pick_vid_path(r)
        if vp and pd.notna(vp) and os.path.exists(str(vp)):
            try:
                probe = VideoFileClip(str(vp))
                target_size = tuple(probe.size)
                probe.close()
                break
            except:
                pass
    if target_size is None:
        target_size = config.RESOLUTION_MAP.get(resolution, (1920, 1080))

    for index, row in df.iterrows():
        vid_path = pick_vid_path(row)
        dur = float(row['Duration'])
        start_time = float(row['Start_Time'])
        snapped_dur = round(dur * 24) / 24
        clip = None

        gap = round((start_time - expected_cursor) * 24) / 24
        if gap > 0.05:
            pad = ColorClip(size=target_size, color=(0,0,0), duration=gap).set_fps(24)
            clips.append(pad)
            clips_to_close.append(pad)

        if vid_path and pd.notna(vid_path) and os.path.exists(str(vid_path)):
            try:
                clip = VideoFileClip(str(vid_path)).without_audio().set_fps(24)

                if clip.duration > snapped_dur:
                    clip = clip.subclip(0, snapped_dur)
                clip = clip.set_duration(snapped_dur)

                if tuple(clip.size) != tuple(target_size):
                    clip = clip.resize(newsize=target_size)

            except Exception as e:
                print(f"Error loading clip {vid_path}: {e}")

        if clip is None:
            if fallback_mode:
                clip = ColorClip(size=target_size, color=(0,0,0), duration=snapped_dur).set_fps(24)
            else:
                for c in clips_to_close: c.close()
                return f"Error: Missing or corrupt video for shot at {start_time}s. Assembly stopped (Strict Mode)."

        if clip is not None:
            clips.append(clip)
            clips_to_close.append(clip)

        expected_cursor = start_time + snapped_dur

    if not clips: return "No valid clips found."

    final = concatenate_videoclips(clips, method="chain")
    audio = None

    audio_path = full_song_path if (full_song_path and os.path.exists(full_song_path)) else pm.get_asset_path_if_exists("full_song.mp3")
    if not audio_path: audio_path = pm.get_asset_path_if_exists("vocals.mp3")

    if audio_path and os.path.exists(audio_path):
        try:
            audio = AudioFileClip(audio_path)
            if audio.duration > final.duration: audio = audio.subclip(0, final.duration)
            final = final.set_audio(audio)
        except Exception as e: print(f"Audio attach failed: {e}")

    total_seconds = pm.get_current_total_time()
    time_str = format_time(total_seconds)

    style_part = ""
    if filter_slug:
        style_part = f"_{filter_slug}"
    elif filter_no_style:
        style_part = "_no_style"
    out_path = os.path.join(pm.get_path("renders"), f"final_cut{style_part}_{time_str}.mp4")

    try:
        final.write_videofile(
            out_path, fps=24, codec='libx264', audio_codec='aac',
            temp_audiofile=os.path.join(pm.get_path("renders"), "temp_audio.m4a"),
            remove_temp=True,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-ar", "44100"]
        )
    finally:
        final.close()
        if audio is not None:
            try: audio.close()
            except: pass
        for c in clips_to_close:
            try: c.close()
            except: pass

    return out_path

def assemble_cutting_room_floor(full_song_path, resolution, pm):
    """Assemble all versions (cutting_room + active videos) into a single chronological showreel."""
    vid_dir = pm.get_path("videos")
    cut_dir = pm.get_path("cutting_room")

    all_files = []
    for d in [vid_dir, cut_dir]:
        if os.path.exists(d):
            all_files.extend(glob.glob(os.path.join(d, "*.mp4")))

    if not all_files:
        return "No videos found in videos or cutting_room directories."

    def sort_key(filepath):
        shot_id = os.path.basename(filepath).split("_")[0].upper()
        return (shot_id, os.path.getmtime(filepath))

    all_files.sort(key=sort_key)

    target_size = None
    for f in all_files:
        try:
            probe = VideoFileClip(f)
            target_size = tuple(probe.size)
            probe.close()
            break
        except:
            pass
    if target_size is None:
        target_size = config.RESOLUTION_MAP.get(resolution, (1920, 1080))

    clips = []
    clips_to_close = []
    for f in all_files:
        try:
            clip = VideoFileClip(f).without_audio().set_fps(24)
            if tuple(clip.size) != target_size:
                clip = clip.resize(newsize=target_size)
            clips.append(clip)
            clips_to_close.append(clip)
        except Exception as e:
            print(f"Skipping {f}: {e}")

    if not clips:
        return "No valid clips could be loaded."

    final = concatenate_videoclips(clips, method="chain")

    audio_path = full_song_path if (full_song_path and os.path.exists(full_song_path)) else pm.get_asset_path_if_exists("full_song.mp3")
    if not audio_path:
        audio_path = pm.get_asset_path_if_exists("vocals.mp3")

    audio = None
    if audio_path and os.path.exists(audio_path):
        try:
            audio = AudioFileClip(audio_path)
            if audio.duration > final.duration:
                audio = audio.subclip(0, final.duration)
            final = final.set_audio(audio)
        except Exception as e:
            print(f"Audio attach failed: {e}")

    total_seconds = pm.get_current_total_time()
    time_str = format_time(total_seconds)
    out_path = os.path.join(pm.get_path("renders"), f"cutting_room_floor_{time_str}.mp4")

    try:
        final.write_videofile(
            out_path, fps=24, codec='libx264', audio_codec='aac',
            temp_audiofile=os.path.join(pm.get_path("renders"), "temp_audio_crf.m4a"),
            remove_temp=True,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-ar", "44100"]
        )
    finally:
        final.close()
        if audio is not None:
            try: audio.close()
            except: pass
        for c in clips_to_close:
            try: c.close()
            except: pass

    return out_path
