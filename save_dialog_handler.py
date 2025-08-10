#!/usr/bin/env python3
"""
Ableton Save Dialog Auto-Handler
Automatically dismisses Ableton's "do you want to save" dialog by pressing Right Arrow + Enter
"""

SAVE_DIALOG_STYLE = -1765277696

import time
import threading
import psutil
import pyautogui
from typing import Optional

import win32gui
import win32api
import win32con

class AbletonSaveDialogHandler:
    def __init__(self, check_interval: float = 0.1):
        self.check_interval = check_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Configure pyautogui
        pyautogui.FAILSAFE = True  # Move mouse to top-left to abort
        pyautogui.PAUSE = 0.01  # Small delay between actions
    
    def is_ableton_running(self) -> bool:
        """Check if any Ableton Live process is running"""
        for proc in psutil.process_iter(['name']):
            try:
                if 'ableton' in proc.info['name'].lower() or 'live' in proc.info['name'].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def handle_save_dialog(self) -> bool:
        """
        Look for Ableton save dialog and dismiss it
        Uses very specific detection criteria based on window analysis
        Returns True if dialog was found and handled
        """
        try:
            def enum_windows_callback(hwnd, dialogs):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        class_name = win32gui.GetClassName(hwnd)
                        if class_name == 'Ableton Live Window Class':
                            window_text = win32gui.GetWindowText(hwnd)
                            parent = win32gui.GetParent(hwnd)
                            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                            has_popup_style = bool(style & win32con.WS_POPUP)
                            has_empty_text = window_text == ''
                            has_parent = parent is not None
                            rect = win32gui.GetWindowRect(hwnd)
                            width = rect[2] - rect[0]
                            if has_parent:
                                try:
                                    if parent and win32gui.IsWindow(parent):
                                        parent_text = win32gui.GetWindowText(parent)
                                        parent_class = win32gui.GetClassName(parent)
                                        parent_is_ableton = (parent_class == 'Ableton Live Window Class' and 'ableton live' in parent_text.lower())
                                        # Fuck Windows, the only reliable way to target the save dialog and not accidentally click the session window
                                        # is by matching the style value. Size and other properties are not unique enough.
                                        if has_popup_style and has_empty_text and parent_is_ableton and style == SAVE_DIALOG_STYLE:
                                            print(f"Found save dialog: {hwnd}, Text: '{window_text}', Class: {class_name}, Parent: {parent}, Style: {style}, Width: {width}")
                                            dialogs.append(hwnd)
                                except Exception:
                                    pass
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
        except ImportError:
            pass
        except Exception:
            pass
        return False
    
    def monitor_loop(self):
        """Main monitoring loop"""
        print("Save dialog handler started")
        
        while self.running:
            try:
                if self.is_ableton_running():
                    self.handle_save_dialog()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(1)  # Wait longer on error
    
    def start(self):
        """Start the save dialog handler in a background thread"""
        if self.running:
            print("Handler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        print("Save dialog handler started in background")
    
    def stop(self):
        """Stop the save dialog handler"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        print("Save dialog handler stopped")


def main():
    """Standalone mode - run the handler continuously"""
    handler = AbletonSaveDialogHandler()
    
    try:
        print("Starting Ableton Save Dialog Handler...")
        print("Press Ctrl+C to stop")
        handler.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping handler...")
        handler.stop()


if __name__ == "__main__":
    main()