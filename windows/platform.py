import os

import psutil

from .save_dialog_handler import AbletonSaveDialogHandler


class WindowsPlatformAdapter:
    name = "Windows"

    def is_ableton_running(self) -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"] or ""
                if "ableton live" in proc_name.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def open_file(self, file_path: str):
        os.startfile(file_path)

    def create_save_dialog_handler(self):
        return AbletonSaveDialogHandler()
