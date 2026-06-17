#!/usr/bin/env python3
"""
Ableton save prompt handler for macOS.

After the server asks macOS to open another .als file, Ableton may prompt to
save the current set. Ableton does not consistently expose that prompt through
Accessibility, so this focuses Live and uses keyboard navigation to choose
"Don't Save".
"""

import subprocess
import time


DISCARD_AFTER_OPEN_DELAY = 0.25


DISCARD_DIALOG_SCRIPT = r'''
on run
    tell application "System Events"
        set abletonProcesses to every process whose name is "Live" or name contains "Ableton Live"
        if (count of abletonProcesses) is 0 then return ""

        set frontmost of item 1 of abletonProcesses to true
        delay 0.15

        -- Ableton's custom prompt does not expose labeled buttons through
        -- Accessibility. From the default Save focus, left/left/return chooses
        -- the left "Don't Save" button.
        key code 123
        delay 0.05
        key code 123
        delay 0.05
        key code 36
    end tell
end run
'''


class AbletonSaveDialogHandler:
    def __init__(self):
        self.reported_accessibility_error = False

    def start(self):
        print("macOS save dialog handler ready")

    def stop(self):
        pass

    def discard_save_dialog(self) -> bool:
        return self.run_osascript(DISCARD_DIALOG_SCRIPT) is not None

    def run_osascript(self, script):
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            self.report_automation_error(str(e))
            return None

        if result.returncode != 0:
            self.report_automation_error(result.stderr.strip())
            return None

        return result.stdout.strip()

    def handle_after_open(self, timeout: float = 5.0) -> bool:
        if self.reported_accessibility_error or timeout <= 0:
            return False

        time.sleep(min(DISCARD_AFTER_OPEN_DELAY, timeout))
        if not self.discard_save_dialog():
            return False

        print("Sent macOS save-dialog discard shortcut")
        return True

    def report_automation_error(self, message: str):
        if self.reported_accessibility_error:
            return

        self.reported_accessibility_error = True
        print("Unable to automate Ableton's save dialog on macOS.")
        if message:
            print(message)
        print(
            "Grant Accessibility permission to the app running this server "
            "in System Settings > Privacy & Security > Accessibility."
        )
