# Synesthesia AI Video Director — Project Context

## Architecture

Modular Gradio application split across `app.py` (entry point) and supporting modules:
- **`models.py`** — `ProjectManager` (project I/O, CSV, assets) and `LLMBridge` (LM Studio API)
- **`config.py`** — API endpoints, resolution map, LLM prompt templates, style loading
- **`timeline.py`** — Audio silence analysis, shot generation, LTX frame locking
- **`llm_logic.py`** — Prompt/plot generation orchestration, LLM response parsing
- **`video.py`** — LTX video generation per shot, gallery display, frame count cache
- **`assembly.py`** — moviepy video assembly, cutting room floor compilation
- **`utils.py`** — Frame snapping, base64 image encoding, restart hotkey
- **`ui/`** — Gradio UI split into 6 tabs (project, storyboard, video, assembly, settings, help)

Orchestrates:
- **LM Studio** (local LLM) — generates video prompts and plot summaries via OpenAI-compatible API
- **LTX Desktop** (local AI video engine) — generates video clips from prompts
- **moviepy 1.x** — assembles clips into final video with audio

## Critical: LTX Desktop Resolution Handling

LTX Desktop generates videos at resolutions that are **multiples of 32** for optimal GPU processing. The actual output resolutions do NOT match standard video resolutions, and they **vary depending on whether audio is attached** to the clip (Vocal vs Action shots produce different resolutions at the same preset). For example, 540p without audio = 960x512, but 540p with audio = 960x576.

Because LTX output resolutions are unpredictable, `RESOLUTION_MAP` uses standard resolutions (for UI labels and API requests only). The `assemble_video` function **dynamically detects** the target resolution by reading the first available video clip's actual dimensions. All other clips are resized to match. Do NOT hardcode LTX output resolutions.

## Dependencies

- **moviepy must be < 2.0** — the codebase uses `from moviepy.editor import ...` which was removed in moviepy 2.x. Version is pinned in `requirements.txt`.
- **pydub** requires FFmpeg installed on the system PATH.
- **keyboard** is used for the Ctrl+R restart hotkey.
- **`styles.json`** — optional file in the project root that defines named prompt style presets; loaded at startup by `config.py`.

## Key Domain Concepts

- **Shot Types**: "Vocal" (singing/performance) and "Action" (narrative/visual). These control prompt generation strategy and audio attachment during video generation.
- **LTX duration snapping**: Shot durations are locked to 1-5 second increments at 24 fps for LTX compatibility.
- **Intercut mode**: Default mode that scans vocal audio for silence gaps to create alternating Vocal/Action shots.
