import os
import shutil

import gradio as gr
import pandas as pd

import config
from timeline import get_existing_projects
from utils import get_file_path, format_time


def build(pm_state, current_proj_var):
    """Build Tab 1: Project & Assets. Returns dict of components needed by other tabs."""

    with gr.Tab("1. Project & Assets") as tab1_ui:
        gr.Markdown("### Create or Load")
        with gr.Row():
            with gr.Column():
                proj_name = gr.Textbox(label="New Project Name", placeholder="MyMusicVideo_v1")
                create_btn = gr.Button("Create New Project")
            with gr.Column():
                with gr.Row():
                    project_dropdown = gr.Dropdown(choices=get_existing_projects(), label="Select Existing Project", interactive=True)
                    refresh_proj_btn = gr.Button("🔄", size="sm")
                with gr.Row():
                    load_btn = gr.Button("Load Selected Project")
                    delete_proj_btn = gr.Button("Delete Selected Project", variant="stop")
                with gr.Row(visible=False) as confirm_delete_row:
                    gr.Markdown("⚠️ **Are you sure?** This permanently deletes the project and all its files.")
                    confirm_delete_btn = gr.Button("Yes, Delete It", variant="stop")
                    cancel_delete_btn = gr.Button("Cancel")

        with gr.Row():
            proj_status = gr.Textbox(label="System Status", interactive=False)
            time_spent_disp = gr.Textbox(label="Total Project Time", interactive=False)

        gr.Markdown("### Assets")
        with gr.Row():
            vocals_up = gr.Audio(label="Upload Vocals (Audio)", type="filepath")
            song_up = gr.Audio(label="Upload Full Song (Audio)", type="filepath")
            lyrics_in = gr.Textbox(label="Lyrics", lines=5)

    # --- Tab 1 Internal Events ---

    refresh_proj_btn.click(lambda: gr.update(choices=get_existing_projects()), outputs=[project_dropdown])

    def handle_delete_project(name, pm):
        if not name: return "No project selected.", gr.update()
        path = os.path.join(pm.base_dir, name)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                if pm.current_project == name:
                    pm.current_project = None
                    pm.df = pd.DataFrame(columns=config.REQUIRED_COLUMNS)
                return f"Deleted project '{name}'.", gr.update(choices=get_existing_projects(), value=None)
            except Exception as e:
                return f"Error deleting project: {e}", gr.update()
        return "Project not found.", gr.update()

    delete_proj_btn.click(
        lambda: (gr.update(visible=True), gr.update(visible=False)),
        outputs=[confirm_delete_row, delete_proj_btn]
    )

    confirm_delete_btn.click(
        handle_delete_project,
        inputs=[project_dropdown, pm_state],
        outputs=[proj_status, project_dropdown]
    ).then(
        lambda: (gr.update(visible=False), gr.update(visible=True)),
        outputs=[confirm_delete_row, delete_proj_btn]
    )

    cancel_delete_btn.click(
        lambda: (gr.update(visible=False), gr.update(visible=True)),
        outputs=[confirm_delete_row, delete_proj_btn]
    )

    def auto_save_lyrics(proj_name_val, text, pm):
        if proj_name_val:
            pm.current_project = proj_name_val
            pm.save_lyrics(text)

    def auto_save_files(proj_name_val, v_file, s_file, pm):
        if proj_name_val:
            v_src = get_file_path(v_file)
            s_src = get_file_path(s_file)
            if v_src: pm.save_asset(v_src, "vocals.mp3")
            if s_src: pm.save_asset(s_src, "full_song.mp3")

    lyrics_in.change(auto_save_lyrics, inputs=[current_proj_var, lyrics_in, pm_state])

    for file_comp in [vocals_up, song_up]:
        file_comp.upload(auto_save_files, inputs=[current_proj_var, vocals_up, song_up, pm_state])
        file_comp.clear(auto_save_files, inputs=[current_proj_var, vocals_up, song_up, pm_state])

    return {
        "tab1_ui": tab1_ui,
        "proj_name": proj_name,
        "create_btn": create_btn,
        "project_dropdown": project_dropdown,
        "load_btn": load_btn,
        "proj_status": proj_status,
        "time_spent_disp": time_spent_disp,
        "vocals_up": vocals_up,
        "song_up": song_up,
        "lyrics_in": lyrics_in,
    }
