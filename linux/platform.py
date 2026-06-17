import subprocess

import psutil


class LinuxSaveDialogHandler:
    def start(self):
        pass

    def stop(self):
        pass

    def handle_after_open(self, timeout: float = 5.0) -> bool:
        return False


class LinuxPlatformAdapter:
    name = "Linux"

    def is_ableton_running(self) -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"] or ""
                if "ableton live" in proc_name.lower() or proc_name.lower() == "live":
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def open_file(self, file_path: str):
        subprocess.run(["xdg-open", file_path], check=True)

    def create_save_dialog_handler(self):
        return LinuxSaveDialogHandler()
