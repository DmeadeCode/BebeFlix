"""
FFmpeg compression utility for BebeFlix.
Handles video compression with presets and progress reporting.
Uses QThread + Qt Signals for reliable cross-thread communication.
"""

import os
import re
import subprocess
import shutil
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QThread, Signal

from utils.paths import get_ffmpeg_path


@dataclass
class CompressionPreset:
    name: str
    description: str
    codec: str
    crf: Optional[int]
    audio_codec: str
    audio_bitrate: str
    extra_args: list

    def __str__(self):
        return f"{self.name} - {self.description}"


PRESETS = {
    "lossless": CompressionPreset(
        name="Lossless",
        description="Zero quality loss, re-encodes for optimal container (largest files)",
        codec="libx264", crf=0, audio_codec="flac", audio_bitrate="",
        extra_args=["-preset", "fast"]
    ),
    "high": CompressionPreset(
        name="High Quality",
        description="Visually identical to original, ~40-50% smaller",
        codec="libx264", crf=18, audio_codec="aac", audio_bitrate="192k",
        extra_args=["-preset", "veryfast"]
    ),
    "balanced": CompressionPreset(
        name="Balanced",
        description="Great quality, ~60-70% smaller",
        codec="libx264", crf=23, audio_codec="aac", audio_bitrate="128k",
        extra_args=["-preset", "veryfast"]
    ),
    "space_saver": CompressionPreset(
        name="Space Saver",
        description="Good quality, ~75-85% smaller",
        codec="libx264", crf=28, audio_codec="aac", audio_bitrate="96k",
        extra_args=["-preset", "ultrafast"]
    ),
    "copy": CompressionPreset(
        name="No Compression",
        description="Copy file as-is (fastest, no quality change)",
        codec="copy", crf=None, audio_codec="copy", audio_bitrate="",
        extra_args=[]
    ),
}

PRESET_ORDER = ["copy", "lossless", "high", "balanced", "space_saver"]


def _detect_gpu_encoder() -> Optional[str]:
    """Check if NVENC (NVIDIA) or QSV (Intel) hardware encoding is available."""
    ffmpeg = get_ffmpeg_path()
    try:
        result = subprocess.run(
            [ffmpeg, "-encoders"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        output = result.stdout
        # Prefer NVENC (NVIDIA), then QSV (Intel)
        if "h264_nvenc" in output:
            return "h264_nvenc"
        if "h264_qsv" in output:
            return "h264_qsv"
    except Exception:
        pass
    return None


def _build_gpu_cmd(encoder: str, crf_equivalent: Optional[int],
                   audio_codec: str, audio_bitrate: str) -> list:
    """Build FFmpeg args for GPU-accelerated encoding."""
    cmd_parts = ["-c:v", encoder]
    if encoder == "h264_nvenc":
        # NVENC uses -cq for constant quality (similar to CRF)
        if crf_equivalent is not None and crf_equivalent > 0:
            cmd_parts.extend(["-rc", "constqp", "-qp", str(crf_equivalent)])
        elif crf_equivalent == 0:
            cmd_parts.extend(["-rc", "lossless"])
        cmd_parts.extend(["-preset", "p4"])  # balanced speed/quality
    elif encoder == "h264_qsv":
        if crf_equivalent is not None and crf_equivalent > 0:
            cmd_parts.extend(["-global_quality", str(crf_equivalent)])
        cmd_parts.extend(["-preset", "faster"])
    cmd_parts.extend(["-c:a", audio_codec])
    if audio_bitrate:
        cmd_parts.extend(["-b:a", audio_bitrate])
    return cmd_parts


def get_video_duration(input_path: str) -> Optional[float]:
    ffmpeg = get_ffmpeg_path()
    try:
        result = subprocess.run(
            [ffmpeg, "-i", input_path],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", result.stderr)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), float(match.group(3))
            return h * 3600 + m * 60 + s
    except Exception:
        pass
    return None


def get_embedded_subtitles(input_path: str) -> list:
    ffmpeg = get_ffmpeg_path()
    try:
        result = subprocess.run(
            [ffmpeg, "-i", input_path],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        subtitles = []
        pattern = re.compile(
            r"Stream #\d+:(\d+)(?:\((\w+)\))?: Subtitle: (\w+)"
        )
        for match in pattern.finditer(result.stderr):
            track_idx = int(match.group(1))
            lang = match.group(2) or "Unknown"
            codec = match.group(3)
            label = f"{lang.upper()} ({codec})"
            subtitles.append({
                "track_index": track_idx,
                "label": label,
                "is_embedded": True,
                "sub_path": ""
            })
        return subtitles
    except Exception:
        return []


class CompressionThread(QThread):
    """Background thread for video compression with Qt signal-based progress."""
    progress = Signal(float)
    finished_signal = Signal(bool, str)

    def __init__(self, input_path, output_path, preset, parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.preset = preset
        self._cancelled = False
        self._process = None
        self._stderr_file = None

    def run(self):
        preset = self.preset

        # Handle simple copy mode
        if preset.codec == "copy":
            try:
                self.progress.emit(0.0)
                shutil.copy2(self.input_path, self.output_path)
                self.progress.emit(100.0)
                self.finished_signal.emit(True, "File copied successfully.")
            except Exception as e:
                self.finished_signal.emit(False, str(e))
            return

        ffmpeg = get_ffmpeg_path()
        duration = get_video_duration(self.input_path)

        # Try GPU-accelerated encoding first
        gpu_encoder = _detect_gpu_encoder()

        if gpu_encoder and preset.crf is not None:
            cmd = [ffmpeg, "-i", self.input_path, "-y"]
            cmd.extend(_build_gpu_cmd(
                gpu_encoder, preset.crf,
                preset.audio_codec, preset.audio_bitrate
            ))
            cmd.extend(["-progress", "pipe:1", "-nostats"])
            cmd.append(self.output_path)
        else:
            # CPU fallback
            cmd = [ffmpeg, "-i", self.input_path, "-y"]
            cmd.extend(["-c:v", preset.codec])
            if preset.crf is not None:
                cmd.extend(["-crf", str(preset.crf)])
            cmd.extend(preset.extra_args)
            cmd.extend(["-c:a", preset.audio_codec])
            if preset.audio_bitrate:
                cmd.extend(["-b:a", preset.audio_bitrate])
            cmd.extend(["-progress", "pipe:1", "-nostats"])
            cmd.append(self.output_path)

        try:
            creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

            # Write stderr to temp file to avoid pipe deadlock
            # (reading stdout for progress while stderr fills its buffer = freeze)
            import tempfile
            self._stderr_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.log', delete=False, prefix='bebeflix_'
            )

            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=self._stderr_file,
                text=True, creationflags=creation_flags
            )

            for line in self._process.stdout:
                if self._cancelled:
                    self._process.terminate()
                    self._cleanup()
                    self.finished_signal.emit(False, "Compression cancelled.")
                    return

                if line.startswith("out_time_ms="):
                    try:
                        time_us = int(line.split("=")[1].strip())
                        current_seconds = time_us / 1_000_000
                        if duration and duration > 0:
                            percent = min((current_seconds / duration) * 100, 99.9)
                            self.progress.emit(percent)
                    except (ValueError, ZeroDivisionError):
                        pass

            self._process.wait()

            if self._process.returncode == 0:
                self.progress.emit(100.0)
                self.finished_signal.emit(True, "Compression complete.")
            else:
                # Read the actual error from the temp log file
                stderr = ""
                try:
                    self._stderr_file.close()
                    with open(self._stderr_file.name, 'r') as f:
                        stderr = f.read()
                except Exception:
                    pass
                self._cleanup()
                error_msg = stderr.strip().split('\n')
                last_lines = '\n'.join(error_msg[-10:])
                self.finished_signal.emit(False, f"FFmpeg error:\n{last_lines[-500:]}")

        except FileNotFoundError:
            self.finished_signal.emit(False, "FFmpeg not found. Please ensure FFmpeg is available.")
        except Exception as e:
            self._cleanup()
            self.finished_signal.emit(False, f"Error: {str(e)}")
        finally:
            self._process = None
            # Clean up temp log file
            if self._stderr_file:
                try:
                    self._stderr_file.close()
                except Exception:
                    pass
                try:
                    os.remove(self._stderr_file.name)
                except Exception:
                    pass

    def cancel(self):
        self._cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def _cleanup(self):
        try:
            if os.path.exists(self.output_path):
                os.remove(self.output_path)
        except Exception:
            pass
