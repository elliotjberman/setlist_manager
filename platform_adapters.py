import sys


class NoOpSaveDialogHandler:
    def start(self):
        pass

    def stop(self):
        pass

    def handle_after_open(self, timeout: float = 5.0) -> bool:
        return False


class UnsupportedPlatformAdapter:
    name = sys.platform

    def is_ableton_running(self) -> bool:
        return False

    def open_file(self, file_path: str):
        raise RuntimeError(f"No Ableton set opener configured for platform: {sys.platform}")

    def create_save_dialog_handler(self):
        return NoOpSaveDialogHandler()


def get_platform_adapter():
    if sys.platform.startswith("win"):
        from windows.platform import WindowsPlatformAdapter

        return WindowsPlatformAdapter()

    if sys.platform == "darwin":
        from macos.platform import MacOSPlatformAdapter

        return MacOSPlatformAdapter()

    if sys.platform.startswith("linux"):
        from linux.platform import LinuxPlatformAdapter

        return LinuxPlatformAdapter()

    return UnsupportedPlatformAdapter()
