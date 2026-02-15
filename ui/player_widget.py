"""
Video player widget for BebeFlix.
"""

import os
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QSlider, QComboBox, QFrame,
                                QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer, Slot
from PySide6.QtGui import QKeySequence, QShortcut

from database import Movie, Database
from utils.paths import get_library_root

try:
    import vlc
    VLC_AVAILABLE = True
except (ImportError, OSError):
    VLC_AVAILABLE = False


def format_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


class PlayerWidget(QWidget):
    back_requested = Signal()
    SPEED_OPTIONS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
    SKIP_SECONDS = 10

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.movie: Movie = None
        self._vlc_instance = None
        self._media_player = None
        self._media = None
        self._is_playing = False
        self._is_fullscreen = False
        self._duration = 0
        self._seeking = False
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(16, 10, 16, 10)

        self.back_btn = QPushButton("\u2190  Library")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setFixedWidth(100)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #D81B60; border: 2px solid #F8BBD0;
                border-radius: 16px; padding: 6px 14px; font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background-color: #FCE4EC; border-color: #EC407A; }
        """)
        self.back_btn.clicked.connect(self._on_back)
        top_bar.addWidget(self.back_btn)

        self.movie_title_label = QLabel("")
        self.movie_title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #C2185B; padding-left: 12px;")
        top_bar.addWidget(self.movie_title_label)
        top_bar.addStretch()

        self.fullscreen_btn = QPushButton("\u26F6  Fullscreen")
        self.fullscreen_btn.setCursor(Qt.PointingHandCursor)
        self.fullscreen_btn.setFixedWidth(120)
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #D81B60; border: 2px solid #F8BBD0;
                border-radius: 16px; padding: 6px 14px; font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background-color: #FCE4EC; border-color: #EC407A; }
        """)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        top_bar.addWidget(self.fullscreen_btn)

        top_widget = QWidget()
        top_widget.setLayout(top_bar)
        top_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFF0F5, stop:1 #FCE4EC);
                border-bottom: 2px solid #F8BBD0;
            }
        """)
        layout.addWidget(top_widget)

        # Video frame (black)
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_frame.mouseDoubleClickEvent = lambda e: self.toggle_fullscreen()
        layout.addWidget(self.video_frame)

        # Controls panel
        controls_widget = QWidget()
        controls_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #FFF5F8);
                border-top: 2px solid #F8BBD0;
            }
        """)
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(16, 10, 16, 14)
        controls_layout.setSpacing(10)

        # Seek row
        seek_row = QHBoxLayout()
        seek_row.setSpacing(10)

        self.time_current = QLabel("0:00")
        self.time_current.setFixedWidth(60)
        self.time_current.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_current.setStyleSheet("font-size: 12px; color: #757575; font-weight: 500;")
        seek_row.addWidget(self.time_current)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderPressed.connect(self._on_seek_start)
        self.seek_slider.sliderReleased.connect(self._on_seek_end)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        seek_row.addWidget(self.seek_slider)

        self.time_total = QLabel("0:00")
        self.time_total.setFixedWidth(60)
        self.time_total.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.time_total.setStyleSheet("font-size: 12px; color: #757575; font-weight: 500;")
        seek_row.addWidget(self.time_total)
        controls_layout.addLayout(seek_row)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.skip_back_btn = QPushButton(f"\u23EA {self.SKIP_SECONDS}s")
        self.skip_back_btn.setCursor(Qt.PointingHandCursor)
        self.skip_back_btn.setFixedWidth(70)
        self.skip_back_btn.clicked.connect(self.skip_backward)
        btn_row.addWidget(self.skip_back_btn)

        self.play_pause_btn = QPushButton("\u25B6  Play")
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setFixedWidth(100)
        self.play_pause_btn.setObjectName("primaryButton")
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        btn_row.addWidget(self.play_pause_btn)

        self.skip_fwd_btn = QPushButton(f"{self.SKIP_SECONDS}s \u23E9")
        self.skip_fwd_btn.setCursor(Qt.PointingHandCursor)
        self.skip_fwd_btn.setFixedWidth(70)
        self.skip_fwd_btn.clicked.connect(self.skip_forward)
        btn_row.addWidget(self.skip_fwd_btn)

        btn_row.addSpacing(20)

        vol_label = QLabel("\U0001F50A")
        vol_label.setFixedWidth(22)
        btn_row.addWidget(vol_label)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        btn_row.addWidget(self.volume_slider)

        self.volume_label = QLabel("100%")
        self.volume_label.setFixedWidth(40)
        self.volume_label.setStyleSheet("font-size: 11px; color: #9E9E9E;")
        btn_row.addWidget(self.volume_label)

        btn_row.addStretch()

        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("font-size: 12px; color: #757575; font-weight: 500;")
        btn_row.addWidget(speed_label)

        self.speed_combo = QComboBox()
        for spd in self.SPEED_OPTIONS:
            self.speed_combo.addItem(f"{spd}x" if spd != 1.0 else "1.0x (Normal)", spd)
        self.speed_combo.setCurrentIndex(self.SPEED_OPTIONS.index(1.0))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        btn_row.addWidget(self.speed_combo)

        btn_row.addSpacing(12)

        sub_label = QLabel("Subtitles:")
        sub_label.setStyleSheet("font-size: 12px; color: #757575; font-weight: 500;")
        btn_row.addWidget(sub_label)

        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItem("Off", -1)
        self.subtitle_combo.setMinimumWidth(120)
        self.subtitle_combo.currentIndexChanged.connect(self._on_subtitle_changed)
        btn_row.addWidget(self.subtitle_combo)

        controls_layout.addLayout(btn_row)
        layout.addWidget(controls_widget)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key_Right), self, self.skip_forward)
        QShortcut(QKeySequence(Qt.Key_Left), self, self.skip_backward)
        QShortcut(QKeySequence(Qt.Key_F11), self, self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._exit_fullscreen)
        QShortcut(QKeySequence(Qt.Key_M), self, self._toggle_mute)
        QShortcut(QKeySequence(Qt.Key_Up), self, self._volume_up)
        QShortcut(QKeySequence(Qt.Key_Down), self, self._volume_down)

    def _setup_timer(self):
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(500)
        self._update_timer.timeout.connect(self._update_ui)

    def load_movie(self, movie: Movie):
        if not VLC_AVAILABLE:
            self.movie_title_label.setText("VLC not available - install VLC to play movies")
            return
        self.movie = movie
        self.movie_title_label.setText(movie.title)
        if not self._vlc_instance:
            self._vlc_instance = vlc.Instance()
        if not self._media_player:
            self._media_player = self._vlc_instance.media_player_new()
        if sys.platform == "win32":
            self._media_player.set_hwnd(int(self.video_frame.winId()))
        elif sys.platform == "darwin":
            self._media_player.set_nsobject(int(self.video_frame.winId()))
        else:
            self._media_player.set_xwindow(int(self.video_frame.winId()))

        movie_abs = os.path.join(get_library_root(), movie.movie_path)
        self._media = self._vlc_instance.media_new(movie_abs)
        self._media_player.set_media(self._media)
        self._media_player.play()
        self._is_playing = True
        self.play_pause_btn.setText("\u23F8  Pause")
        if movie.last_position > 0:
            QTimer.singleShot(500, lambda: self._resume_position(movie.last_position))
        QTimer.singleShot(1000, self._populate_subtitles)
        for sub_path, label in movie.subtitle_paths:
            if sub_path:
                sub_abs = os.path.join(get_library_root(), sub_path)
                if os.path.exists(sub_abs):
                    self._media_player.add_slave(vlc.MediaSlaveType.subtitle, f"file:///{sub_abs}", True)
        self._update_timer.start()
        self.speed_combo.setCurrentIndex(self.SPEED_OPTIONS.index(1.0))

    def stop(self):
        if self._media_player:
            self._save_position()
            self._media_player.stop()
        self._is_playing = False
        self._update_timer.stop()
        self.play_pause_btn.setText("\u25B6  Play")

    def toggle_play_pause(self):
        if not self._media_player:
            return
        if self._is_playing:
            self._media_player.pause()
            self._is_playing = False
            self.play_pause_btn.setText("\u25B6  Play")
        else:
            self._media_player.play()
            self._is_playing = True
            self.play_pause_btn.setText("\u23F8  Pause")

    def skip_forward(self):
        if self._media_player:
            c = self._media_player.get_time()
            if c >= 0:
                self._media_player.set_time(c + self.SKIP_SECONDS * 1000)

    def skip_backward(self):
        if self._media_player:
            c = self._media_player.get_time()
            if c >= 0:
                self._media_player.set_time(max(0, c - self.SKIP_SECONDS * 1000))

    def toggle_fullscreen(self):
        window = self.window()
        if self._is_fullscreen:
            window.showNormal()
            self._is_fullscreen = False
            self.fullscreen_btn.setText("\u26F6  Fullscreen")
        else:
            window.showFullScreen()
            self._is_fullscreen = True
            self.fullscreen_btn.setText("\u26F6  Exit FS")

    def cleanup(self):
        self._update_timer.stop()
        if self._media_player:
            self._save_position()
            self._media_player.stop()
            self._media_player.release()
            self._media_player = None
        if self._vlc_instance:
            self._vlc_instance.release()
            self._vlc_instance = None

    def _exit_fullscreen(self):
        if self._is_fullscreen:
            self.toggle_fullscreen()

    def _resume_position(self, pos):
        if self._media_player:
            self._media_player.set_time(int(pos * 1000))

    def _save_position(self):
        if not self._media_player or not self.movie:
            return
        ms = self._media_player.get_time()
        if ms > 0:
            self.db.update_playback_position(self.movie.id, ms / 1000.0)
        dur = self._media_player.get_length()
        if dur > 0 and self.movie.duration == 0:
            self.db.update_duration(self.movie.id, dur / 1000.0)

    def _populate_subtitles(self):
        if not self._media_player:
            return
        self.subtitle_combo.blockSignals(True)
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("Off", -1)
        try:
            spu_desc = self._media_player.video_get_spu_description()
            if spu_desc:
                for tid, tname in spu_desc:
                    if tid == -1:
                        continue
                    name = tname.decode() if isinstance(tname, bytes) else tname
                    self.subtitle_combo.addItem(name, tid)
        except Exception:
            pass
        self.subtitle_combo.blockSignals(False)

    def _on_seek_start(self):
        self._seeking = True

    def _on_seek_moved(self, value):
        if self._duration > 0:
            self.time_current.setText(format_time((value / 1000) * (self._duration / 1000)))

    def _on_seek_end(self):
        self._seeking = False
        if self._media_player and self._duration > 0:
            self._media_player.set_position(self.seek_slider.value() / 1000.0)

    def _on_volume_changed(self, value):
        if self._media_player:
            self._media_player.audio_set_volume(value)
        self.volume_label.setText(f"{value}%")

    def _on_speed_changed(self, index):
        speed = self.speed_combo.currentData()
        if self._media_player and speed:
            self._media_player.set_rate(speed)

    def _on_subtitle_changed(self, index):
        tid = self.subtitle_combo.currentData()
        if self._media_player and tid is not None:
            self._media_player.video_set_spu(tid)

    def _toggle_mute(self):
        if self._media_player:
            self._media_player.audio_toggle_mute()

    def _volume_up(self):
        self.volume_slider.setValue(min(100, self.volume_slider.value() + 5))

    def _volume_down(self):
        self.volume_slider.setValue(max(0, self.volume_slider.value() - 5))

    def _on_back(self):
        self.stop()
        if self._is_fullscreen:
            self.toggle_fullscreen()
        self.back_requested.emit()

    @Slot()
    def _update_ui(self):
        if not self._media_player:
            return
        length = self._media_player.get_length()
        if length > 0:
            self._duration = length
            self.time_total.setText(format_time(length / 1000))
        if not self._seeking:
            current = self._media_player.get_time()
            if current >= 0:
                self.time_current.setText(format_time(current / 1000))
                if self._duration > 0:
                    self.seek_slider.blockSignals(True)
                    self.seek_slider.setValue(int((current / self._duration) * 1000))
                    self.seek_slider.blockSignals(False)
        state = self._media_player.get_state()
        if state == vlc.State.Ended:
            self._is_playing = False
            self.play_pause_btn.setText("\u25B6  Play")
            self._update_timer.stop()
            if self.movie:
                self.db.update_playback_position(self.movie.id, 0)
        if self._is_playing and self.movie:
            ms = self._media_player.get_time()
            if ms > 0:
                self.db.update_playback_position(self.movie.id, ms / 1000.0)
