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


DISCARD_DIALOG_GRACE_SECONDS = 4.0


DISCARD_DIALOG_SCRIPT = r'''
on hasSaveDialog(abletonProcess)
    tell application "System Events"
        tell abletonProcess
            repeat with candidateWindow in windows
                set roleName to ""
                set subroleName to ""
                set windowName to ""

                try
                    set roleName to role of candidateWindow as text
                end try
                try
                    set subroleName to subrole of candidateWindow as text
                end try
                try
                    set windowName to name of candidateWindow as text
                end try

                if roleName is "AXSheet" or roleName is "AXDialog" then return true
                if subroleName is "AXSheet" or subroleName is "AXDialog" then return true
                if windowName contains "Save" or windowName contains "save" then return true
            end repeat
        end tell
    end tell

    return false
end hasSaveDialog

on run
    tell application "System Events"
        set abletonProcesses to every process whose name is "Live" or name contains "Ableton Live"
        if (count of abletonProcesses) is 0 then return "no_live"

        set abletonProcess to item 1 of abletonProcesses
        if my hasSaveDialog(abletonProcess) is false then return "no_dialog"

        set frontmost of abletonProcess to true
        delay 0.15

        -- Ableton's custom prompt does not expose labeled buttons through
        -- Accessibility. From the default Save focus, left/left/return chooses
        -- the left "Don't Save" button.
        key code 123
        delay 0.05
        key code 123
        delay 0.05
        key code 36
        return "sent"
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
        return self.run_osascript(DISCARD_DIALOG_SCRIPT) == "sent"

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

    def handle_after_open(self, timeout: float = DISCARD_DIALOG_GRACE_SECONDS) -> bool:
        if self.reported_accessibility_error or timeout <= 0:
            return False

        # Ableton's custom prompt is not reliably inspectable, so spend one
        # short window sending the discard shortcut while it is likely to appear.
        attempt_interval_seconds = 0.35
        deadline = time.monotonic() + timeout
        sent = False
        while time.monotonic() <= deadline and not self.reported_accessibility_error:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(attempt_interval_seconds, remaining))
            if self.discard_save_dialog():
                sent = True
                print("Sent macOS save-dialog discard shortcut")

        return sent

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
