## Synesthesia AI Video Director — Initial Release

AI-powered music video creation tool that analyses vocal audio to build a shot timeline, uses a local LLM to generate cinematic video prompts, sends those prompts to LTX Desktop for video generation, and assembles the final video with your song audio.

### Features

- **AI-powered music video creation** from vocal audio analysis
- **LM Studio integration** for cinematic prompt generation via OpenAI-compatible API
- **LTX Desktop integration** for local AI video synthesis
- **Multiple video modes**: Intercut, All Vocals, All Action, Scripted
- **Dynamic resolution detection** — automatically adapts to LTX output resolutions
- **Customizable LLM prompt templates** for fine-tuning video style
- **CSV-based shot timeline** import/export for manual editing
- **Automatic silence detection** in Intercut mode for natural Vocal/Action shot transitions
- **Windows batch scripts** for easy install (install.bat, run.bat, update.bat)
- **Cross-platform support** (Python 3.8+, FFmpeg required)

### Bug Fixes

- PIL ANTIALIAS compatibility shim for Pillow 10+
- Rolling shutter fix via yuv420p pixel format enforcement
- moviepy pinned to <2.0 for API compatibility
- Windows asyncio event loop error handling

### Prerequisites

- [LM Studio](https://lmstudio.ai/) — local LLM server
- [LTX Desktop](https://ltx.studio/) — local AI video engine
- Python 3.8+
- FFmpeg on system PATH

### Quick Start (Windows)

```
git clone https://github.com/RowanUnderwood/Synesthesia-AI-Video-Director.git
cd Synesthesia-AI-Video-Director
install.bat
run.bat
```

See [README](https://github.com/RowanUnderwood/Synesthesia-AI-Video-Director/blob/main/README.MD) for full setup instructions.
