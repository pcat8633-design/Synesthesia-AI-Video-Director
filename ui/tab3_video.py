import os
import time

import gradio as gr
import pandas as pd

import config
from models import LLMBridge, sync_video_directory
from video import (get_project_videos, delete_video_file, generate_video_for_shot,
                   advanced_batch_video_generation)
from llm_logic import stop_gen


def build(pm_state, current_proj_var, shared_shot_state):
    """Build Tab 3: Video Generation. Returns dict of exported components."""

    with gr.Tab("3. Video Generation") as tab3_ui:
        selected_vid_path = gr.State("")
        gallery_paths_state = gr.State([])

        with gr.Row():
            vid_gen_mode_dropdown = gr.Dropdown(choices=["Generate Remaining Shots", "Regenerate all Shots", "Generate all Action Shots", "Generate all Vocal Shots"], value="Generate Remaining Shots", label="Generation Mode")
            vid_versions_dropdown = gr.Dropdown(choices=[1, 2, 3, 4, 5], value=1, label="Versions per Shot")
            vid_resolution_dropdown = gr.Dropdown(choices=["540p", "720p", "1080p"], value="1080p", label="Resolution")
            vid_vocal_prompt_mode = gr.Dropdown(choices=["Use Singer/Band Description", "Use Storyboard Prompt"], value="Use Singer/Band Description", label="Vocal Shot Prompt Mode")
            vid_style_dropdown = gr.Dropdown(choices=config.STYLE_NAMES, value="None", label="Style")
            vid_gen_start_btn = gr.Button("Start Batch Generation", variant="primary")
            vid_gen_stop_btn = gr.Button("Stop Batch Generation", variant="stop", visible=False)

        vid_gen_status = gr.Textbox(label="Batch Generation Status", interactive=False)

        gr.Markdown("### 🎯 Single Shot Generation")
        with gr.Row():
            single_shot_dropdown = gr.Dropdown(label="Select Shot to Generate", choices=[], interactive=True)
            single_shot_btn = gr.Button("Generate Additional Version", variant="primary")
        single_shot_prompt_edit = gr.Textbox(label="Edit Video Prompt for Selected Shot", lines=3, interactive=True)
        single_shot_status = gr.Textbox(label="Single Shot Status", interactive=False)

        with gr.Row():
            with gr.Column(scale=1):
                vid_gallery = gr.Gallery(label="Generated Video Thumbnails", columns=4, elem_classes=["scrollable-gallery"], allow_preview=False, interactive=True)

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
            return str(pm.df.loc[row_idx[0], 'Video_Prompt'])
        return ""

    single_shot_dropdown.change(load_single_shot_prompt, inputs=[single_shot_dropdown, pm_state], outputs=[single_shot_prompt_edit])
    single_shot_dropdown.change(lambda s: s, inputs=[single_shot_dropdown], outputs=[shared_shot_state])

    def save_single_shot_prompt(shot_id, new_prompt, pm):
        if not shot_id or pm.df.empty: return
        row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id).upper()].tolist()
        if row_idx:
            pm.df.at[row_idx[0], 'Video_Prompt'] = new_prompt
            pm.save_data()

    single_shot_prompt_edit.change(save_single_shot_prompt, inputs=[single_shot_dropdown, single_shot_prompt_edit, pm_state])

    def on_vid_gallery_select(evt: gr.SelectData, gallery_paths):
        if gallery_paths and evt.index < len(gallery_paths):
            fpath = gallery_paths[evt.index]
            fname = os.path.basename(fpath)
            shot_id = fname.split('_')[0] if '_' in fname else "Unknown"
            return fpath, shot_id, fpath, gr.update(value=shot_id)
        return None, "", "", gr.update()

    vid_gallery.select(on_vid_gallery_select, inputs=[gallery_paths_state], outputs=[vid_large_view, sel_shot_info_vid, selected_vid_path, single_shot_dropdown])

    start_vid_evt = vid_gen_start_btn.click(
        lambda: (gr.update(visible=False), gr.update(visible=True)), outputs=[vid_gen_start_btn, vid_gen_stop_btn]
    ).then(
        advanced_batch_video_generation, inputs=[vid_gen_mode_dropdown, vid_versions_dropdown, vid_resolution_dropdown, vid_vocal_prompt_mode, vid_style_dropdown, pm_state], outputs=[vid_gallery, vid_large_view, vid_gen_status, gallery_paths_state], show_progress="hidden", concurrency_id="generation", concurrency_limit=1
    ).then(
        lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[vid_gen_start_btn, vid_gen_stop_btn]
    )

    vid_gen_stop_btn.click(
        stop_gen, inputs=[pm_state], outputs=[vid_gen_status], cancels=[start_vid_evt]
    ).then(
        lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[vid_gen_start_btn, vid_gen_stop_btn]
    )

    def update_single_shot_choices(pm, shared_shot):
        if pm.df.empty: return gr.update(choices=[]), shared_shot
        choices = pm.df['Shot_ID'].dropna().unique().tolist()
        value = shared_shot if shared_shot in choices else None
        return gr.update(choices=choices, value=value), shared_shot

    def handle_single_shot(shot_id, res, vocal_mode, style, proj, pm):
        if pm.is_generating:
            gal = get_project_videos(pm, proj)
            yield gal, "❌ Error: A generation process is already actively running.", [item[0] for item in gal]
            return
        if not shot_id:
            gal = get_project_videos(pm, proj)
            yield gal, "❌ Error: No shot selected.", [item[0] for item in gal]
            return

        pm.is_generating = True
        try:
            vid_gen = generate_video_for_shot(shot_id, res, vocal_mode, pm, style)
            final_path = None
            for path, msg in vid_gen:
                if path is None:
                    gal = get_project_videos(pm, proj)
                    yield gal, f"⏳ {shot_id}: {msg}", [item[0] for item in gal]
                else:
                    final_path = path

            if final_path:
                sync_video_directory(pm)
                gal = get_project_videos(pm, proj)
                yield gal, f"✅ Finished generating new version of {shot_id}", [item[0] for item in gal]
            else:
                gal = get_project_videos(pm, proj)
                yield gal, f"❌ Failed to generate {shot_id}", [item[0] for item in gal]
        finally:
            pm.is_generating = False

    single_shot_btn.click(handle_single_shot, inputs=[single_shot_dropdown, vid_resolution_dropdown, vid_vocal_prompt_mode, vid_style_dropdown, current_proj_var, pm_state], outputs=[vid_gallery, single_shot_status, gallery_paths_state])

    def handle_vid_delete(path_to_del, proj, pm):
        new_gal, _ = delete_video_file(path_to_del, proj, pm)
        return new_gal, None, "", "", [item[0] for item in new_gal]

    del_vid_btn.click(handle_vid_delete, inputs=[selected_vid_path, current_proj_var, pm_state], outputs=[vid_gallery, vid_large_view, sel_shot_info_vid, selected_vid_path, gallery_paths_state])

    def handle_regen_vid(shot_id_txt, selected_path, resolution, vocal_mode, style, proj, pm):
        if pm.is_generating:
            yield gr.update(), gr.update(), "❌ Error: A generation process is already actively running.", gr.update()
            return
        if not shot_id_txt:
            yield gr.update(), gr.update(), "❌ No Shot ID selected", gr.update()
            return

        pm.is_generating = True
        try:
            if selected_path and os.path.exists(selected_path):
                try: os.remove(selected_path)
                except Exception as e: print(f"Could not delete file {selected_path}: {e}")

            vid_generator = generate_video_for_shot(shot_id_txt, resolution, vocal_mode, pm, style)
            final_path = None
            for path, msg in vid_generator:
                if path is None:
                    yield gr.update(), gr.update(), f"⏳ {shot_id_txt}: {msg}", gr.update()
                else:
                    final_path = path

            if final_path:
                sync_video_directory(pm)
                gal = get_project_videos(pm, proj)
                yield gal, final_path, f"✅ Finished regenerating {shot_id_txt}", [item[0] for item in gal]
            else:
                gal = get_project_videos(pm, proj)
                yield gal, gr.update(), f"❌ Failed to regenerate {shot_id_txt}", [item[0] for item in gal]
        finally:
            pm.is_generating = False

    def handle_regen_vid_and_prompt(shot_id_txt, selected_path, resolution, vocal_mode, style, proj, pm):
        if pm.is_generating:
            yield gr.update(), gr.update(), "❌ Error: A generation process is already actively running.", gr.update()
            return
        if not shot_id_txt:
            yield gr.update(), gr.update(), "❌ No Shot ID selected", gr.update()
            return

        pm.is_generating = True
        try:
            settings = pm.load_project_settings()
            llm_model = settings.get("llm_model", "qwen3-vl-8b-instruct-abliterated-v2.0")
            plot = settings.get("plot", "")
            prompt_template = settings.get("prompt_template", config.DEFAULT_CONCEPT_PROMPT)
            performance_desc = settings.get("performance_desc", "")

            gal = get_project_videos(pm, proj)
            yield gal, gr.update(), f"⏳ Generating new prompt for {shot_id_txt}...", [item[0] for item in gal]
            time.sleep(0.1)

            llm = LLMBridge()
            row_idx = pm.df.index[pm.df['Shot_ID'].astype(str).str.upper() == str(shot_id_txt).upper()].tolist()
            if not row_idx:
                gal = get_project_videos(pm, proj)
                yield gal, gr.update(), f"❌ Shot {shot_id_txt} not found.", [item[0] for item in gal]
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

            gal = get_project_videos(pm, proj)
            yield gal, gr.update(), f"⏳ Prompt generated. Starting video generation for {shot_id_txt}...", [item[0] for item in gal]
            time.sleep(0.1)

            if selected_path and os.path.exists(selected_path):
                try: os.remove(selected_path)
                except Exception as e: print(f"Could not delete file {selected_path}: {e}")

            vid_generator = generate_video_for_shot(shot_id_txt, resolution, vocal_mode, pm, style)
            final_path = None
            for path, msg in vid_generator:
                if path is None:
                    gal = get_project_videos(pm, proj)
                    yield gal, gr.update(), f"⏳ {shot_id_txt}: {msg}", [item[0] for item in gal]
                else:
                    final_path = path

            if final_path:
                sync_video_directory(pm)
                gal = get_project_videos(pm, proj)
                yield gal, final_path, f"✅ Finished regenerating prompt and video for {shot_id_txt}", [item[0] for item in gal]
            else:
                gal = get_project_videos(pm, proj)
                yield gal, gr.update(), f"❌ Failed to regenerate {shot_id_txt}", [item[0] for item in gal]
        finally:
            pm.is_generating = False

    regen_vid_same_prompt_btn.click(handle_regen_vid, inputs=[sel_shot_info_vid, selected_vid_path, vid_resolution_dropdown, vid_vocal_prompt_mode, vid_style_dropdown, current_proj_var, pm_state], outputs=[vid_gallery, vid_large_view, vid_gen_status, gallery_paths_state], show_progress="hidden")
    regen_vid_new_prompt_btn.click(handle_regen_vid_and_prompt, inputs=[sel_shot_info_vid, selected_vid_path, vid_resolution_dropdown, vid_vocal_prompt_mode, vid_style_dropdown, current_proj_var, pm_state], outputs=[vid_gallery, vid_large_view, vid_gen_status, gallery_paths_state], show_progress="hidden")

    tab3_ui.select(update_single_shot_choices, inputs=[pm_state, shared_shot_state], outputs=[single_shot_dropdown, shared_shot_state])

    return {
        "tab3_ui": tab3_ui,
        "vid_resolution_dropdown": vid_resolution_dropdown,
        "single_shot_dropdown": single_shot_dropdown,
        "vid_gallery": vid_gallery,
        "gallery_paths_state": gallery_paths_state,
        "vid_gen_start_btn": vid_gen_start_btn,
    }
