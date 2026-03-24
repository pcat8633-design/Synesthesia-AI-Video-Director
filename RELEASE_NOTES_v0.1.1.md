## Synesthesia AI Video Director — v0.1.1

### New Features

- **Character Bibles** — define consistent character descriptions that are automatically injected into video prompts and included in the generated story file
- **Video Styles** — apply named style presets (from `styles.json`) to prompts at generation time; filter assembly by style in Tab 4
- **Cutting Room Floor** — assemble all alternate takes into a single review video from Tab 4
- **Z-Image First Frame mode** — generates a still image as the first frame before each video clip for stronger visual consistency (i2v conditioning)
- **Wan2GP backend support** — alternative to LTX Desktop for GPUs with less VRAM; configurable in Tab 5 Settings
- **Render queue with pause/cancel** — batch generation now uses a persistent queue; pause mid-batch or cancel without losing progress
- **VRAM leak detection** — monitors GPU memory between renders and warns if VRAM isn't being freed (requires pynvml)
- **Render cost & ETA estimates** — real-time cost ($/kWh) and time estimates per shot and for the full queue, with automatic calibration from your hardware
- **Per-shot resolution tracking** — each shot records the resolution it was rendered at; used for accurate cost estimates and assembly
- **10-second shot support** — max shot duration extended from 5s to 10s (720p and below)
- **Flexible CSV import for non-Intercut modes** — in All Vocals, All Action, and Scripted modes, shot count and durations can be freely changed on import; timings are recalculated automatically with LTX duration snapping
- **Directed by presets** — apply cinematic director styles to generation prompts
- **llama.cpp / local API support** — any OpenAI-compatible endpoint works in addition to LM Studio

### Improvements

- **Simplified launcher** — `install.bat`, `update.bat`, and `run.bat` merged into a single `run.bat`; auto-installs on first run, checks for updates on every launch with a Y/N prompt; `GIT_BRANCH` setting switches between stable releases and dev tracking
- **Tab 5 Settings** — GPU selector, electricity cost, system wattage, and calibration stats panel all configurable in-app; no more manual JSON editing
- **Modular UI architecture** — app split into per-tab modules for easier maintenance
- **Assembly style filtering** — assemble a cut using only clips from a specific style

### Bug Fixes

- Z-Image endpoint discovery fixed for newer LTX Desktop versions (dynamic OpenAPI lookup)
- Z-Image ETA model corrected
- Tab 4 race condition on assembly button fixed
- Tab 3 gallery index desync during active generation fixed
- `assembly.py` shot-label `TypeError` (PIL float coordinate) fixed
- `VideoFileClip` probe resource leak in all three assembly functions fixed
- NaN passthrough for `Render_Resolution` in flexible CSV import fixed
- LM Studio URL reset to `127.0.0.1` in default config (was developer LAN IP)
- `core.autocrlf` ambiguity resolved via `.gitattributes` (LF for source, CRLF for `.bat`)

### Prerequisites

- [LM Studio](https://lmstudio.ai/) or any OpenAI-compatible local LLM server
- [LTX Desktop](https://ltx.studio/) or [Wan2GP](https://github.com/deepbeepmeep/Wan2GP)
- Python 3.8+
- FFmpeg on system PATH

### Quick Start (Windows)

```
git clone https://github.com/RowanUnderwood/Synesthesia-AI-Video-Director.git
cd Synesthesia-AI-Video-Director
run.bat
```

`run.bat` handles installation automatically on first run. See [README](https://github.com/RowanUnderwood/Synesthesia-AI-Video-Director/blob/main/README.MD) for full setup instructions.
