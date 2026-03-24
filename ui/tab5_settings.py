import gradio as gr

import config
from models import LLMBridge

_DEFAULT_URLS = {
    "LTX Desktop": "http://127.0.0.1:8000/api",
    "Wan2GP":       "http://127.0.0.1:7862/api",
}


def build(pm_state, llm_dropdown):
    """Build Tab 5: Settings."""

    with gr.Tab("5. Settings"):
        gr.Markdown("### ⚙️ Global Settings")
        gr.Markdown("These settings apply globally across all projects and are saved immediately on click.")
        with gr.Row():
            video_backend_drp = gr.Dropdown(
                choices=["LTX Desktop", "Wan2GP"],
                value=config.VIDEO_BACKEND,
                label="Video Generation Backend",
            )
            video_api_url_in = gr.Textbox(
                label="Video Backend API URL",
                value=config.LTX_BASE_URL,
                placeholder="http://127.0.0.1:8000/api",
            )
            lm_url_in = gr.Textbox(
                label="LLM API URL (LM Studio / llama.cpp)",
                value=config.LM_STUDIO_URL,
                placeholder="http://127.0.0.1:1234/v1",
            )
            electricity_cost_in = gr.Number(
                label="Electricity Cost ($/kWh)",
                value=config.ELECTRICITY_COST,
                minimum=0.0,
                maximum=10.0,
                step=0.001,
                info="Used for render cost estimates. Default: $0.1805 (18.05¢/kWh)",
            )
            system_wattage_in = gr.Number(
                label="System Wattage (W)",
                value=config.SYSTEM_WATTAGE,
                minimum=50,
                maximum=5000,
                step=10,
                info="Full system draw during video generation. Default: 600W (RTX 5090 system)",
            )
        _gpu_choices = config.get_gpu_list()
        _gpu_default_idx = config.GPU_MONITOR_INDEX
        _gpu_default = next((c for c in _gpu_choices if c.startswith(str(_gpu_default_idx))), _gpu_choices[0])
        gpu_monitor_drp = gr.Dropdown(
            label="GPU to Monitor (VRAM leakage detection)",
            choices=_gpu_choices,
            value=_gpu_default,
            info="Select the GPU used by LTX Desktop. Requires pynvml. For multi-GPU systems.",
        )
        with gr.Row():
            save_settings_btn = gr.Button("💾 Save Settings", variant="primary")
            calibration_reset_btn = gr.Button("🔄 Reset Render Calibration", variant="secondary")
        settings_status = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📊 Render Calibration Stats", open=False):
            calibration_stats_txt = gr.Textbox(
                label="Current Calibration Data",
                value=config.get_calibration_summary(),
                interactive=False,
                lines=8,
            )
            calibration_refresh_btn = gr.Button("🔄 Refresh Stats", variant="secondary")

        with gr.Accordion("Wan2GP Setup Instructions", open=(config.VIDEO_BACKEND == "Wan2GP")) as wan2gp_accordion:
            gr.Markdown("""
**Wan2GP** is a free open-source video generation app that runs on GPUs with less VRAM than LTX Desktop.
The Wan2.1 1.3B model runs on ~6 GB VRAM.

> **Note:** Wan2GP does not support audio-guided generation. Vocal shots will be generated
> from their text prompt only — no lip-sync. All other Synesthesia features work normally.

---

#### Manual Install

1. Clone Wan2GP: `git clone https://github.com/deepbeepmeep/Wan2GP` and follow its README
2. Install Flask in your Wan2GP virtual environment: `pip install flask`
3. Copy `wan2gp_server.py` from the Synesthesia folder into your Wan2GP folder
4. Start the bridge server:
   ```
   python wan2gp_server.py --model t2v_1.3B
   ```
5. Set **Video Backend API URL** above to `http://127.0.0.1:7862/api` and click **Save Settings**

---

#### Pinokio Install

Pinokio sandboxes Wan2GP in its own Python environment — you must use Pinokio's Python, not the system Python.

1. Find your Pinokio home directory: open **Pinokio → Settings** (shown at the top of the page). Call this path `<pinokio_home>`.
2. Install Flask using **Pinokio's pip** (run once in a terminal):
   ```
   <pinokio_home>\\api\\wan2gp.git\\app\\env\\Scripts\\pip.exe install flask
   ```
3. Copy `wan2gp_server.py` from the Synesthesia folder into:
   `<pinokio_home>\\api\\wan2gp.git\\app\\`
4. **⚠️ Stop Pinokio's Wan2GP UI before starting the bridge** — both try to load the model and will conflict.
5. Start the bridge using **Pinokio's Python**:
   ```
   <pinokio_home>\\api\\wan2gp.git\\app\\env\\Scripts\\python.exe wan2gp_server.py --model t2v_1.3B
   ```
6. Set **Video Backend API URL** above to `http://127.0.0.1:7862/api` and click **Save Settings**

---

**Available models:**

| Model | VRAM | Notes |
|-------|------|-------|
| `t2v_1.3B` | ~6 GB | Good quality, runs on modest GPUs |
| `t2v` | ~20 GB | Better quality (14B model) |
| `ltx2_22B_distilled` | ~24 GB | Best quality (same engine as LTX Desktop) |
""")

        backend_switch_status = gr.Textbox(label="", interactive=False, visible=True)

    # --- Events ---

    def on_backend_change(backend, pm):
        if backend == "Wan2GP":
            df = pm.load_dataframe()
            if df is not None and not df.empty and "Total_Frames" in df.columns:
                oversized = df[df["Total_Frames"] > 81]
                if not oversized.empty:
                    shot_ids = ", ".join(str(s) for s in oversized["Shot_ID"].tolist()[:5])
                    return (
                        gr.update(value="LTX Desktop"),
                        gr.update(value=_DEFAULT_URLS["LTX Desktop"]),
                        gr.update(open=False),
                        gr.update(value=f"❌ Cannot switch to Wan2GP: shots {shot_ids} exceed 81 frames (3s max). Shorten or regenerate timeline first."),
                    )
            if df is not None and not df.empty and "Video_Path" in df.columns:
                has_videos = df["Video_Path"].notna() & (df["Video_Path"].astype(str).str.strip() != "")
                if has_videos.any():
                    return (
                        gr.update(value="LTX Desktop"),
                        gr.update(value=_DEFAULT_URLS["LTX Desktop"]),
                        gr.update(open=False),
                        gr.update(value="❌ Cannot switch to Wan2GP: LTX-generated videos already exist. Delete them first to avoid timing mismatches."),
                    )
        url = _DEFAULT_URLS.get(backend, config.LTX_BASE_URL)
        is_wan2gp = (backend == "Wan2GP")
        return gr.update(), gr.update(value=url), gr.update(open=is_wan2gp), gr.update(value="")

    video_backend_drp.change(
        on_backend_change,
        inputs=[video_backend_drp, pm_state],
        outputs=[video_backend_drp, video_api_url_in, wan2gp_accordion, backend_switch_status],
    )

    def handle_save_settings(video_url, lm_url, backend, electricity_cost, system_wattage, gpu_monitor):
        settings = {
            "ltx_base_url": video_url,
            "lm_studio_url": lm_url,
            "video_backend": backend,
            "electricity_cost": electricity_cost,
            "system_wattage": system_wattage,
            "gpu_monitor_index": gpu_monitor,
        }
        status = config.save_global_url_settings(settings)
        return status, gr.update(choices=LLMBridge().get_models())

    save_settings_btn.click(
        handle_save_settings,
        inputs=[video_api_url_in, lm_url_in, video_backend_drp, electricity_cost_in, system_wattage_in, gpu_monitor_drp],
        outputs=[settings_status, llm_dropdown],
    )

    calibration_reset_btn.click(
        config.reset_render_calibration,
        outputs=[settings_status],
    ).then(
        config.get_calibration_summary,
        outputs=[calibration_stats_txt],
    )

    calibration_refresh_btn.click(
        config.get_calibration_summary,
        outputs=[calibration_stats_txt],
    )

    return {"video_backend_drp": video_backend_drp}
