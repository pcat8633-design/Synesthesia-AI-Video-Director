import os
import glob
import re
import time

import gradio as gr
import pandas as pd

import config
from models import LLMBridge, sync_video_directory
from utils import format_eta
from video import (get_project_videos, delete_video_file, generate_video_for_shot,
                   get_video_count_for_shot, apply_character_bibles, resolve_style_data)


def build(pm_state, current_proj_var, shared_shot_state):
    """Build Tab 3: Video Generation. Returns dict of exported components."""

    with gr.Tab("3. Video Generation") as tab3_ui:
        selected_vid_path = gr.State("")
        gallery_paths_state = gr.State([])

        with gr.Row():
            vid_gen_mode_dropdown = gr.Dropdown(choices=["Generate Remaining Shots", "Regenerate all Shots", "Generate all Action Shots", "Generate all Vocal Shots", "Generate Remaining Action Shots", "Generate Remaining Vocal Shots"], value="Generate Remaining Shots", label="Generation Mode")
            vid_versions_dropdown = gr.Dropdown(choices=[1, 2, 3, 4, 5], value=1, label="Versions per Shot")
            vid_resolution_dropdown = gr.Dropdown(choices=["540p", "720p", "1080p"], value="1080p", label="Resolution")
            vid_firstframe_mode = gr.Radio(
                choices=["LTX-Native", "Z-Image First Frame"],
                value="LTX-Native",
                label="First Frame Mode"
            )
            vid_vocal_prompt_mode = gr.Dropdown(choices=["Use Singer/Band Description", "Use Storyboard Prompt"], value="Use Singer/Band Description", label="Vocal Shot Prompt Mode")
            vid_style_dropdown = gr.Dropdown(choices=config.STYLE_NAMES, value="None", label="Style")

        with gr.Accordion("✏️ Style Editor", open=False):
            gr.Markdown("Edit the style prompt for the selected style. Changes are saved per-project and never overwrite `styles.json`.")
            style_prompt_edit = gr.Textbox(
                label="Style Prompt Template (use `{prompt}` for your video prompt)",
                lines=3, interactive=False,
                placeholder='e.g. "A neon cyberpunk scene of {prompt}, vivid colors, glowing signs."'
            )
            style_negative_edit = gr.Textbox(
                label="Additional Negative Prompts",
                lines=2, interactive=False,
                placeholder="e.g. muted colors, realism"
            )

        with gr.Row():
            vid_director_dropdown = gr.Dropdown(choices=config.DIRECTORS, value="None", label="Directed by")
            vid_custom_director_txt = gr.Textbox(
                label="Custom Director Name", placeholder="Enter director name...",
                visible=False, interactive=True, scale=2
            )

        with gr.Row():
            vid_gen_start_btn = gr.Button("🎬 Start Batch Generation", variant="primary", scale=3)
            vid_gen_stop_btn = gr.Button("⏹ Stop", variant="stop", visible=False, scale=1)

        vid_gen_status = gr.Textbox(label="Queue Status", interactive=False, lines=5)

        with gr.Row():
            current_render_progress = gr.Slider(label="Current Render", minimum=0, maximum=100, value=0, interactive=False, step=1)
            queue_progress_bar = gr.Slider(label="Queue Progress", minimum=0, maximum=100, value=0, interactive=False, step=1)
        with gr.Row():
            current_render_eta = gr.Textbox(label="Render ETA", interactive=False, scale=1)
            queue_eta_txt = gr.Textbox(label="Queue Complete", interactive=False, scale=1)
            current_render_cost = gr.Textbox(label="Render Cost Est.", interactive=False, scale=1)
            queue_cost_txt = gr.Textbox(label="Queue Cost Est.", interactive=False, scale=1)

        gr.Markdown("### 🎯 Single Shot Generation")
        with gr.Row():
            single_shot_dropdown = gr.Dropdown(label="Select Shot to Generate", choices=[], interactive=True)
            single_shot_btn = gr.Button("Generate Additional Version", variant="primary")
        with gr.Row():
            single_shot_camera_dropdown = gr.Dropdown(
                choices=config.CAMERA_MOTIONS, value="none",
                label="Camera Motion (this shot only)"
            )
        with gr.Row():
            queue_pause_btn = gr.Button("⏸ Pause Queue")
            queue_cancel_btn = gr.Button("✖ Cancel All", variant="stop")
        single_shot_prompt_edit = gr.Textbox(label="Edit Video Prompt for Selected Shot", lines=3, interactive=True)
        with gr.Accordion("Full prompt text", open=False):
            full_prompt_preview = gr.Textbox(label="Full prompt text", interactive=False, lines=5,
                                             placeholder="Select a shot to preview the full assembled prompt.")
        with gr.Row():
            prev_shot_btn_t3 = gr.Button("◀ Prev Shot")
            next_shot_btn_t3 = gr.Button("Next Shot ▶")

        with gr.Row():
            with gr.Column(scale=1):
                vid_gallery = gr.Gallery(label="Generated Video Thumbnails", columns=4, height=600, allow_preview=False, interactive=True)

            with gr.Column(scale=1):
                vid_large_view = gr.Video(label="Selected Video", interactive=False)
                with gr.Row():
                    sel_shot_info_vid = gr.Textbox(label="Selected Shot ID", interactive=False)

                with gr.Row():
                    del_vid_btn = gr.Button("🗑️ Delete This Video", variant="stop")
                with gr.Row():
                    regen_vid_same_prompt_btn = gr.Button("♻️ Regenerate Video (Same Prompt)")
                    regen_vid_new_prompt_btn = gr.Button("✨ Regenerate Video AND Prompt", variant="primary")

    # --- Tab 3 Internal Events ---

    def load_single_shot_prompt(shot_id, pm):
        if not shot_id or pm.df.empty: return ""
        row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id).upper()].tolist()
        if row_idx:
            val = pm.df.loc[row_idx[0], 'Video_Prompt']
            return "" if pd.isna(val) else str(val)
        return ""

    single_shot_dropdown.change(load_single_shot_prompt, inputs=[single_shot_dropdown, pm_state], outputs=[single_shot_prompt_edit])
    single_shot_dropdown.change(lambda s: s, inputs=[single_shot_dropdown], outputs=[shared_shot_state])

    def _nav_shot_t3(new_shot, gallery_paths):
        shot_vid = next(
            (p for p in gallery_paths if os.path.basename(p).split('_')[0] == new_shot),
            None
        )
        return gr.update(value=new_shot), shot_vid, new_shot if shot_vid else "", shot_vid or ""

    def get_prev_shot_t3(current_shot, pm, gallery_paths):
        if pm.df.empty: return gr.update(), None, "", ""
        choices = pm.df['Shot_ID'].dropna().unique().tolist()
        if not choices: return gr.update(), None, "", ""
        if current_shot not in choices:
            new_shot = choices[-1]
        else:
            new_shot = choices[(choices.index(current_shot) - 1) % len(choices)]
        return _nav_shot_t3(new_shot, gallery_paths)

    def get_next_shot_t3(current_shot, pm, gallery_paths):
        if pm.df.empty: return gr.update(), None, "", ""
        choices = pm.df['Shot_ID'].dropna().unique().tolist()
        if not choices: return gr.update(), None, "", ""
        if current_shot not in choices:
            new_shot = choices[0]
        else:
            new_shot = choices[(choices.index(current_shot) + 1) % len(choices)]
        return _nav_shot_t3(new_shot, gallery_paths)

    prev_shot_btn_t3.click(
        get_prev_shot_t3,
        inputs=[single_shot_dropdown, pm_state, gallery_paths_state],
        outputs=[single_shot_dropdown, vid_large_view, sel_shot_info_vid, selected_vid_path]
    )
    next_shot_btn_t3.click(
        get_next_shot_t3,
        inputs=[single_shot_dropdown, pm_state, gallery_paths_state],
        outputs=[single_shot_dropdown, vid_large_view, sel_shot_info_vid, selected_vid_path]
    )

    def save_single_shot_prompt(shot_id, new_prompt, pm):
        if not shot_id or pm.df.empty: return
        row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id).upper()].tolist()
        if row_idx:
            pm.df.at[row_idx[0], 'Video_Prompt'] = new_prompt
            pm.save_data()

    single_shot_prompt_edit.change(save_single_shot_prompt, inputs=[single_shot_dropdown, single_shot_prompt_edit, pm_state])

    def build_full_prompt_preview(shot_id, style, director, vocal_mode, pm):
        if not shot_id or pm.df.empty:
            return ""
        row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id).upper()].tolist()
        if not row_idx:
            return ""
        row = pm.df.loc[row_idx[0]]
        vid_prompt_raw = row.get('Video_Prompt', '')
        vid_prompt = "" if pd.isna(vid_prompt_raw) else str(vid_prompt_raw).strip()

        if row.get('Type') == "Vocal" and vocal_mode == "Use Singer/Band Description":
            settings = pm.load_project_settings()
            perf_desc = settings.get("performance_desc", "")
            if perf_desc:
                vid_prompt = perf_desc

        if not vid_prompt:
            return ""

        if pm.character_bibles:
            vid_prompt = apply_character_bibles(vid_prompt, pm.character_bibles)

        style_data = resolve_style_data(style, pm)
        if style_data:
            vid_prompt = style_data["prompt"].replace("{prompt}", vid_prompt)

        if director and director != "None":
            effective_director = director
            if director == "Custom":
                settings = pm.load_project_settings()
                effective_director = settings.get("custom_director", "")
            if effective_director:
                vid_prompt += f". This video was directed by {effective_director}."

        return vid_prompt

    _full_prompt_inputs = [single_shot_dropdown, vid_style_dropdown, vid_director_dropdown, vid_vocal_prompt_mode, pm_state]
    single_shot_dropdown.change(build_full_prompt_preview, inputs=_full_prompt_inputs, outputs=[full_prompt_preview])
    single_shot_prompt_edit.change(build_full_prompt_preview, inputs=_full_prompt_inputs, outputs=[full_prompt_preview])
    vid_style_dropdown.change(build_full_prompt_preview, inputs=_full_prompt_inputs, outputs=[full_prompt_preview])
    vid_director_dropdown.change(build_full_prompt_preview, inputs=_full_prompt_inputs, outputs=[full_prompt_preview])
    vid_custom_director_txt.change(build_full_prompt_preview, inputs=_full_prompt_inputs, outputs=[full_prompt_preview])
    vid_vocal_prompt_mode.change(build_full_prompt_preview, inputs=_full_prompt_inputs, outputs=[full_prompt_preview])

    # --- Style Editor handlers ---

    def on_style_change(style_name, pm):
        if not style_name or style_name == "None":
            return gr.update(value="", interactive=False), gr.update(value="", interactive=False)
        settings = pm.load_project_settings() if pm.current_project else {}
        if style_name == "Custom":
            p = settings.get("custom_style_prompt", "")
            n = settings.get("custom_style_negative", "")
            return gr.update(value=p, interactive=True), gr.update(value=n, interactive=True)
        overrides = settings.get("style_overrides", {})
        if style_name in overrides:
            p = overrides[style_name].get("prompt", "")
            n = overrides[style_name].get("negative_prompt", "")
        else:
            style = next((s for s in config.STYLES if s["name"] == style_name), None)
            p = style["prompt"] if style else ""
            n = style["negative_prompt"] if style else ""
        return gr.update(value=p, interactive=True), gr.update(value=n, interactive=True)

    def save_style_prompt(style_name, prompt_val, pm):
        if not style_name or style_name == "None" or not pm.current_project:
            return
        if style_name == "Custom":
            pm.save_project_settings({"custom_style_prompt": prompt_val})
        else:
            settings = pm.load_project_settings()
            overrides = settings.get("style_overrides", {})
            if style_name not in overrides:
                overrides[style_name] = {}
            overrides[style_name]["prompt"] = prompt_val
            pm.save_project_settings({"style_overrides": overrides})

    def save_style_negative(style_name, negative_val, pm):
        if not style_name or style_name == "None" or not pm.current_project:
            return
        if style_name == "Custom":
            pm.save_project_settings({"custom_style_negative": negative_val})
        else:
            settings = pm.load_project_settings()
            overrides = settings.get("style_overrides", {})
            if style_name not in overrides:
                overrides[style_name] = {}
            overrides[style_name]["negative_prompt"] = negative_val
            pm.save_project_settings({"style_overrides": overrides})

    vid_style_dropdown.change(on_style_change, inputs=[vid_style_dropdown, pm_state], outputs=[style_prompt_edit, style_negative_edit])
    style_prompt_edit.change(save_style_prompt, inputs=[vid_style_dropdown, style_prompt_edit, pm_state])
    style_negative_edit.change(save_style_negative, inputs=[vid_style_dropdown, style_negative_edit, pm_state])

    # --- Director handlers ---

    def on_director_change(director_name, pm):
        if director_name == "Custom":
            saved = pm.load_project_settings().get("custom_director", "") if pm.current_project else ""
            return gr.update(visible=True, value=saved)
        return gr.update(visible=False, value="")

    def save_custom_director(name, pm):
        if pm.current_project:
            pm.save_project_settings({"custom_director": name})

    vid_director_dropdown.change(on_director_change, inputs=[vid_director_dropdown, pm_state], outputs=[vid_custom_director_txt])
    vid_custom_director_txt.change(save_custom_director, inputs=[vid_custom_director_txt, pm_state])

    # --- Gallery select ---

    def on_vid_gallery_select(evt: gr.SelectData, gallery_paths):
        if gallery_paths and evt.index < len(gallery_paths):
            fpath = gallery_paths[evt.index]
            fname = os.path.basename(fpath)
            shot_id = fname.split('_')[0] if '_' in fname else "Unknown"
            return fpath, shot_id, fpath, gr.update(value=shot_id)
        return None, "", "", gr.update()

    vid_gallery.select(on_vid_gallery_select, inputs=[gallery_paths_state], outputs=[vid_large_view, sel_shot_info_vid, selected_vid_path, single_shot_dropdown])

    def update_single_shot_choices(pm, shared_shot):
        if pm.df.empty: return gr.update(choices=[]), shared_shot
        choices = pm.df['Shot_ID'].dropna().unique().tolist()
        value = shared_shot if shared_shot in choices else None
        return gr.update(choices=choices, value=value), shared_shot

    def format_queue_status(pm, current_item=None, current_msg=""):
        lines = []
        if getattr(pm, 'ltx_ram_warning', ''):
            lines.append(pm.ltx_ram_warning)
        if current_item:
            shot_label = f"{current_item['shot_id']} — {current_item['resolution']} — {current_item['style']}"
            director = current_item.get('director', 'None')
            if director and director != 'None':
                shot_label += f" — dir: {director}"
            lines.append(f"🎬 NOW RENDERING: {shot_label}")
            if current_msg:
                lines.append(f"  ⏳ {current_msg}")
        if pm.render_queue:
            lines.append(f"📋 QUEUE ({len(pm.render_queue)}):")
            for i, item in enumerate(pm.render_queue, 1):
                lines.append(f"  {i}. {item['shot_id']} — {item['resolution']} — {item['style']}")
        if not lines:
            return "💤 Queue is empty."
        return "\n".join(lines)

    def _effective_resolution(shot_id, resolution, df):
        """Downgrade 1080p to 720p for shots longer than 5 seconds.
        LTX Desktop only supports >5s clips at 720p or lower."""
        if resolution != "1080p":
            return resolution
        try:
            dur = float(df[df['Shot_ID'] == shot_id]['Duration'].values[0])
            if dur > 5.0:
                return "720p"
        except Exception:
            pass
        return resolution

    def add_to_render_queue(shot_id, resolution, vocal_mode, style, director, generation_mode, pm, delete_path=None, camera_motion="none"):
        if not shot_id:
            return "❌ No shot selected."
        effective_res = _effective_resolution(shot_id, resolution, pm.df)
        item = {'shot_id': shot_id, 'resolution': effective_res, 'vocal_mode': vocal_mode,
                'style': style, 'director': director, 'generation_mode': generation_mode,
                'delete_path': delete_path, 'camera_motion': camera_motion}
        with pm.queue_lock:
            pm.render_queue.append(item)
        status = format_queue_status(pm)
        if effective_res != resolution:
            status = f"⚠️ Shot {shot_id} is >5s — resolution downgraded to 720p.\n" + status
        return status

    _queue_est_cache = [0.0, -1]  # [cached_estimate, last_queue_len]

    def _calc_remaining_queue_est(pm):
        """Dynamically sum estimates for all items still in pm.render_queue.
        Caches by queue length to avoid redundant DataFrame scans on every 1s yield."""
        with pm.queue_lock:
            remaining = list(pm.render_queue)
        queue_len = len(remaining)
        if queue_len == _queue_est_cache[1]:
            return _queue_est_cache[0]
        est = 0.0
        for _qi in remaining:
            try:
                _dur = float(pm.df[pm.df['Shot_ID'] == _qi['shot_id']]['Duration'].values[0])
            except Exception:
                _dur = 3.0
            est += config.estimate_render_seconds(_dur, _qi['resolution'], _qi.get('generation_mode', 'LTX-Native'))
        _queue_est_cache[0] = est
        _queue_est_cache[1] = queue_len
        return est

    def process_render_queue_if_idle(pm, proj):
        with pm.queue_lock:
            if pm.queue_processor_running or not pm.render_queue:
                gal = get_project_videos(pm, proj)
                yield gal, format_queue_status(pm), [item[0] for item in gal], 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()
                return
            pm.queue_processor_running = True
            pm.stop_video_generation = False

        queue_elapsed = 0.0
        _first_shot_in_session = True

        try:
            while True:
                if pm.queue_paused:
                    with pm.queue_lock:
                        queue_snapshot = list(pm.render_queue)
                    gal = get_project_videos(pm, proj)
                    paused_lines = ["⏸ [PAUSED]"]
                    if queue_snapshot:
                        paused_lines.append(f"📋 QUEUE ({len(queue_snapshot)}):")
                        for i, it in enumerate(queue_snapshot, 1):
                            paused_lines.append(f"  {i}. {it['shot_id']} — {it['resolution']} — {it['style']}")
                    yield gal, "\n".join(paused_lines), [item[0] for item in gal], 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()
                    time.sleep(0.5)
                    continue

                with pm.queue_lock:
                    if not pm.render_queue or pm.stop_video_generation:
                        break
                    current_item = pm.render_queue.pop(0)

                delete_path = current_item.get('delete_path')
                if delete_path and os.path.exists(delete_path):
                    try:
                        os.remove(delete_path)
                    except Exception as e:
                        print(f"Could not delete {delete_path}: {e}")

                # Duration and time estimate for this shot
                try:
                    shot_dur = float(pm.df[pm.df['Shot_ID'] == current_item['shot_id']]['Duration'].values[0])
                except Exception:
                    shot_dur = 3.0
                shot_est = config.estimate_render_seconds(shot_dur, current_item['resolution'], current_item.get('generation_mode', 'LTX-Native'))
                render_start = time.time()

                for path, msg in generate_video_for_shot(
                    current_item['shot_id'], current_item['resolution'],
                    current_item['vocal_mode'], pm, current_item['style'],
                    director=current_item.get('director'),
                    generation_mode=current_item.get('generation_mode', 'LTX-Native'),
                    camera_motion=current_item.get('camera_motion', 'none')
                ):
                    if path is None:
                        ltx_pct = 0
                        _m = re.search(r'(\d+)%', msg)
                        if _m:
                            ltx_pct = int(_m.group(1))
                        elapsed = time.time() - render_start
                        # Dynamic estimates — accounts for shots added/removed mid-queue
                        remaining_queue_est = _calc_remaining_queue_est(pm)
                        render_remaining = max(0.0, shot_est - elapsed)
                        queue_remaining = render_remaining + remaining_queue_est
                        total_done = queue_elapsed + elapsed
                        total_dynamic_est = total_done + queue_remaining
                        queue_pct = min(100, int(total_done / max(total_dynamic_est, 1) * 100))
                        render_pct = min(99, int(elapsed / max(shot_est, 1) * 100))
                        render_cost = (elapsed / 3600.0) * (config.SYSTEM_WATTAGE / 1000.0) * config.ELECTRICITY_COST
                        queue_cost_proj = (total_dynamic_est / 3600.0) * (config.SYSTEM_WATTAGE / 1000.0) * config.ELECTRICITY_COST
                        gal = get_project_videos(pm, proj)
                        yield (gal, format_queue_status(pm, current_item, msg), [item[0] for item in gal],
                               render_pct, queue_pct,
                               f"~{format_eta(render_remaining)}", f"~{format_eta(queue_remaining)}",
                               f"${render_cost:.4f}", f"${queue_cost_proj:.3f}",
                               gr.update(), gr.update(), gr.update())

                actual_render_secs = time.time() - render_start
                queue_elapsed += actual_render_secs
                config.record_render_time(
                    current_item['resolution'],
                    current_item.get('generation_mode', 'LTX-Native'),
                    shot_dur,
                    actual_render_secs
                )

                # VRAM leakage heuristic: check VRAM fullness + render slowdown
                _vram = config.get_vram_usage()
                _slowdown_ratio = actual_render_secs / max(shot_est, 1)
                _vram_warning = _vram and (_vram[0] / max(_vram[1], 1)) > config.VRAM_WARN_THRESHOLD
                _slowdown_warning = _slowdown_ratio > config.SLOWDOWN_WARN_FACTOR
                if _first_shot_in_session and _slowdown_ratio > 3.0:
                    pm.ltx_ram_warning = (
                        f"⚠️ FIRST SHOT ALERT: Render took {_slowdown_ratio:.1f}x estimated time. "
                        "Possible RAM leakage before queue started — consider restarting LTX Desktop now."
                    )
                elif _vram_warning or _slowdown_warning:
                    _warn_parts = []
                    if _vram_warning:
                        _warn_parts.append(f"GPU VRAM {_vram[0]:.1f}/{_vram[1]:.1f} GB ({100*_vram[0]/_vram[1]:.0f}% full)")
                    if _slowdown_warning:
                        _warn_parts.append(f"render took {_slowdown_ratio:.1f}x estimated time")
                    pm.ltx_ram_warning = "⚠️ Possible LTX RAM leakage: " + "; ".join(_warn_parts) + ". Consider restarting LTX Desktop."
                else:
                    pm.ltx_ram_warning = ""
                _first_shot_in_session = False

                sync_video_directory(pm)
                gal = get_project_videos(pm, proj)
                _shot_vids = sorted(
                    glob.glob(os.path.join(pm.get_path("videos"), f"{current_item['shot_id']}_*.mp4")),
                    key=os.path.getmtime
                )
                _new_vid = _shot_vids[-1] if _shot_vids else None
                yield (gal, format_queue_status(pm), [item[0] for item in gal], 0, 0, "", "", "", "",
                       _new_vid, current_item['shot_id'] if _new_vid else gr.update(), _new_vid or gr.update())
        finally:
            with pm.queue_lock:
                pm.queue_processor_running = False
                pm.stop_video_generation = False
            gal = get_project_videos(pm, proj)
            yield gal, "💤 Queue is empty.", [item[0] for item in gal], 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()

    def batch_enqueue_shots(mode, target_versions, resolution, vocal_mode, style, director, generation_mode, pm):
        if pm.current_project:
            pm.load_project(pm.current_project)
        df = pm.df
        if df.empty:
            return "No shots found.", gr.update(value="Start Batch Generation")

        if mode == "Regenerate all Shots":
            vid_dir = pm.get_path("videos")
            if os.path.exists(vid_dir):
                for f in glob.glob(os.path.join(vid_dir, "*.mp4")):
                    try: os.remove(f)
                    except: pass
            sync_video_directory(pm)
            current_gallery = []
            shot_ids = df['Shot_ID'].tolist()
        else:
            current_gallery = get_project_videos(pm)
            if mode in ("Generate all Action Shots", "Generate Remaining Action Shots"):
                shot_ids = df[df['Type'] == 'Action']['Shot_ID'].tolist()
            elif mode in ("Generate all Vocal Shots", "Generate Remaining Vocal Shots"):
                shot_ids = df[df['Type'] == 'Vocal']['Shot_ID'].tolist()
            else:
                shot_ids = df['Shot_ID'].tolist()

        items_added = 0
        downgraded_count = 0
        for shot_id in shot_ids:
            row = df[df['Shot_ID'] == shot_id]
            if row.empty:
                continue
            if pd.isna(row.iloc[0].get('Video_Prompt')) or not str(row.iloc[0].get('Video_Prompt')).strip():
                continue
            effective_res = _effective_resolution(shot_id, resolution, df)
            if effective_res != resolution:
                downgraded_count += 1
            current_count = get_video_count_for_shot(shot_id, current_gallery)
            needed = max(0, target_versions - current_count)
            for _ in range(needed):
                item = {'shot_id': shot_id, 'resolution': effective_res,
                        'vocal_mode': vocal_mode, 'style': style,
                        'director': director, 'generation_mode': generation_mode,
                        'delete_path': None}
                with pm.queue_lock:
                    pm.render_queue.append(item)
                items_added += 1

        if items_added == 0:
            return "ℹ️ No shots need generation.\n" + format_queue_status(pm), gr.update(value="Start Batch Generation")
        msg = f"✅ Added {items_added} item(s) to queue."
        if downgraded_count:
            msg += f" ⚠️ {downgraded_count} shot(s) downgraded to 720p (duration >5s)."
        return msg + "\n" + format_queue_status(pm), gr.update(value=f"⏳ Queue: {items_added} items")

    single_shot_btn.click(
        lambda shot_id, res, vocal, style, director, gen_mode, cam, pm:
            add_to_render_queue(shot_id, res, vocal, style, director, gen_mode, pm, camera_motion=cam),
        inputs=[single_shot_dropdown, vid_resolution_dropdown, vid_vocal_prompt_mode,
                vid_style_dropdown, vid_director_dropdown, vid_firstframe_mode,
                single_shot_camera_dropdown, pm_state],
        outputs=[vid_gen_status]
    ).then(
        process_render_queue_if_idle,
        inputs=[pm_state, current_proj_var],
        outputs=[vid_gallery, vid_gen_status, gallery_paths_state,
                 current_render_progress, queue_progress_bar,
                 current_render_eta, queue_eta_txt,
                 current_render_cost, queue_cost_txt,
                 vid_large_view, sel_shot_info_vid, selected_vid_path],
        show_progress="hidden"
    )

    def toggle_queue_pause(pm):
        pm.queue_paused = not pm.queue_paused
        return "▶ Resume Queue" if pm.queue_paused else "⏸ Pause Queue"

    queue_pause_btn.click(toggle_queue_pause, inputs=[pm_state], outputs=[queue_pause_btn])

    def cancel_render_queue(pm):
        with pm.queue_lock:
            pm.render_queue.clear()
            pm.stop_video_generation = True
            pm.queue_paused = False
        return "🚫 Cancelling... current render will finish, then queue stops.", "⏸ Pause Queue"

    queue_cancel_btn.click(
        cancel_render_queue, inputs=[pm_state], outputs=[vid_gen_status, queue_pause_btn]
    ).then(
        lambda: (0, 0, "", "", "", ""),
        outputs=[current_render_progress, queue_progress_bar,
                 current_render_eta, queue_eta_txt,
                 current_render_cost, queue_cost_txt]
    )

    vid_gen_start_btn.click(
        batch_enqueue_shots,
        inputs=[vid_gen_mode_dropdown, vid_versions_dropdown, vid_resolution_dropdown,
                vid_vocal_prompt_mode, vid_style_dropdown, vid_director_dropdown, vid_firstframe_mode, pm_state],
        outputs=[vid_gen_status, vid_gen_start_btn]
    ).then(
        process_render_queue_if_idle,
        inputs=[pm_state, current_proj_var],
        outputs=[vid_gallery, vid_gen_status, gallery_paths_state,
                 current_render_progress, queue_progress_bar,
                 current_render_eta, queue_eta_txt,
                 current_render_cost, queue_cost_txt,
                 vid_large_view, sel_shot_info_vid, selected_vid_path],
        show_progress="hidden"
    ).then(
        lambda: gr.update(value="Start Batch Generation"),
        outputs=[vid_gen_start_btn]
    )

    vid_gen_stop_btn.click(
        cancel_render_queue, inputs=[pm_state], outputs=[vid_gen_status, queue_pause_btn]
    ).then(
        lambda: (0, 0, "", "", "", ""),
        outputs=[current_render_progress, queue_progress_bar,
                 current_render_eta, queue_eta_txt,
                 current_render_cost, queue_cost_txt]
    )

    def handle_vid_delete(path_to_del, proj, pm, gallery_paths):
        try:
            current_idx = gallery_paths.index(path_to_del)
        except ValueError:
            current_idx = -1

        new_gal, _ = delete_video_file(path_to_del, proj, pm)
        new_paths = [item[0] for item in new_gal]

        next_path = ""
        next_shot_id = ""
        if new_paths and current_idx >= 0:
            next_idx = min(current_idx, len(new_paths) - 1)
            next_path = new_paths[next_idx]
            fname = os.path.basename(next_path)
            next_shot_id = fname.split('_')[0] if '_' in fname else ""

        return new_gal, next_path or None, next_shot_id, next_path, new_paths

    del_vid_btn.click(handle_vid_delete, inputs=[selected_vid_path, current_proj_var, pm_state, gallery_paths_state], outputs=[vid_gallery, vid_large_view, sel_shot_info_vid, selected_vid_path, gallery_paths_state])

    def handle_regen_vid_and_prompt(shot_id_txt, selected_path, resolution, vocal_mode, style, director, generation_mode, proj, pm):
        if not shot_id_txt:
            yield gr.update(), "❌ No Shot ID selected", gr.update(), 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()
            return
        if pm.llm_busy:
            yield gr.update(), "⚠️ LLM already running — please wait.", gr.update(), 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()
            return
        pm.llm_busy = True
        try:
            settings = pm.load_project_settings()
            llm_model = settings.get("llm_model", "qwen3-vl-8b-instruct-abliterated-v2.0")
            plot = settings.get("plot", "")
            prompt_template = settings.get("prompt_template", config.DEFAULT_CONCEPT_PROMPT)
            performance_desc = settings.get("performance_desc", "")

            gal = get_project_videos(pm, proj)
            yield gal, f"⏳ Generating new prompt for {shot_id_txt}...", [item[0] for item in gal], 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()
            time.sleep(0.1)

            llm = LLMBridge()
            row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id_txt).upper()].tolist()
            if not row_idx:
                gal = get_project_videos(pm, proj)
                yield gal, f"❌ Shot {shot_id_txt} not found.", [item[0] for item in gal], 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()
                return
            index = row_idx[0]
            row = pm.df.loc[index]

            if row['Type'] == 'Vocal':
                final_vid_prompt = performance_desc
            else:
                loc_pos = pm.df.index.get_loc(index)
                if loc_pos > 0:
                    prev_index = pm.df.index[loc_pos - 1]
                    prev_shot_text = pm.df.loc[prev_index, 'Video_Prompt']
                    if pd.isna(prev_shot_text): prev_shot_text = "N/A"
                else:
                    prev_shot_text = "None (Start of video)"

                filled_prompt = prompt_template.replace("{plot}", plot)\
                    .replace("{type}", row['Type'])\
                    .replace("{start}", f"{row['Start_Time']:.1f}")\
                    .replace("{duration}", f"{row['Duration']:.1f}")\
                    .replace("{prev_shot}", prev_shot_text)

                final_vid_prompt = llm.query(config.LTX_SYSTEM_PROMPT, filled_prompt, llm_model)

            pm.df.at[index, 'Video_Prompt'] = final_vid_prompt
            pm.save_data()

            add_to_render_queue(shot_id_txt, resolution, vocal_mode, style, director, generation_mode, pm, delete_path=selected_path)
            gal = get_project_videos(pm, proj)
            yield gal, f"✅ Prompt saved. Added to queue.\n" + format_queue_status(pm), [item[0] for item in gal], 0, 0, "", "", "", "", gr.update(), gr.update(), gr.update()
        finally:
            pm.llm_busy = False

    regen_vid_same_prompt_btn.click(
        lambda shot_id, sel_path, res, vocal, style, director, gen_mode, pm:
            add_to_render_queue(shot_id, res, vocal, style, director, gen_mode, pm, delete_path=sel_path),
        inputs=[sel_shot_info_vid, selected_vid_path, vid_resolution_dropdown,
                vid_vocal_prompt_mode, vid_style_dropdown, vid_director_dropdown, vid_firstframe_mode, pm_state],
        outputs=[vid_gen_status]
    ).then(
        process_render_queue_if_idle,
        inputs=[pm_state, current_proj_var],
        outputs=[vid_gallery, vid_gen_status, gallery_paths_state,
                 current_render_progress, queue_progress_bar,
                 current_render_eta, queue_eta_txt,
                 current_render_cost, queue_cost_txt,
                 vid_large_view, sel_shot_info_vid, selected_vid_path],
        show_progress="hidden"
    )

    regen_vid_new_prompt_btn.click(
        handle_regen_vid_and_prompt,
        inputs=[sel_shot_info_vid, selected_vid_path, vid_resolution_dropdown,
                vid_vocal_prompt_mode, vid_style_dropdown, vid_director_dropdown, vid_firstframe_mode, current_proj_var, pm_state],
        outputs=[vid_gallery, vid_gen_status, gallery_paths_state,
                 current_render_progress, queue_progress_bar,
                 current_render_eta, queue_eta_txt,
                 current_render_cost, queue_cost_txt,
                 vid_large_view, sel_shot_info_vid, selected_vid_path],
        show_progress="hidden"
    ).then(
        process_render_queue_if_idle,
        inputs=[pm_state, current_proj_var],
        outputs=[vid_gallery, vid_gen_status, gallery_paths_state,
                 current_render_progress, queue_progress_bar,
                 current_render_eta, queue_eta_txt,
                 current_render_cost, queue_cost_txt,
                 vid_large_view, sel_shot_info_vid, selected_vid_path],
        show_progress="hidden"
    )

    tab3_ui.select(update_single_shot_choices, inputs=[pm_state, shared_shot_state], outputs=[single_shot_dropdown, shared_shot_state])

    return {
        "tab3_ui": tab3_ui,
        "vid_resolution_dropdown": vid_resolution_dropdown,
        "single_shot_dropdown": single_shot_dropdown,
        "vid_gallery": vid_gallery,
        "gallery_paths_state": gallery_paths_state,
        "vid_gen_start_btn": vid_gen_start_btn,
        "current_render_progress": current_render_progress,
        "queue_progress_bar": queue_progress_bar,
        "current_render_eta": current_render_eta,
        "queue_eta_txt": queue_eta_txt,
        "current_render_cost": current_render_cost,
        "queue_cost_txt": queue_cost_txt,
    }
