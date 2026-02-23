"""
Prevent the OS from sleeping/dimming the screen during video playback.
macOS:   Spawns `caffeinate -d` (display sleep prevention)
Windows: Calls SetThreadExecutionState to prevent display sleep
"""

import sys
import subprocess


class SleepInhibitor:
    """Context-managed or manual sleep prevention."""

    def __init__(self):
        self._active = False
        self._process = None  # macOS caffeinate process

    def inhibit(self):
        """Prevent display sleep."""
        if self._active:
            return

        if sys.platform == "darwin":
            try:
                # -d = prevent display sleep, -i = prevent idle sleep
                self._process = subprocess.Popen(
                    ["caffeinate", "-d", "-i"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._active = True
            except (FileNotFoundError, OSError):
                pass

        elif sys.platform == "win32":
            try:
                import ctypes
                # ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
                ES_CONTINUOUS = 0x80000000
                ES_DISPLAY_REQUIRED = 0x00000002
                ES_SYSTEM_REQUIRED = 0x00000001
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
                )
                self._active = True
            except Exception:
                pass

    def release(self):
        """Allow display sleep again."""
        if not self._active:
            return

        if sys.platform == "darwin":
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=2)
                except Exception:
                    pass
                self._process = None

        elif sys.platform == "win32":
            try:
                import ctypes
                ES_CONTINUOUS = 0x80000000
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except Exception:
                pass

        self._active = False

    @property
    def is_active(self):
        return self._active
