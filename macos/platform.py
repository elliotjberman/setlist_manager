import subprocess

import psutil

from .save_dialog_handler import AbletonSaveDialogHandler


class MacOSPlatformAdapter:
    name = "macOS"

    def is_ableton_running(self) -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"] or ""
                proc_name = proc_name.lower()
                if proc_name == "live" or "ableton live" in proc_name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def open_file(self, file_path: str):
        subprocess.run(["open", file_path], check=True)

    def create_save_dialog_handler(self):
        return AbletonSaveDialogHandler()
