import os
import sys

# Compatibility shim: Pillow 10.0+ removed PIL.Image.ANTIALIAS (replaced by LANCZOS),
# but moviepy 1.x still references it internally during clip.resize().
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# ==========================================
# WINDOWS ASYNCIO PATCH (Fixes WinError 10054)
# ==========================================
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        def silence_event_loop_closed(func):
            def wrapper(self, *args, **kwargs):
                try:
                    return func(self, *args, **kwargs)
                except (RuntimeError, ConnectionResetError):
                    pass
            return wrapper
        _ProactorBasePipeTransport._call_connection_lost = silence_event_loop_closed(_ProactorBasePipeTransport._call_connection_lost)
    except ImportError:
        pass

import keyboard
from ui import build_app
from utils import restart_application

if __name__ == "__main__":
    app = build_app()
    try:
        keyboard.add_hotkey('ctrl+r', restart_application)
        print("⌨️  Hotkey Ctrl+R registered for restarting the application. (Ensure your terminal has focus to use)")
    except Exception as e:
        print(f"⚠️ Could not register hotkey 'ctrl+r'. Run script as admin or ensure 'keyboard' module is installed. Error: {e}")

    app.queue()
    app.launch(allowed_paths=[os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects")])
