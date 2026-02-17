"""
BebeFlix - Portable Movie Player
Main entry point.
"""

import sys
import os

# Ensure our package is importable
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# --- VLC setup for bundled builds ---
# Must happen BEFORE importing vlc module
if getattr(sys, 'frozen', False):
    if sys.platform == "win32":
        vlc_dir = os.path.join(app_dir, "vlc")
        if os.path.isdir(vlc_dir):
            os.environ["VLC_PLUGIN_PATH"] = os.path.join(vlc_dir, "plugins")
            os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(vlc_dir)
            except (AttributeError, OSError):
                pass
    elif sys.platform == "darwin":
        vlc_dir = os.path.join(app_dir, "vlc")
        if os.path.isdir(vlc_dir):
            os.environ["VLC_PLUGIN_PATH"] = os.path.join(vlc_dir, "plugins")
            os.environ["DYLD_LIBRARY_PATH"] = vlc_dir + os.pathsep + os.environ.get("DYLD_LIBRARY_PATH", "")

# Fix DLL loading on Windows
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.kernel32.SetDllDirectoryW(None)
    except Exception:
        pass


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("BebeFlix")
    app.setOrganizationName("BebeFlix")

    from ui.styles import LIGHT_THEME
    app.setStyleSheet(LIGHT_THEME)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
