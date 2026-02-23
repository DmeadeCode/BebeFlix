"""
Path utilities for BebeFlix portable operation.
All paths are resolved relative to the drive root so the app
works regardless of which drive letter/mount point is used.
"""

import os
import sys


def normalize_path(rel_path: str) -> str:
    """Convert Windows backslashes to forward slashes for cross-platform."""
    return rel_path.replace("\\", "/") if rel_path else rel_path


def get_app_root() -> str:
    """Get the directory containing the executable or source."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_drive_root() -> str:
    """
    Get the shared drive root for cross-platform library storage.
    Windows: exe is at E:\\BebeFlix-Win\\BebeFlix.exe -> drive root is 1 up
    macOS:   exe is at /Volumes/X/BebeFlix.app/Contents/MacOS/BebeFlix -> 3 up from app_root
    Source:  same as app root.
    """
    if getattr(sys, 'frozen', False):
        app_root = get_app_root()
        if sys.platform == "darwin":
            # app_root = .../BebeFlix.app/Contents/MacOS
            # drive root = 3 levels up (MacOS -> Contents -> BebeFlix.app -> drive)
            return os.path.dirname(os.path.dirname(os.path.dirname(app_root)))
        else:
            # Windows: app_root = .../BebeFlix-Win
            return os.path.dirname(app_root)
    else:
        return get_app_root()


def get_library_root() -> str:
    path = os.path.join(get_drive_root(), "library")
    os.makedirs(path, exist_ok=True)
    return path


def get_movies_dir() -> str:
    path = os.path.join(get_library_root(), "movies")
    os.makedirs(path, exist_ok=True)
    return path


def get_db_path() -> str:
    return os.path.join(get_library_root(), "catalog.db")


def get_ffmpeg_path() -> str:
    root = get_app_root()
    if sys.platform == "win32":
        path = os.path.join(root, "ffmpeg", "ffmpeg.exe")
    else:
        path = os.path.join(root, "ffmpeg", "ffmpeg")

    if os.path.exists(path):
        return path
    return "ffmpeg"


def get_resource_path(filename: str) -> str:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "resources", filename)


def make_movie_dir(slug: str) -> str:
    path = os.path.join(get_movies_dir(), slug)
    os.makedirs(path, exist_ok=True)
    return path


def slugify(title: str) -> str:
    import re
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = slug.strip('-')
    return slug or "untitled"


def get_drive_free_space() -> int:
    import shutil
    usage = shutil.disk_usage(get_drive_root())
    return usage.free


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
