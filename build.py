"""
BebeFlix Build Script
Produces a fully self-contained executable with VLC + FFmpeg bundled.

Usage:
    python build.py              Build for current platform
    python build.py --check      Just verify dependencies exist
"""

import os
import sys
import glob
import shutil
import platform
import subprocess
import argparse


# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────

APP_NAME = "BebeFlix"
MAIN_SCRIPT = "main.py"

def get_platform_suffix():
    if sys.platform == "win32":
        return "Win"
    elif sys.platform == "darwin":
        return "Mac"
    return "Linux"

DIST_FOLDER = f"{APP_NAME}-{get_platform_suffix()}"
DIST_DIR = os.path.join("dist", DIST_FOLDER)

# Common VLC install locations
VLC_SEARCH_WIN = [
    os.path.expandvars(r"%ProgramFiles%\VideoLAN\VLC"),
    os.path.expandvars(r"%ProgramFiles(x86)%\VideoLAN\VLC"),
    r"C:\Program Files\VideoLAN\VLC",
]
VLC_SEARCH_MAC = [
    "/Applications/VLC.app/Contents/MacOS",
]


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def find_vlc_dir() -> str:
    """Locate VLC installation directory."""
    search = VLC_SEARCH_WIN if sys.platform == "win32" else VLC_SEARCH_MAC
    for path in search:
        if os.path.isdir(path):
            # Verify it actually has the core library
            if sys.platform == "win32":
                if os.path.isfile(os.path.join(path, "libvlc.dll")):
                    return path
            else:
                lib_dir = os.path.join(path, "lib")
                if os.path.isdir(lib_dir):
                    return path
                # Also check if libvlc is directly here
                for f in os.listdir(path):
                    if "libvlc" in f:
                        return path
    return ""


def find_ffmpeg() -> str:
    """Locate FFmpeg binary."""
    # Check bundled location first
    if sys.platform == "win32":
        local = os.path.join("ffmpeg", "ffmpeg.exe")
    else:
        local = os.path.join("ffmpeg", "ffmpeg")
    if os.path.isfile(local):
        return os.path.abspath(local)

    # Check system PATH
    cmd = "where" if sys.platform == "win32" else "which"
    try:
        result = subprocess.run([cmd, "ffmpeg"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return ""


def copy_vlc_windows(vlc_dir: str, dest: str):
    """Copy VLC libraries to build output (Windows)."""
    vlc_dest = os.path.join(dest, "vlc")
    os.makedirs(vlc_dest, exist_ok=True)

    # Core DLLs
    for dll in ["libvlc.dll", "libvlccore.dll"]:
        src = os.path.join(vlc_dir, dll)
        if os.path.isfile(src):
            shutil.copy2(src, vlc_dest)
            print(f"  Copied {dll}")

    # Plugins folder (required)
    plugins_src = os.path.join(vlc_dir, "plugins")
    plugins_dest = os.path.join(vlc_dest, "plugins")
    if os.path.isdir(plugins_src):
        if os.path.isdir(plugins_dest):
            shutil.rmtree(plugins_dest)
        shutil.copytree(plugins_src, plugins_dest)
        plugin_count = sum(1 for _ in glob.glob(os.path.join(plugins_dest, "**", "*.dll"), recursive=True))
        print(f"  Copied plugins/ ({plugin_count} DLLs)")


def copy_vlc_mac(vlc_dir: str, dest: str):
    """Copy VLC libraries to build output (macOS)."""
    vlc_dest = os.path.join(dest, "vlc")
    os.makedirs(vlc_dest, exist_ok=True)

    # Copy dylibs from lib/
    lib_dir = os.path.join(vlc_dir, "lib")
    if os.path.isdir(lib_dir):
        for f in os.listdir(lib_dir):
            if f.endswith(".dylib") and "vlc" in f.lower():
                shutil.copy2(os.path.join(lib_dir, f), vlc_dest)
                print(f"  Copied {f}")

    # Plugins
    plugins_src = os.path.join(vlc_dir, "plugins")
    if not os.path.isdir(plugins_src):
        plugins_src = os.path.join(lib_dir, "vlc", "plugins")
    plugins_dest = os.path.join(vlc_dest, "plugins")
    if os.path.isdir(plugins_src):
        if os.path.isdir(plugins_dest):
            shutil.rmtree(plugins_dest)
        shutil.copytree(plugins_src, plugins_dest)
        print(f"  Copied plugins/")


def copy_ffmpeg(ffmpeg_path: str, dest: str):
    """Copy FFmpeg binary to build output."""
    ffmpeg_dest = os.path.join(dest, "ffmpeg")
    os.makedirs(ffmpeg_dest, exist_ok=True)

    out_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    out_path = os.path.join(ffmpeg_dest, out_name)
    shutil.copy2(ffmpeg_path, out_path)

    # Make executable on Unix
    if sys.platform != "win32":
        os.chmod(out_path, 0o755)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"  Copied ffmpeg ({size_mb:.1f} MB)")


# ──────────────────────────────────────────────────────────────
# Dependency Check
# ──────────────────────────────────────────────────────────────

def check_deps():
    """Verify all build dependencies exist."""
    print(f"\n{'='*60}")
    print(f"  BebeFlix Dependency Check — {platform.system()} {platform.machine()}")
    print(f"{'='*60}\n")

    ok = True

    # Python
    print(f"  Python:     {sys.version.split()[0]}  ✓")

    # PySide6
    try:
        import PySide6
        print(f"  PySide6:    {PySide6.__version__}  ✓")
    except ImportError:
        print(f"  PySide6:    NOT FOUND  ✗  →  pip install PySide6")
        ok = False

    # python-vlc
    try:
        import vlc
        print(f"  python-vlc: {vlc.__version__ if hasattr(vlc, '__version__') else 'installed'}  ✓")
    except ImportError:
        print(f"  python-vlc: NOT FOUND  ✗  →  pip install python-vlc")
        ok = False

    # PyInstaller
    try:
        import PyInstaller
        print(f"  PyInstaller: {PyInstaller.__version__}  ✓")
    except ImportError:
        print(f"  PyInstaller: NOT FOUND  ✗  →  pip install pyinstaller")
        ok = False

    # VLC binaries
    vlc_dir = find_vlc_dir()
    if vlc_dir:
        print(f"  VLC libs:   {vlc_dir}  ✓")
    else:
        print(f"  VLC libs:   NOT FOUND  ✗")
        if sys.platform == "win32":
            print(f"              → Install VLC 64-bit from https://www.videolan.org")
        else:
            print(f"              → Install VLC from https://www.videolan.org")
        ok = False

    # FFmpeg
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        print(f"  FFmpeg:     {ffmpeg}  ✓")
    else:
        print(f"  FFmpeg:     NOT FOUND  ✗")
        if sys.platform == "win32":
            print(f"              → Download from https://www.gyan.dev/ffmpeg/builds/")
            print(f"              → Place ffmpeg.exe in ./ffmpeg/ folder")
        else:
            print(f"              → brew install ffmpeg  (or download static build)")
        ok = False

    print()
    if ok:
        print("  All dependencies found! Ready to build.\n")
    else:
        print("  Some dependencies are missing. Install them and try again.\n")

    return ok


# ──────────────────────────────────────────────────────────────
# Build
# ──────────────────────────────────────────────────────────────

def build():
    print(f"\n{'='*60}")
    print(f"  Building {APP_NAME} for {platform.system()} ({platform.machine()})")
    print(f"{'='*60}\n")

    # Verify deps
    vlc_dir = find_vlc_dir()
    ffmpeg_path = find_ffmpeg()

    if not vlc_dir:
        print("ERROR: VLC not found. Run 'python build.py --check' for details.")
        sys.exit(1)

    if not ffmpeg_path:
        print("WARNING: FFmpeg not found. Compression features will be unavailable.")
        print("         Continue anyway? (y/n) ", end="")
        if input().strip().lower() != "y":
            sys.exit(1)

    # Step 1: Run PyInstaller
    print("\n[1/3] Running PyInstaller...\n")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--hidden-import", "vlc",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
    ]

    # Bundle resources folder if it exists and has content
    if os.path.isdir("resources") and os.listdir("resources"):
        sep = ";" if sys.platform == "win32" else ":"
        cmd.extend(["--add-data", f"resources{sep}resources"])

    if sys.platform == "darwin":
        cmd.extend(["--osx-bundle-identifier", "com.bebeflix.app"])

    cmd.append(MAIN_SCRIPT)

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nPyInstaller failed with exit code {result.returncode}")
        sys.exit(1)

    # Determine actual output directory
    pyinstaller_out = os.path.join("dist", APP_NAME)
    if sys.platform == "darwin" and os.path.isdir(os.path.join("dist", f"{APP_NAME}.app")):
        dist_inner = os.path.join("dist", f"{APP_NAME}.app", "Contents", "MacOS")
    else:
        dist_inner = pyinstaller_out

    if not os.path.isdir(dist_inner):
        print(f"\nERROR: Expected output dir not found: {dist_inner}")
        sys.exit(1)

    # Step 2: Bundle VLC
    print("\n[2/3] Bundling VLC libraries...")
    if sys.platform == "win32":
        copy_vlc_windows(vlc_dir, dist_inner)
    else:
        copy_vlc_mac(vlc_dir, dist_inner)

    # Step 3: Bundle FFmpeg
    print("\n[3/3] Bundling FFmpeg...")
    if ffmpeg_path:
        copy_ffmpeg(ffmpeg_path, dist_inner)
    else:
        print("  Skipped (not found)")

    # Rename output folder to platform-specific name
    final_dir = DIST_DIR
    if sys.platform != "darwin" and os.path.isdir(pyinstaller_out):
        if os.path.isdir(final_dir):
            shutil.rmtree(final_dir)
        os.rename(pyinstaller_out, final_dir)
    elif sys.platform == "darwin":
        mac_app = os.path.join("dist", f"{APP_NAME}.app")
        mac_final = os.path.join("dist", f"{APP_NAME}-Mac.app")
        if os.path.isdir(mac_app):
            if os.path.isdir(mac_final):
                shutil.rmtree(mac_final)
            os.rename(mac_app, mac_final)
            final_dir = mac_final

    # Summary
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(final_dir):
        for f in filenames:
            total_size += os.path.getsize(os.path.join(dirpath, f))

    print(f"\n{'='*60}")
    print(f"  BUILD SUCCESSFUL!")
    print(f"")
    if sys.platform == "win32":
        print(f"  Output:  dist/{DIST_FOLDER}/{APP_NAME}.exe")
    elif sys.platform == "darwin":
        print(f"  Output:  dist/{APP_NAME}-Mac.app")
    else:
        print(f"  Output:  dist/{DIST_FOLDER}/{APP_NAME}")
    print(f"  Size:    {total_size / (1024*1024):.1f} MB total")
    print(f"")
    print(f"  USB Drive Layout:")
    print(f"  ┌─────────────────────────────────────────┐")
    print(f"  │  ExFAT USB Drive/                       │")
    print(f"  │  ├── BebeFlix-Win/   ← Windows build    │")
    print(f"  │  ├── BebeFlix-Mac/   ← macOS build      │")
    print(f"  │  ├── library/        ← SHARED database  │")
    print(f"  │  │   ├── catalog.db                     │")
    print(f"  │  │   └── movies/                        │")
    print(f"  │  └── ffmpeg/         ← (optional)       │")
    print(f"  └─────────────────────────────────────────┘")
    print(f"")
    print(f"  Both platforms share the same library/ folder.")
    print(f"  Format the USB drive as ExFAT for cross-platform.")
    print(f"{'='*60}\n")


# ──────────────────────────────────────────────────────────────
# Entry
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME}")
    parser.add_argument("--check", action="store_true", help="Check dependencies only")
    args = parser.parse_args()

    if args.check:
        check_deps()
    else:
        build()
