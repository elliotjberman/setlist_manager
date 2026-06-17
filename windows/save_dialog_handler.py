#!/usr/bin/env python3
"""
Ableton Save Dialog Auto-Handler for Windows.
Automatically dismisses Ableton's save prompt by pressing Right Arrow + Enter.
"""

import threading
import time
from typing import Optional

import psutil
import win32api
import win32con
import win32gui


SAVE_DIALOG_STYLE = -1765277696


class AbletonSaveDialogHandler:
    def __init__(self, check_interval: float = 0.1):
        self.check_interval = check_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def is_ableton_running(self) -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"] or ""
                if "ableton" in proc_name.lower() or "live" in proc_name.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def handle_save_dialog(self) -> bool:
        """
        Look for Ableton's save dialog and dismiss it.
        Uses specific detection criteria based on observed Ableton window metadata.
        """
        try:
            def enum_windows_callback(hwnd, dialogs):
                if not win32gui.IsWindowVisible(hwnd):
                    return

                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name != "Ableton Live Window Class":
                        return

                    window_text = win32gui.GetWindowText(hwnd)
                    parent = win32gui.GetParent(hwnd)
                    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                    has_popup_style = bool(style & win32con.WS_POPUP)
                    has_empty_text = window_text == ""
                    has_parent = parent is not None
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]

                    if not has_parent or not parent or not win32gui.IsWindow(parent):
                        return

                    parent_text = win32gui.GetWindowText(parent)
                    parent_class = win32gui.GetClassName(parent)
                    parent_is_ableton = (
                        parent_class == "Ableton Live Window Class"
                        and "ableton live" in parent_text.lower()
                    )

                    if (
                        has_popup_style
                        and has_empty_text
                        and parent_is_ableton
                        and style == SAVE_DIALOG_STYLE
                    ):
                        print(
                            "Found save dialog: "
                            f"{hwnd}, Text: '{window_text}', Class: {class_name}, "
                            f"Parent: {parent}, Style: {style}, Width: {width}"
                        )
                        dialogs.append(hwnd)
                except Exception:
                    pass

            save_dialogs = []
            win32gui.EnumWindows(enum_windows_callback, save_dialogs)

            for hwnd in save_dialogs:
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.1)
                    win32api.keybd_event(win32con.VK_RIGHT, 0, 0, 0)
                    win32api.keybd_event(win32con.VK_RIGHT, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                    win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
                    return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def handle_after_open(self, timeout: float = 5.0) -> bool:
        return self.handle_save_dialog()

    def monitor_loop(self):
        print("Windows save dialog handler started")

        while self.running:
            try:
                if self.is_ableton_running():
                    self.handle_save_dialog()

                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(1)

    def start(self):
        if self.running:
            print("Handler already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        print("Windows save dialog handler started in background")

    def stop(self):
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        print("Windows save dialog handler stopped")


def main():
    handler = AbletonSaveDialogHandler()

    try:
        print("Starting Ableton Save Dialog Handler...")
        print("Press Ctrl+C to stop")
        handler.start()

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping handler...")
        handler.stop()


if __name__ == "__main__":
    main()
