import gradio as gr


def build():
    """Build Tab 6: Help (static content)."""

    with gr.Tab("6. Help"):
        gr.HTML("""
        <a href="https://www.buymeacoffee.com/jacobpederson" target="_blank">
            <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 181px !important;" >
        </a>
        """)
        gr.Markdown("""
# Synesthesia AI Video Director — User Guide

This application helps you create AI-generated music videos by combining audio analysis, LLM-generated video prompts, and the LTX Desktop video generation engine.

---

## Tab 1 · Project & Assets

**Create a project** by typing a name and clicking *Create New Project*. This sets up all the necessary folders for your project. **Load an existing project** from the dropdown and click *Load Selected Project* — all your previous settings, prompts, and video paths will be restored automatically.

Upload your **vocals audio** (an isolated vocal track — stems work best). The vocals file is used for two things: scanning silence to build the shot timeline, and providing audio sync for generated vocal shots. Optionally upload a **full song** file, which is used as the audio track in the final assembled video.

Paste your **lyrics** in the text box. These are saved with the project and handed to the LLM when generating the overarching plot.

---

## Tab 2 · Storyboard

### Step 1 — Build the Timeline

Choose a **Mode** from the dropdown to control how the shot timeline is constructed:

| Mode | Description |
|------|-------------|
| **Intercut** (default) | Scans the vocals audio for silence gaps and creates alternating **Vocal** shots (singing detected) and **Action** shots (silent gaps). Requires a vocals audio file. The silence-detection sliders are only active in this mode. |
| **All Vocals** | Divides the entire audio duration into **Vocal**-type shots only. No silence detection is performed. Ideal for performance-focused music videos where every shot features the singer/band. |
| **All Action** | Divides the entire audio duration into **Action**-type shots only. No silence detection is performed. Ideal for narrative or visual-only videos that don't require lip-sync. |
| **Scripted** | No audio file is needed. You specify a **Total Duration** or **Number of Shots** instead. All shots are Action type. UI labels change from "Singer" to "Main Character", making this mode suited for short narrative films without music. |

Click *Scan Vocals & Build Timeline* (or *Build Timeline* in non-Intercut modes) to generate the shot list.

Adjust the sliders to fine-tune detection (Intercut mode) and shot lengths:
- **Min Silence (ms)** — how long a pause must be to count as silence (Intercut only)
- **Silence Threshold (dB)** — how quiet audio must be to be treated as silent (Intercut only)
- **Shot Duration Mode** — *Fixed* uses the Min Duration for every shot; *Random* picks a random length between Min and Max
- **Min/Max Duration** — the allowed range for shot lengths (1–5 seconds)

All shot durations are automatically locked to LTX-compatible frame counts (1–5 second increments at 24 fps).

### Step 2 — Generate Prompts

1. Select your **LLM model** from the dropdown. Click 🔄 to refresh the list from your LLM backend (LM Studio or llama-server).
2. Write a **rough concept** describing the vibe, setting, or mood of the video.
3. Click *Generate Singer, Band & Venue Desc* to create a concise visual description of your performer(s). This is also used as the video prompt for all Vocal shots.
4. Click *Generate Overarching Plot* to produce a cohesive linear narrative based on your concept and lyrics.
5. Click *Generate Video Prompts (Bulk Generation)* to send your entire timeline context, lyrics, and plots over to the LLM. It will return fully conceptualized, sequenced shot descriptions across all rows at once.

**Advanced — Prompt Templates:** Expand this section to customise the fallback instruction sent to the LLM for each Action shot (this is utilized mainly when regenerating single shots in Tab 3). The following placeholders are filled in automatically: `{plot}`, `{prev_shot}`, `{start}`, `{duration}`, `{type}`.

**Data Management:**
- *Export CSV* — download the full shot list with all prompts for external editing
- *Import CSV* — upload an edited CSV to push updated `Video_Prompt` values back in (Shot IDs and Types must match exactly)
- *Download Story (.txt)* — export every shot's prompt as a readable text file

---

## Tab 3 · Video Generation

### Batch Generation

Select a **Generation Mode**:
- *Generate Remaining Shots* — only shots that don't yet have a video
- *Generate all Action Shots* / *Generate all Vocal Shots* — target one shot type
- *Regenerate all Shots* — delete all existing videos and regenerate from scratch

Set how many **Versions per Shot** to generate (1–5). Having multiple versions gives you options to compare in Tab 4. Choose your **Resolution** (540p → 1080p). Click *Start Batch Generation* to begin. Click *Stop Batch Generation* to halt after the current shot finishes.

**Vocal Shot Prompt Mode** controls which prompt drives video generation for Vocal shots:
- *Use Singer/Band Description* — uses the performer/venue description from Tab 2
- *Use Storyboard Prompt* — uses the individually generated shot prompt

### Single Shot Generation

Select a specific shot from the dropdown, optionally edit its prompt inline (changes save automatically), then click *Generate Additional Version* to add another version without deleting existing ones.

### Gallery & Controls

All generated videos appear in the gallery with their Shot ID and frame count. Click a thumbnail to view it full-size on the right panel. From there you can:
- **🗑️ Delete This Video** — permanently removes the selected video file
- **♻️ Regenerate Video (Same Prompt)** — deletes the selected video and generates a new one with the same prompt
- **✨ Regenerate Video AND Prompt** — generates a fresh LLM prompt first, then generates a new video

---

## Tab 4 · Assembly & Cutting Room

### Version Comparison

Select a shot from the dropdown to see all its generated versions side by side (up to 5 at once).
- Click **⭐ Set as Active** on the version you want to use in the final edit
- Click **✂️ Move to Cutting Room Floor** to move an unwanted version out of the videos folder (it goes to the `cutting_room/` subfolder, not deleted)
- Use **➡️ Next Shot** to quickly cycle to the next shot that has multiple versions

The tab automatically refreshes its shot list when you switch to it.

### Final Assembly

Once you're satisfied with your active video selections:
- **Assemble Final Video (Strictly Videos)** — stops with an error if any shot is missing a video. Use this for a complete edit.
- **Assemble with Current Assets (Videos > Black Fallback)** — substitutes a black frame for any missing video. Useful for previewing a partial edit.

The assembled video is written to the project's `renders/` folder. The full song audio (from Tab 1) is attached if available; otherwise the vocals file is used as a fallback.

---

## Tab 5 · Settings

Configure the API endpoints used by the application:
- **Video Generation Backend** — select **LTX Desktop** (default) or **Wan2GP** (see below). The URL field pre-fills with the default for the chosen backend.
- **Video Backend API URL** — the base URL for the video generation backend (LTX Desktop default: `http://127.0.0.1:8000/api`; Wan2GP default: `http://127.0.0.1:7862/api`)
- **LLM API URL** — the base URL for the local LLM backend. Supports **LM Studio** (default: `http://127.0.0.1:1234/v1`) and **llama.cpp** `llama-server.exe` (default: `http://127.0.0.1:8080/v1`). When using llama-server, start it with at least **32K context** (`--ctx-size 32768`) for projects with large shot lists.

Click *Save Settings* to apply immediately and refresh the model list. Settings are stored globally in `global_settings.json` and persist across all projects and sessions.

---

## Wan2GP Alternative Backend

For GPUs with limited VRAM that can't run LTX Desktop, **Wan2GP** is a free open-source alternative. The Wan2.1 1.3B model runs on ~6–8 GB VRAM.

**Limitation:** Wan2GP does not support audio-guided generation. Vocal shots will be generated from their text prompt only (no lip-sync). All other features work normally.

#### Manual Install

1. Clone Wan2GP: `git clone https://github.com/deepbeepmeep/Wan2GP` and install its dependencies per its README
2. Install Flask in your Wan2GP virtual environment: `pip install flask`
3. Copy `wan2gp_server.py` from the Synesthesia folder into your Wan2GP folder
4. Start the bridge server: `python wan2gp_server.py --model t2v_1.3B`
5. In Synesthesia → Tab 5 Settings: select **Wan2GP** backend, verify the URL is `http://127.0.0.1:7862/api`, and click **Save Settings**

#### Pinokio Install

Pinokio sandboxes Wan2GP in its own Python environment. You must use Pinokio's Python — not the system Python — to run the bridge.

1. Find your **Pinokio home directory**: open Pinokio → Settings (the path is shown at the top). Call this `<pinokio_home>`. The Wan2GP app lives at `<pinokio_home>\api\wan2gp.git\app\`.
2. Install Flask using **Pinokio's pip** (run once):
   ```
   <pinokio_home>\api\wan2gp.git\app\env\Scripts\pip.exe install flask
   ```
3. Copy `wan2gp_server.py` from the Synesthesia folder into `<pinokio_home>\api\wan2gp.git\app\`.
4. **⚠️ Stop Pinokio's Wan2GP UI before continuing** — both the UI and the bridge try to load the model and will conflict if run together.
5. Start the bridge using **Pinokio's Python**:
   ```
   <pinokio_home>\api\wan2gp.git\app\env\Scripts\python.exe wan2gp_server.py --model t2v_1.3B
   ```
6. In Synesthesia → Tab 5 Settings: select **Wan2GP** backend, set the URL to `http://127.0.0.1:7862/api`, and click **Save Settings**.

**Available models:**

| Model | VRAM | Quality |
|-------|------|---------|
| `t2v_1.3B` | ~6 GB | Good |
| `t2v` | ~20 GB | Better (14B model) |
| `ltx2_22B_distilled` | ~24 GB | Best (same engine as LTX Desktop) |

---

## Tips & Workflow

1. **Vocals file is the backbone** — use a clean isolated vocal track for accurate silence detection. Stems from a vocal remover work well.
2. **Iterate on prompts** — use Export/Import CSV to batch-edit prompts in a spreadsheet before spending time on video generation.
3. **Generate multiple versions** — set Versions Per Shot to 2–3 and use the Cutting Room to pick the best take for each shot.
4. **Use Regenerate AND Prompt** on shots you're unhappy with — sometimes a fresh LLM pass produces a much better visual concept.
5. **Strict vs. Fallback assembly** — use Fallback mode to preview your edit before all shots are done, then switch to Strict for the final render.
6. **Hotkey** — press `Ctrl+R` in the terminal window to restart the application quickly without losing your project data.

---

## LTX Desktop VRAM Bypass

LTX Desktop may refuse to run if your GPU VRAM is below its default threshold. You can bypass this on a **fresh install** (before launching the app for the first time):

1. Navigate to `LTX Desktop\\resources\\backend\\runtime_config\\`
2. Open `runtime_policy.py` in a text editor
3. Find the Windows VRAM check and lower the threshold to below your available VRAM:

```python
if system == "Windows":
    if not cuda_available:
        return True
    if vram_gb is None:
        return True
    return vram_gb < 22
```

4. Change `22` to a value less than or equal to your GPU's VRAM (e.g. `< 8` for an 8 GB card)
5. Save the file, then start LTX Desktop — it will work, though generation may be slower

---

## Cloud LLM Prompt Template

If you prefer not to run a local LLM, you can use a cloud-based model (such as Claude, ChatGPT, etc.) to generate your video prompts. Here's how:

1. **Export** your shot list from Tab 2 using the **Export CSV** button.
2. **Open** your preferred cloud LLM in a browser.
3. **Attach** the exported shot list file to your message.
4. **Paste** the template below into the message, filling in the bracketed placeholders with your own details.
5. **Send** the message and wait for the LLM to return the completed shot list.
6. **Import** the completed file back into Synesthesia using the **Import CSV** button on Tab 2.

### Template (copy and paste this into your cloud LLM)

```
Create a music video via AI video prompts for the following song. See the attached shot list with durations and frame counts. We need to tell a coherent story using the shots labeled "action" in the type column. Return the shot list file with each "Video_Prompt" field filled out.

The AI video prompt for the vocal shots should always be very similar to the following as we cut to the live performance. We need to focus on consistency and always being closeup so the lip-sync model has enough pixels to work with.

"Handheld dynamic closeup shot of a [describe lead singer here] Dynamic camera movement with slight handheld shake, shallow depth of field, dramatic chiaroscuro lighting, 85mm lens, 24fps, high contrast, crowd silhouettes, energetic atmosphere, cinematic color grading, [describe color palette here] [name of singer] is careful to enunciate each word to the camera to account for their deaf sister's lip reading."

Follow the LTX prompt guide to create each "action" AI video model prompt:

- Establish the shot. Use cinematography terms that match your preferred film genre. Include aspects like scale or specific category characteristics to further refine the style you're looking for.
- Set the scene. Describe lighting conditions, color palette, surface textures, and atmosphere to shape the mood.
- Describe the action. Write the core action as a natural sequence, flowing from beginning to end.
- Define your character(s). Include age, hairstyle, clothing, and distinguishing details. Express emotions through physical cues.
- Identify camera movement(s). Specify when the view should shift and how. Including how subjects or objects appear after the camera motion gives the model a better idea of how to finish the motion.
- Keep your prompt in a single flowing paragraph to give the model a cohesive scene to work with.
- Use present tense verbs to describe movement and action.
- Match your detail to the shot scale. Closeups need more precise detail than wide shots.
- When describing camera movement, focus on the camera's relationship to the subject.
- You should expect to write 4 to 8 descriptive sentences to cover all the key aspects of the prompt.

Lead Singer's gender: [insert gender description here]
Story Idea: [insert story idea here]
Genre: [insert genre tags here]
Lyrics: [insert lyrics here]
```
        """)
