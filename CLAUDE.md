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
- **LTX duration snapping**: Shot durations are locked to 1-5 second increments at 24 fps for specific compatibility with the LTX Desktop application.  Other versions of LTX do not have this limitation.
- **Intercut mode**: Default mode that scans vocal audio for silence gaps to create alternating Vocal/Action shots.
- **Z-Image First Frame mode**: Before generating a video, sends the video prompt to LTX's image endpoint to produce a 1920×1080 first-frame image, then passes it as `imagePath` conditioning into the video generation call. First frames are saved to `first_frames/` and never reused.

## LTX Desktop API (http://127.0.0.1:8000/api)

Reverse-engineered from LTX-API-Files/. No official public docs exist.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/generate | Generate a video clip |
| POST | {discovered}/generate/image | Generate a still image (Z-image) — path discovered via OpenAPI |
| POST | /api/generate/cancel | Cancel active generation |
| GET  | /api/generation/progress | Poll generation progress |

### POST /api/generate — GenerateVideoRequest
- `prompt` (str, required)
- `resolution` (str): "512p", "540p", "720p", "1080p" — UI labels only, actual output varies
- `model` (str): "fast" | "pro"
- `cameraMotion` (str): "none" | "dolly_in" | "dolly_out" | "dolly_left" | "dolly_right" | "jib_up" | "jib_down" | "static" | "focus_shift"
- `negativePrompt` (str)
- `duration` (str): seconds as string, e.g. "3"
- `fps` (str): "24"
- `audio` (str): "true" | "false"
- `imagePath` (str | null): absolute path to first-frame image for i2v conditioning
- `audioPath` (str | null): absolute path to audio file for a2v
- `aspectRatio` (str): "16:9" | "9:16"

Response: `{ "status": str, "video_path": str | null }`

### POST {discovered}/generate/image — GenerateImageRequest
Built into LTX Desktop. Uses ZitImageGenerationPipeline (local GPU, ZImage model).
The exact path varies by LTX Desktop version — Synesthesia discovers it at startup by querying
`GET {host}/openapi.json` and finding the route whose requestBody references `GenerateImageRequest`.
- `prompt` (str, required)
- `width` (int): default 1024 — use 1920 for 1080p
- `height` (int): default 1024 — use 1080 for 1080p
- `numSteps` (int): default 4 — inference steps
- `numImages` (int): default 1

Response: `{ "status": str, "image_paths": list[str] | null }` — local absolute paths on the LTX Desktop machine.
Note: The POST blocks until generation completes; `image_paths[0]` in the response is the result.
Discovery: `_discover_zimage_url()` in `video.py` handles this — caches after first successful call.

### GET /api/generation/progress
Response: `{ "status": str, "phase": str, "progress": int, "currentStep": int|null, "totalSteps": int|null }`

### Important notes
- Only one generation can run at a time (video or image)
- Both video and image generation are polled via the same `/generation/progress` endpoint
- `imagePath` and `audioPath` must be absolute paths
- LTX output resolutions are multiples of 32 and vary by audio attachment — do NOT hardcode
