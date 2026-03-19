import os
import io
import time
import threading

import pandas as pd

import config
from models import LLMBridge

# ==========================================
# LOGIC: LLM GENERATION
# ==========================================

def generate_overarching_plot(concept, lyrics, llm_model, pm, video_mode="Intercut",
                              plot_sys_music="", plot_user_music="",
                              plot_sys_scripted="", plot_user_scripted=""):
    yield "⏳ Generating overarching plot... (Please wait)"
    llm = LLMBridge()
    df = pm.df

    if video_mode == "Scripted":
        sys_prompt = plot_sys_scripted.strip() if plot_sys_scripted and plot_sys_scripted.strip() else config.DEFAULT_PLOT_SYSTEM_PROMPT_SCRIPTED
        template = plot_user_scripted.strip() if plot_user_scripted and plot_user_scripted.strip() else config.DEFAULT_PLOT_USER_TEMPLATE_SCRIPTED
        timeline_str = ""
        if not df.empty:
            for idx, row in df.iterrows():
                timeline_str += f"[{row['Start_Time']:.2f}s - {row['End_Time']:.2f}s: Shot]\n"
        user_prompt = template.format(concept=concept, timeline=timeline_str)
        yield llm.query(sys_prompt, user_prompt, llm_model)
        return

    # Music video modes (Intercut, All Vocals, All Action)
    if df.empty:
        yield "Error: Timeline is empty."
        return

    timeline_str = ""
    for idx, row in df.iterrows():
        if row['Type'] == 'Vocal':
            timeline_str += f"[{row['Start_Time']:.2f}s - {row['End_Time']:.2f}s: SINGING]\n"

    sys_prompt = plot_sys_music.strip() if plot_sys_music and plot_sys_music.strip() else config.DEFAULT_PLOT_SYSTEM_PROMPT_MUSIC
    template = plot_user_music.strip() if plot_user_music and plot_user_music.strip() else config.DEFAULT_PLOT_USER_TEMPLATE_MUSIC
    user_prompt = template.format(concept=concept, lyrics=lyrics, timeline=timeline_str)
    yield llm.query(sys_prompt, user_prompt, llm_model)

def generate_performance_description(concept, plot, gender, llm_model, video_mode="Intercut",
                                     perf_sys_music="", perf_user_music="",
                                     perf_sys_scripted="", perf_user_scripted=""):
    yield "⏳ Generating description... (Please wait)"
    llm = LLMBridge()

    if video_mode == "Scripted":
        sys_prompt = perf_sys_scripted.strip() if perf_sys_scripted and perf_sys_scripted.strip() else config.DEFAULT_PERF_SYSTEM_PROMPT_SCRIPTED
        template = perf_user_scripted.strip() if perf_user_scripted and perf_user_scripted.strip() else config.DEFAULT_PERF_USER_TEMPLATE_SCRIPTED
        gender_instruction = f"Main Character's Gender: {gender}\n" if gender and gender.strip() else "Main Character's Gender: Please invent a gender.\n"
        user_prompt = template.format(concept=concept, plot=plot, gender_instruction=gender_instruction)
        yield llm.query(sys_prompt, user_prompt, llm_model)
        return

    sys_prompt = perf_sys_music.strip() if perf_sys_music and perf_sys_music.strip() else config.DEFAULT_PERF_SYSTEM_PROMPT_MUSIC
    template = perf_user_music.strip() if perf_user_music and perf_user_music.strip() else config.DEFAULT_PERF_USER_TEMPLATE_MUSIC
    gender_instruction = f"Singer Gender: {gender}\n" if gender and gender.strip() else "Singer Gender: Please invent a gender for the singer.\n"
    user_prompt = template.format(concept=concept, plot=plot, gender_instruction=gender_instruction)
    yield llm.query(sys_prompt, user_prompt, llm_model)

def generate_concepts_logic(overarching_plot, llm_model, rough_concept, performance_desc, pm, video_mode="Intercut", gender="",
                            bulk_template="", vocals_template="", scripted_template=""):
    llm = LLMBridge()
    df = pm.df
    pm.stop_generation = False

    if df.empty:
        yield df, "Error: Timeline is empty."
        return

    yield df, "⏳ LLM is thinking... (Check your LM Studio instance for progress)"
    time.sleep(0.1)

    shot_list_csv = df[['Shot_ID', 'Type', 'Duration', 'Total_Frames']].to_csv(index=False)
    sys_prompt = "You are an expert AI video prompt generator. Only output valid CSV data."

    if video_mode == "Scripted":
        tmpl = scripted_template.strip() if scripted_template and scripted_template.strip() else config.SCRIPTED_PROMPT_TEMPLATE
        user_prompt = tmpl.format(
            gender=gender if gender and gender.strip() else "Not specified",
            character_desc=performance_desc if performance_desc else "Not specified",
            concept=overarching_plot if overarching_plot else rough_concept if rough_concept else "None provided.",
            shot_list=shot_list_csv
        )
    elif video_mode == "All Vocals":
        lyrics = pm.get_lyrics()
        tmpl = vocals_template.strip() if vocals_template and vocals_template.strip() else config.ALL_VOCALS_PROMPT_TEMPLATE
        user_prompt = tmpl.format(
            lyrics=lyrics if lyrics else "None provided.",
            plot=overarching_plot if overarching_plot else rough_concept if rough_concept else "None provided.",
            performance_desc=performance_desc if performance_desc else "Not specified.",
            shot_list=shot_list_csv
        )
    else:
        # Intercut and All Action use the standard bulk template
        lyrics = pm.get_lyrics()
        tmpl = bulk_template.strip() if bulk_template and bulk_template.strip() else config.BULK_PROMPT_TEMPLATE
        user_prompt = tmpl.format(
            lyrics=lyrics if lyrics else "None provided.",
            plot=overarching_plot if overarching_plot else rough_concept if rough_concept else "None provided.",
            shot_list=shot_list_csv
        )

    result_box = [None]
    def _run_query(): result_box[0] = llm.query(sys_prompt, user_prompt, llm_model)
    t = threading.Thread(target=_run_query, daemon=True)
    t.start()
    elapsed, warned = 0, False
    while t.is_alive():
        if pm.stop_generation:
            yield df, "🛑 Stopped."
            return
        time.sleep(1)
        elapsed += 1
        if elapsed >= 120 and not warned:
            yield df, "⚠️ LLM is taking longer than 2 minutes. Click *Stop Generation* to cancel, or continue waiting..."
            warned = True
    t.join()
    response = result_box[0]
    if response is None:
        yield df, "❌ LLM query failed or returned no result."
        return

    if pm.stop_generation:
        yield df, "🛑 Stopped."
        return

    yield df, "⏳ Parsing CSV response..."
    time.sleep(0.1)

    csv_text = response
    if "```csv" in response:
        csv_text = response.split("```csv")[1].split("```")[0].strip()
    elif "```" in response:
        csv_text = response.split("```")[1].split("```")[0].strip()

    try:
        new_df = pd.read_csv(io.StringIO(csv_text))

        if not all(col in new_df.columns for col in ["Shot_ID", "Type", "Video_Prompt"]):
            yield df, "❌ Error: LLM returned malformed CSV missing required columns (Shot_ID, Type, Video_Prompt)."
            print("LLM Response:\n", response)
            return

        for _, row in new_df.iterrows():
            sid = str(row.get('Shot_ID', '')).strip()
            prompt_raw = row.get('Video_Prompt', '')
            prompt = "" if pd.isna(prompt_raw) else str(prompt_raw).strip()
            if prompt.lower() == 'nan':
                prompt = ""

            match_idx = df.index[df['Shot_ID'].astype(str).str.upper() == sid.upper()].tolist()
            if match_idx:
                df.at[match_idx[0], 'Video_Prompt'] = prompt

        # Post-process: In Intercut mode, override Vocal shots with performance description
        if video_mode == "Intercut":
            for index, row in df.iterrows():
                if row['Type'] == 'Vocal':
                    df.at[index, 'Video_Prompt'] = performance_desc

        pm.df = df
        pm.save_data()
        yield df, "🎉 Concept Generation Complete!"

    except Exception as e:
        yield df, f"❌ Error parsing LLM CSV response: {str(e)}"
        print("LLM Response:\n", response)

def stop_gen(pm):
    pm.stop_generation = True
    pm.stop_video_generation = True
    pm.is_generating = False
    return "🛑 Stopping... Waiting for current task to complete..."

def generate_story_file(pm):
    if not pm.current_project or pm.df.empty: return None
    story_content = ""
    for _, row in pm.df.iterrows():
        sid = row.get("Shot_ID", "Unknown")
        prompt = row.get("Video_Prompt", "No prompt generated.")
        story_content += f"Shot {sid}:\n{prompt}\n\n"

    path = os.path.join(pm.base_dir, pm.current_project, "story.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(story_content)
    return path
