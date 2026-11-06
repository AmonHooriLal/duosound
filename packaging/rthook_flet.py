"""PyInstaller runtime hook (Windows): lets the Flet client talk to the bundled app and gives the client window the DuoSound.exe
taskbar identity (a trimmed copy of flet-cli's own hook, so building does not need flet-cli)."""
import os
import sys

os.environ["FLET_SERVER_IP"] = "127.0.0.1"
if sys.platform == "win32" and "FLET_APP_USER_MODEL_ID" not in os.environ:
    exe_path = os.path.abspath(sys.executable)
    os.environ["FLET_APP_USER_MODEL_ID"] = exe_path
    os.environ.setdefault("FLET_APP_RELAUNCH_COMMAND", f'"{exe_path}"')
    os.environ.setdefault("FLET_APP_RELAUNCH_DISPLAY_NAME", os.path.splitext(os.path.basename(exe_path))[0])
    os.environ.setdefault("FLET_APP_RELAUNCH_ICON", f"{exe_path},0")
