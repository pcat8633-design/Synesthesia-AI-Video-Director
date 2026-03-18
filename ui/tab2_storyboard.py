import os

import gradio as gr
import pandas as pd
from pydub import AudioSegment

import config
from models import LLMBridge
from timeline import get_existing_projects, scan_vocals_advanced, build_simple_timeline
from llm_logic import (generate_overarching_plot, generate_performance_description,
                       generate_concepts_logic, stop_gen, generate_story_file)
from utils import get_file_path


def build(pm_state, current_proj_var, shared_shot_state, vocals_up, lyrics_in):
    """Build Tab 2: Storyboard. Returns dict of exported components."""

    with gr.Tab("2. Storyboard") as tab2_ui:
        with gr.Accordion("Step 1: Timeline Settings", open=True):
            with gr.Row():
                video_mode_drp = gr.Dropdown(["Intercut", "All Vocals", "All Action", "Scripted"], value="Intercut", label="Mode")
            with gr.Row():
                min_silence_sl = gr.Slider(500, 2000, value=700, label="Min Silence (ms)")
                silence_thresh_sl = gr.Slider(-60, -20, value=-45, label="Silence Threshold (dB)")
            with gr.Row():
                shot_mode_drp = gr.Dropdown(["Fixed", "Random"], value="Random", label="Shot Duration Mode")
                min_shot_dur = gr.Slider(1, 5, value=2, label="Min Duration (s)")
                max_shot_dur = gr.Slider(1, 5, value=4, label="Max Duration (s)")
            with gr.Row(visible=False) as scripted_duration_row:
                scripted_total_dur = gr.Number(label="Total Duration (seconds)", value=60, precision=0)
                scripted_shot_count = gr.Number(label="Number of Shots (alternative)", value=0, precision=0)
                gr.Markdown("*Specify total duration OR shot count. If both > 0, total duration takes priority.*")
            with gr.Row():
                scan_btn = gr.Button("1. Scan Vocals & Build Timeline", variant="primary")
                scan_status = gr.Textbox(label="Build Status", interactive=False)

        with gr.Accordion("Step 2: Plot & Concept Generation", open=True):
            with gr.Row():
                avail_models = LLMBridge().get_models()
                last_model = config.get_global_llm()
                if not last_model:
                    last_model = avail_models[0] if avail_models else "qwen3-vl-8b-instruct-abliterated-v2.0"

                llm_dropdown = gr.Dropdown(choices=avail_models, value=last_model, label="Select LLM Model", interactive=True, allow_custom_value=True)
                refresh_llm_btn = gr.Button("🔄", size="sm")

                llm_dropdown.change(config.save_global_llm, inputs=[llm_dropdown])

            with gr.Row():
                rough_concept_in = gr.Textbox(label="Rough User Concept / Vibe (Optional)", placeholder="e.g. A cyberpunk rainstorm...", scale=2, lines=5)
                with gr.Column(scale=1):
                    singer_gender_in = gr.Textbox(label="Singer Gender (Optional)", placeholder="e.g. Female, Male, Non-binary (Leave blank to invent)", lines=1)
                    gen_performance_btn = gr.Button("Generate Singer, Band & Venue Desc")
                    performance_desc_in = gr.Textbox(label="Singer, Band, and Venue Description (Also used as Prompt for Vocal Shots)", placeholder="Short description of the singer, band, and venue setup", lines=2)

            gen_plot_btn = gr.Button("2. Generate Overarching Plot")
            plot_out = gr.Textbox(label="Overarching Plot (Optional)", lines=4, interactive=True)

            with gr.Accordion("Advanced: LLM Prompt Templates", open=False):
                gr.Markdown("Customize the prompts sent to the local LLM for each generation step. "
                            "Templates use `{placeholder}` syntax for dynamic values.")
                reset_templates_btn = gr.Button("Reset All Templates to Defaults")

                with gr.Accordion("Plot Generation Template", open=False):
                    plot_sys_prompt_in = gr.Textbox(value=config.DEFAULT_PLOT_SYSTEM_PROMPT_MUSIC, label="System Prompt (Music Video Mode)", lines=2)
                    plot_user_template_in = gr.Textbox(value=config.DEFAULT_PLOT_USER_TEMPLATE_MUSIC, label="User Prompt Template (Music Video Mode)", lines=4)
                    gr.Markdown("*Placeholders: `{concept}`, `{lyrics}`, `{timeline}`*")
                    plot_sys_prompt_scripted_in = gr.Textbox(value=config.DEFAULT_PLOT_SYSTEM_PROMPT_SCRIPTED, label="System Prompt (Scripted Mode)", lines=2)
                    plot_user_template_scripted_in = gr.Textbox(value=config.DEFAULT_PLOT_USER_TEMPLATE_SCRIPTED, label="User Prompt Template (Scripted Mode)", lines=4)
                    gr.Markdown("*Placeholders: `{concept}`, `{timeline}`*")

                with gr.Accordion("Performance Description Template", open=False):
                    perf_sys_prompt_in = gr.Textbox(value=config.DEFAULT_PERF_SYSTEM_PROMPT_MUSIC, label="System Prompt (Music Video Mode)", lines=2)
                    perf_user_template_in = gr.Textbox(value=config.DEFAULT_PERF_USER_TEMPLATE_MUSIC, label="User Prompt Template (Music Video Mode)", lines=4)
                    gr.Markdown("*Placeholders: `{concept}`, `{plot}`, `{gender_instruction}`*")
                    perf_sys_prompt_scripted_in = gr.Textbox(value=config.DEFAULT_PERF_SYSTEM_PROMPT_SCRIPTED, label="System Prompt (Scripted Mode)", lines=2)
                    perf_user_template_scripted_in = gr.Textbox(value=config.DEFAULT_PERF_USER_TEMPLATE_SCRIPTED, label="User Prompt Template (Scripted Mode)", lines=4)
                    gr.Markdown("*Placeholders: `{concept}`, `{plot}`, `{gender_instruction}`*")

                with gr.Accordion("Video Prompt Generation Template (Bulk)", open=False):
                    concepts_bulk_template_in = gr.Textbox(value=config.BULK_PROMPT_TEMPLATE, label="Intercut / All Action Template", lines=6)
                    gr.Markdown("*Placeholders: `{lyrics}`, `{plot}`, `{shot_list}`*")
                    concepts_vocals_template_in = gr.Textbox(value=config.ALL_VOCALS_PROMPT_TEMPLATE, label="All Vocals Template", lines=6)
                    gr.Markdown("*Placeholders: `{lyrics}`, `{plot}`, `{performance_desc}`, `{shot_list}`*")
                    concepts_scripted_template_in = gr.Textbox(value=config.SCRIPTED_PROMPT_TEMPLATE, label="Scripted Template", lines=6)
                    gr.Markdown("*Placeholders: `{gender}`, `{character_desc}`, `{concept}`, `{shot_list}`*")

                with gr.Accordion("Single Shot Regeneration Template (Used in Tab 3)", open=False):
                    prompt_template_in = gr.Textbox(value=config.DEFAULT_CONCEPT_PROMPT, label="Single Shot Prompt Template", lines=4)
                    gr.Markdown("*Placeholders: `{plot}`, `{prev_shot}`, `{start}`, `{duration}`, `{type}`*")

            with gr.Row():
                gen_concepts_btn = gr.Button("3. Generate Video Prompts (Bulk Generation)", variant="primary")
                stop_concepts_btn = gr.Button("Stop Generation", variant="stop")

            concept_gen_status = gr.Textbox(label="Concept Generation Status", interactive=False)

        with gr.Row():
            gr.Markdown("### 📂 Data Management")
            with gr.Row():
                export_csv_btn = gr.Button("Export CSV")
                csv_downloader = gr.File(label="Download Shot List", interactive=False)
            with gr.Row():
                download_story_btn = gr.Button("Download Story (.txt)")
                story_downloader = gr.File(label="Story Text File", interactive=False)
            with gr.Row():
                import_csv_btn = gr.UploadButton("Import CSV (Update Prompts)", file_types=[".csv"])
                import_status = gr.Textbox(label="Import Status", interactive=False)

        shot_table = gr.Dataframe(headers=config.REQUIRED_COLUMNS, interactive=True, wrap=True, type="pandas")

    # --- Tab 2 Internal Events ---

    t2_inputs = [current_proj_var, min_silence_sl, silence_thresh_sl, shot_mode_drp, min_shot_dur, max_shot_dur, llm_dropdown, rough_concept_in, plot_out, prompt_template_in, performance_desc_in, video_mode_drp, scripted_total_dur, scripted_shot_count, pm_state,
                 plot_sys_prompt_in, plot_user_template_in, plot_sys_prompt_scripted_in, plot_user_template_scripted_in,
                 perf_sys_prompt_in, perf_user_template_in, perf_sys_prompt_scripted_in, perf_user_template_scripted_in,
                 concepts_bulk_template_in, concepts_vocals_template_in, concepts_scripted_template_in]

    def auto_save_tab2(proj_name, min_sil, sil_thresh, mode, min_d, max_d, llm, concept, plot, template, performance_d, video_mode, s_total_dur, s_shot_count, pm,
                       p_sys_m, p_user_m, p_sys_s, p_user_s,
                       pf_sys_m, pf_user_m, pf_sys_s, pf_user_s,
                       c_bulk, c_vocals, c_scripted):
        if proj_name:
            pm.current_project = proj_name
            settings = {
                "min_silence": min_sil, "silence_thresh": sil_thresh, "shot_mode": mode,
                "min_dur": min_d, "max_dur": max_d, "llm_model": llm,
                "rough_concept": concept, "plot": plot, "prompt_template": template,
                "performance_desc": performance_d,
                "video_mode": video_mode,
                "scripted_total_dur": s_total_dur, "scripted_shot_count": s_shot_count,
                "plot_sys_prompt_music": p_sys_m, "plot_user_template_music": p_user_m,
                "plot_sys_prompt_scripted": p_sys_s, "plot_user_template_scripted": p_user_s,
                "perf_sys_prompt_music": pf_sys_m, "perf_user_template_music": pf_user_m,
                "perf_sys_prompt_scripted": pf_sys_s, "perf_user_template_scripted": pf_user_s,
                "concepts_bulk_template": c_bulk, "concepts_vocals_template": c_vocals,
                "concepts_scripted_template": c_scripted
            }
            pm.save_project_settings(settings)

    for tab2_comp in [min_silence_sl, silence_thresh_sl, shot_mode_drp, min_shot_dur, max_shot_dur, llm_dropdown, video_mode_drp, scripted_total_dur, scripted_shot_count]:
        tab2_comp.change(auto_save_tab2, inputs=t2_inputs)

    for tab2_text_comp in [rough_concept_in, plot_out, prompt_template_in, performance_desc_in,
                           plot_sys_prompt_in, plot_user_template_in, plot_sys_prompt_scripted_in, plot_user_template_scripted_in,
                           perf_sys_prompt_in, perf_user_template_in, perf_sys_prompt_scripted_in, perf_user_template_scripted_in,
                           concepts_bulk_template_in, concepts_vocals_template_in, concepts_scripted_template_in]:
        tab2_text_comp.blur(auto_save_tab2, inputs=t2_inputs)

    def reset_templates():
        return (
            config.DEFAULT_PLOT_SYSTEM_PROMPT_MUSIC, config.DEFAULT_PLOT_USER_TEMPLATE_MUSIC,
            config.DEFAULT_PLOT_SYSTEM_PROMPT_SCRIPTED, config.DEFAULT_PLOT_USER_TEMPLATE_SCRIPTED,
            config.DEFAULT_PERF_SYSTEM_PROMPT_MUSIC, config.DEFAULT_PERF_USER_TEMPLATE_MUSIC,
            config.DEFAULT_PERF_SYSTEM_PROMPT_SCRIPTED, config.DEFAULT_PERF_USER_TEMPLATE_SCRIPTED,
            config.BULK_PROMPT_TEMPLATE, config.ALL_VOCALS_PROMPT_TEMPLATE, config.SCRIPTED_PROMPT_TEMPLATE,
            config.DEFAULT_CONCEPT_PROMPT
        )
    reset_templates_btn.click(reset_templates, outputs=[
        plot_sys_prompt_in, plot_user_template_in,
        plot_sys_prompt_scripted_in, plot_user_template_scripted_in,
        perf_sys_prompt_in, perf_user_template_in,
        perf_sys_prompt_scripted_in, perf_user_template_scripted_in,
        concepts_bulk_template_in, concepts_vocals_template_in, concepts_scripted_template_in,
        prompt_template_in
    ])

    def on_mode_change(mode):
        is_scripted = (mode == "Scripted")
        is_intercut = (mode == "Intercut")

        silence_vis = gr.update(visible=is_intercut)
        scripted_vis = gr.update(visible=is_scripted)

        if is_scripted:
            scan_label = gr.update(value="1. Build Timeline")
        else:
            scan_label = gr.update(value="1. Scan Vocals & Build Timeline") if is_intercut else gr.update(value="1. Build Timeline")

        if is_scripted:
            gender_label = gr.update(label="Main Character's Gender (Optional)")
            perf_label = gr.update(label="Main Character and Setting Description")
            perf_btn_label = gr.update(value="Generate Main Character & Setting Desc")
        else:
            gender_label = gr.update(label="Singer Gender (Optional)")
            perf_label = gr.update(label="Singer, Band, and Venue Description (Also used as Prompt for Vocal Shots)")
            perf_btn_label = gr.update(value="Generate Singer, Band & Venue Desc")

        return [silence_vis, silence_vis, scripted_vis, scan_label, gender_label, perf_label, perf_btn_label]

    video_mode_drp.change(
        on_mode_change,
        inputs=[video_mode_drp],
        outputs=[min_silence_sl, silence_thresh_sl, scripted_duration_row, scan_btn, singer_gender_in, performance_desc_in, gen_performance_btn]
    )

    def run_scan(v_file, p_name, m_sil, s_thr, s_mode, min_d, max_d, v_mode, s_total_dur, s_shot_count, pm):
        yield "⏳ Initializing...", pm.df
        if not p_name:
            yield "❌ Error: No project selected.", pm.df
            return
        pm.current_project = p_name

        if v_mode == "Intercut":
            final_v_path = get_file_path(v_file) or pm.get_asset_path_if_exists("vocals.mp3")
            if not final_v_path or not os.path.exists(final_v_path):
                yield "❌ Error: No vocals file found.", pm.df
                return
            yield "⏳ Detecting silence and building timeline (this may take a moment)...", pm.df
            df = scan_vocals_advanced(final_v_path, p_name, m_sil, s_thr, s_mode, min_d, max_d, pm)

        elif v_mode in ("All Vocals", "All Action"):
            audio_path = get_file_path(v_file) or pm.get_asset_path_if_exists("vocals.mp3") or pm.get_asset_path_if_exists("full_song.mp3")
            if not audio_path or not os.path.exists(audio_path):
                yield "❌ Error: No audio file found. Upload a vocals or full song file.", pm.df
                return
            try:
                audio = AudioSegment.from_file(audio_path)
                total_dur = audio.duration_seconds
            except Exception as e:
                yield f"❌ Error loading audio: {e}", pm.df
                return
            shot_type = "Vocal" if v_mode == "All Vocals" else "Action"
            yield f"⏳ Building {v_mode.lower()} timeline ({total_dur:.1f}s)...", pm.df
            df = build_simple_timeline(total_dur, shot_type, s_mode, min_d, max_d, pm)

        elif v_mode == "Scripted":
            total_dur = 0
            if s_total_dur and s_total_dur > 0:
                total_dur = float(s_total_dur)
            elif s_shot_count and s_shot_count > 0:
                avg_dur = (min_d + max_d) / 2.0
                total_dur = float(s_shot_count) * avg_dur
            else:
                yield "❌ Error: Specify a Total Duration or Number of Shots for Scripted mode.", pm.df
                return
            yield f"⏳ Building scripted timeline ({total_dur:.1f}s)...", pm.df
            df = build_simple_timeline(total_dur, "Action", s_mode, min_d, max_d, pm)
        else:
            yield "❌ Error: Unknown mode.", pm.df
            return

        if df.empty:
            yield "❌ Error: Could not build timeline. Check settings.", pm.df
        else:
            yield "✅ Timeline Built Successfully!", df

    scan_btn.click(run_scan, inputs=[vocals_up, current_proj_var, min_silence_sl, silence_thresh_sl, shot_mode_drp, min_shot_dur, max_shot_dur, video_mode_drp, scripted_total_dur, scripted_shot_count, pm_state], outputs=[scan_status, shot_table])

    refresh_llm_btn.click(lambda: gr.update(choices=LLMBridge().get_models()), outputs=llm_dropdown)

    gen_performance_btn.click(generate_performance_description, inputs=[rough_concept_in, plot_out, singer_gender_in, llm_dropdown, video_mode_drp, perf_sys_prompt_in, perf_user_template_in, perf_sys_prompt_scripted_in, perf_user_template_scripted_in], outputs=performance_desc_in)
    gen_plot_btn.click(generate_overarching_plot, inputs=[rough_concept_in, lyrics_in, llm_dropdown, pm_state, video_mode_drp, plot_sys_prompt_in, plot_user_template_in, plot_sys_prompt_scripted_in, plot_user_template_scripted_in], outputs=plot_out)

    gen_concepts_btn.click(generate_concepts_logic, inputs=[plot_out, llm_dropdown, rough_concept_in, performance_desc_in, pm_state, video_mode_drp, singer_gender_in, concepts_bulk_template_in, concepts_vocals_template_in, concepts_scripted_template_in], outputs=[shot_table, concept_gen_status])
    stop_concepts_btn.click(stop_gen, inputs=[pm_state], outputs=[concept_gen_status])

    export_csv_btn.click(lambda pm: pm.export_csv(), inputs=[pm_state], outputs=csv_downloader)
    import_csv_btn.upload(lambda f, pm: pm.import_csv(f), inputs=[import_csv_btn, pm_state], outputs=[import_status, shot_table])
    download_story_btn.click(generate_story_file, inputs=[pm_state], outputs=[story_downloader])

    def save_manual_df_edits(new_df, pm):
        if pm.current_project:
            if isinstance(new_df, list):
                if new_df and len(new_df[0]) == len(config.REQUIRED_COLUMNS):
                    new_df = pd.DataFrame(new_df, columns=config.REQUIRED_COLUMNS)
                else:
                    return
            pm.df = new_df
            pm.save_data()

    shot_table.change(save_manual_df_edits, inputs=[shot_table, pm_state])

    tab2_ui.select(lambda pm: pm.df, inputs=[pm_state], outputs=[shot_table])

    return {
        "tab2_ui": tab2_ui,
        "shot_table": shot_table,
        "llm_dropdown": llm_dropdown,
        "video_mode_drp": video_mode_drp,
        # All fields needed as handle_load outputs
        "min_silence_sl": min_silence_sl,
        "silence_thresh_sl": silence_thresh_sl,
        "shot_mode_drp": shot_mode_drp,
        "min_shot_dur": min_shot_dur,
        "max_shot_dur": max_shot_dur,
        "rough_concept_in": rough_concept_in,
        "plot_out": plot_out,
        "prompt_template_in": prompt_template_in,
        "performance_desc_in": performance_desc_in,
        "scripted_total_dur": scripted_total_dur,
        "scripted_shot_count": scripted_shot_count,
        "scripted_duration_row": scripted_duration_row,
        "scan_btn": scan_btn,
        "singer_gender_in": singer_gender_in,
        "gen_performance_btn": gen_performance_btn,
        "plot_sys_prompt_in": plot_sys_prompt_in,
        "plot_user_template_in": plot_user_template_in,
        "plot_sys_prompt_scripted_in": plot_sys_prompt_scripted_in,
        "plot_user_template_scripted_in": plot_user_template_scripted_in,
        "perf_sys_prompt_in": perf_sys_prompt_in,
        "perf_user_template_in": perf_user_template_in,
        "perf_sys_prompt_scripted_in": perf_sys_prompt_scripted_in,
        "perf_user_template_scripted_in": perf_user_template_scripted_in,
        "concepts_bulk_template_in": concepts_bulk_template_in,
        "concepts_vocals_template_in": concepts_vocals_template_in,
        "concepts_scripted_template_in": concepts_scripted_template_in,
    }
