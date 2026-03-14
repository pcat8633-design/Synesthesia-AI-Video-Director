# Synesthesia AI Video Director

Synesthesia AI Video Director is an AI-powered music video creation tool. It analyses vocal audio to build a shot timeline, uses a local LLM to generate cinematic video prompts, sends those prompts to LTX Desktop for video generation, and assembles the final video with your song audio.

## Prerequisites

You will need two external applications running alongside this tool:

- **[LM Studio](https://lmstudio.ai/)** — Local LLM inference server. Load a model (e.g. Qwen, LLaMA) and start the server on the default port (`http://127.0.0.1:1234`). LM Studio provides the language model that writes video prompts and plot summaries.

- **[LTX Desktop](https://ltx.io/ltx-desktop)** — Local AI video generation engine. Start the LTX Desktop server on the default port (`http://127.0.0.1:8000`). LTX Desktop generates the actual video clips from the prompts.

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/RowanUnderwood/Synesthesia-AI-Video-Director.git
   cd Synesthesia-AI-Video-Director
   ```

2. **Create a virtual environment (recommended)**

   ```bash
   python -m venv venv
   source venv/bin/activate        # Linux / macOS
   venv\Scripts\activate           # Windows
   ```

3. **Install Python dependencies**

   ```bash
   pip install gradio pandas pydub moviepy requests keyboard
   ```

   > **Note:** `pydub` requires [FFmpeg](https://ffmpeg.org/) to be installed and available on your system PATH.

4. **Start the external services**

   - Open **LM Studio**, load a model, and start the local server.
   - Open **LTX Desktop** and start the API server.

5. **Launch the application**

   ```bash
   python app.py
   ```

   The Gradio interface will open in your browser (typically at `http://127.0.0.1:7860`).

## Usage

### Quick-Start Workflow

1. **Create a Project** (Tab 1) — Give your project a name and click *Create New Project*.
2. **Upload Assets** (Tab 1) — Upload an isolated vocal track (for timeline scanning), optionally upload the full song (for final assembly), and paste your lyrics.
3. **Build the Timeline** (Tab 2) — Choose a mode, adjust silence detection settings, and click *Scan Vocals & Build Timeline*. The app splits your audio into Vocal and Action shots.
4. **Generate Prompts** (Tab 2) — Select your LLM model, write a rough concept, then generate the overarching plot and video prompts with the bulk generation button.
5. **Generate Videos** (Tab 3) — Pick a generation mode and resolution, then click *Start Batch Generation*. LTX Desktop will render each shot.
6. **Review & Assemble** (Tab 4) — Compare video versions for each shot, pick the best take, and assemble the final video with audio.

### Video Modes

The **Mode** dropdown on Tab 2 controls how the shot timeline is built:

| Mode | Description |
|------|-------------|
| **Intercut** | Default. Scans vocals for silence gaps and creates alternating Vocal and Action shots. Requires a vocals audio file. |
| **All Vocals** | Divides the entire audio duration into Vocal-type shots only. Great for performance-focused music videos. |
| **All Action** | Divides the entire audio duration into Action-type shots only. Great for narrative or visual-only videos. |
| **Scripted** | No audio file needed. Specify a total duration or number of shots. All shots are Action type. Designed for short narrative films. |

### Settings

API endpoints for LTX Desktop and LM Studio can be changed on Tab 5. Settings persist across projects in `global_settings.json`.

### Hotkey

Press `Ctrl+R` in the terminal to restart the application without losing project data.

## License

See [LICENSE](LICENSE) for details.
