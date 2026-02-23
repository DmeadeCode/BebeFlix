"""
Video player widget for BebeFlix.
Supports movies and TV show episodes with fullscreen auto-hide controls,
next episode, and autoplay.
"""

import os
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QSlider, QComboBox, QFrame,
                                QSizePolicy, QCheckBox)
from PySide6.QtCore import Qt, Signal, QTimer, Slot
from PySide6.QtGui import QKeySequence, QShortcut, QCursor

from database import Movie, Episode, Database
from utils.paths import get_library_root, normalize_path

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
    HIDE_DELAY_MS = 3000

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.movie: Movie = None
        self.episode: Episode = None
        self._episode_list = []      # flat list of all episodes in the show
        self._current_ep_index = -1  # index into _episode_list
        self._show_title = ""
        self._autoplay = True
        self._vlc_instance = None
        self._media_player = None
        self._media = None
        self._is_playing = False
        self._is_fullscreen = False
        self._duration = 0
        self._seeking = False
        self._controls_visible = True
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_timer()
        self._setup_hide_timer()
        self.setMouseTracking(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(16, 10, 16, 10)

        self.back_btn = QPushButton("<- Library")
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
        self.movie_title_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #C2185B; padding-left: 12px;")
        top_bar.addWidget(self.movie_title_label)
        top_bar.addStretch()

        # Show-only controls in top bar
        self.autoplay_check = QCheckBox("Autoplay")
        self.autoplay_check.setChecked(True)
        self.autoplay_check.setStyleSheet("""
            QCheckBox {
                font-size: 12px; font-weight: 600; color: #D81B60;
                spacing: 6px; padding: 4px 8px;
            }
        """)
        self.autoplay_check.toggled.connect(self._on_autoplay_toggled)
        self.autoplay_check.setVisible(False)
        top_bar.addWidget(self.autoplay_check)

        self.next_ep_btn = QPushButton("Next Ep >>")
        self.next_ep_btn.setCursor(Qt.PointingHandCursor)
        self.next_ep_btn.setFixedWidth(100)
        self.next_ep_btn.setStyleSheet("""
            QPushButton {
                background-color: #EC407A; color: #FFFFFF; border: none;
                border-radius: 16px; padding: 6px 14px; font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background-color: #D81B60; }
        """)
        self.next_ep_btn.clicked.connect(self._play_next_episode)
        self.next_ep_btn.setVisible(False)
        top_bar.addWidget(self.next_ep_btn)

        top_bar.addSpacing(8)

        self.fullscreen_btn = QPushButton("Fullscreen")
        self.fullscreen_btn.setCursor(Qt.PointingHandCursor)
        self.fullscreen_btn.setFixedWidth(100)
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #D81B60; border: 2px solid #F8BBD0;
                border-radius: 16px; padding: 6px 14px; font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background-color: #FCE4EC; border-color: #EC407A; }
        """)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        top_bar.addWidget(self.fullscreen_btn)

        self.top_widget = QWidget()
        self.top_widget.setLayout(top_bar)
        self.top_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFF0F5, stop:1 #FCE4EC);
                border-bottom: 2px solid #F8BBD0;
            }
        """)
        layout.addWidget(self.top_widget)

        # Video frame
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_frame.mouseDoubleClickEvent = lambda e: self.toggle_fullscreen()
        self.video_frame.setMouseTracking(True)
        layout.addWidget(self.video_frame)

        # Controls panel
        self.controls_widget = QWidget()
        self.controls_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #FFF5F8);
                border-top: 2px solid #F8BBD0;
            }
        """)
        controls_layout = QVBoxLayout(self.controls_widget)
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

        compact_btn_style = """
            QPushButton {
                padding: 6px 8px; border-radius: 12px; font-size: 12px;
                font-weight: 600; background: #FFFFFF; color: #2C2C2C;
                border: 2px solid #E0E0E0;
            }
            QPushButton:hover { background: #FCE4EC; border-color: #F48FB1; color: #D81B60; }
        """
        play_btn_style = """
            QPushButton {
                padding: 6px 8px; border-radius: 12px; font-size: 12px;
                font-weight: bold; background: #F48FB1; color: #FFFFFF; border: none;
            }
            QPushButton:hover { background: #EC407A; }
        """

        self.skip_back_btn = QPushButton("-10s")
        self.skip_back_btn.setCursor(Qt.PointingHandCursor)
        self.skip_back_btn.setFixedWidth(56)
        self.skip_back_btn.setStyleSheet(compact_btn_style)
        self.skip_back_btn.clicked.connect(self.skip_backward)
        btn_row.addWidget(self.skip_back_btn)

        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setFixedWidth(70)
        self.play_pause_btn.setStyleSheet(play_btn_style)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        btn_row.addWidget(self.play_pause_btn)

        self.skip_fwd_btn = QPushButton("+10s")
        self.skip_fwd_btn.setCursor(Qt.PointingHandCursor)
        self.skip_fwd_btn.setFixedWidth(56)
        self.skip_fwd_btn.setStyleSheet(compact_btn_style)
        self.skip_fwd_btn.clicked.connect(self.skip_forward)
        btn_row.addWidget(self.skip_fwd_btn)

        btn_row.addSpacing(20)

        vol_label = QLabel("Vol")
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

        audio_label = QLabel("Audio:")
        audio_label.setStyleSheet("font-size: 12px; color: #757575; font-weight: 500;")
        btn_row.addWidget(audio_label)

        self.audio_combo = QComboBox()
        self.audio_combo.addItem("Default", -1)
        self.audio_combo.currentIndexChanged.connect(self._on_audio_changed)
        btn_row.addWidget(self.audio_combo)

        btn_row.addSpacing(12)

        sub_label = QLabel("Subs:")
        sub_label.setStyleSheet("font-size: 12px; color: #757575; font-weight: 500;")
        btn_row.addWidget(sub_label)

        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItem("Off", -1)
        self.subtitle_combo.currentIndexChanged.connect(self._on_subtitle_changed)
        btn_row.addWidget(self.subtitle_combo)
        controls_layout.addLayout(btn_row)
        layout.addWidget(self.controls_widget)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key_Right), self, self.skip_forward)
        QShortcut(QKeySequence(Qt.Key_Left), self, self.skip_backward)
        QShortcut(QKeySequence(Qt.Key_F11), self, self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._exit_fullscreen)
        QShortcut(QKeySequence(Qt.Key_M), self, self._toggle_mute)
        QShortcut(QKeySequence(Qt.Key_Up), self, self._volume_up)
        QShortcut(QKeySequence(Qt.Key_Down), self, self._volume_down)
        QShortcut(QKeySequence(Qt.Key_N), self, self._play_next_episode)

    def _setup_timer(self):
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(500)
        self._update_timer.timeout.connect(self._update_ui)

    def _setup_hide_timer(self):
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(self.HIDE_DELAY_MS)
        self._hide_timer.timeout.connect(self._hide_controls)

    def _show_controls(self):
        if not self._controls_visible:
            self.top_widget.setVisible(True)
            self.controls_widget.setVisible(True)
            self._controls_visible = True
        self.setCursor(Qt.ArrowCursor)
        self.video_frame.setCursor(Qt.ArrowCursor)
        if self._is_fullscreen:
            self._hide_timer.start()

    def _hide_controls(self):
        if not self._is_fullscreen:
            return
        self.top_widget.setVisible(False)
        self.controls_widget.setVisible(False)
        self._controls_visible = False
        self.setCursor(Qt.BlankCursor)
        self.video_frame.setCursor(Qt.BlankCursor)

    def mouseMoveEvent(self, event):
        self._show_controls()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        self._show_controls()
        super().keyPressEvent(event)

    # ---- Show/hide episode controls -------------------------------------------------------

    def _update_episode_controls(self):
        """Show or hide episode-specific controls."""
        is_episode = self.episode is not None
        has_next = self._has_next_episode()
        self.autoplay_check.setVisible(is_episode)
        self.next_ep_btn.setVisible(is_episode and has_next)

    def _has_next_episode(self):
        return (self._episode_list
                and 0 <= self._current_ep_index < len(self._episode_list) - 1)

    # ---- Loading --------------------------------------------------------------------------

    def load_movie(self, movie: Movie):
        self.movie = movie
        self.episode = None
        self._episode_list = []
        self._current_ep_index = -1
        self._show_title = ""
        self.movie_title_label.setText(movie.title)
        movie_abs = os.path.join(get_library_root(), normalize_path(movie.movie_path))
        self._load_media(movie_abs)
        if movie.last_position > 0:
            QTimer.singleShot(500, lambda: self._resume_position(movie.last_position))
        QTimer.singleShot(1000, self._populate_tracks)
        for sub_path, label in movie.subtitle_paths:
            if sub_path:
                sub_abs = os.path.join(get_library_root(), sub_path)
                if os.path.exists(sub_abs):
                    self._media_player.add_slave(
                        vlc.MediaSlaveType.subtitle, f"file:///{sub_abs}", True)
        self._update_episode_controls()

    def load_episode(self, episode: Episode, show_title: str = "",
                     episode_list: list = None, episode_index: int = -1):
        """Load a TV show episode. Optionally pass full episode list for next/autoplay."""
        self.episode = episode
        self.movie = None
        self._show_title = show_title
        self._episode_list = episode_list or []
        self._current_ep_index = episode_index

        display = f"{show_title} - " if show_title else ""
        display += f"E{episode.episode_number}"
        if episode.title:
            display += f": {episode.title}"
        self.movie_title_label.setText(display)

        ep_abs = os.path.join(get_library_root(), normalize_path(episode.movie_path))
        self._load_media(ep_abs)
        if episode.last_position > 0:
            QTimer.singleShot(500, lambda: self._resume_position(episode.last_position))
        QTimer.singleShot(1000, self._populate_tracks)
        self._update_episode_controls()

    def _load_media(self, file_path: str):
        if not VLC_AVAILABLE:
            self.movie_title_label.setText("VLC not available - install VLC to play movies")
            return
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
        self._media = self._vlc_instance.media_new(file_path)
        self._media_player.set_media(self._media)
        self._media_player.play()
        self._is_playing = True
        self.play_pause_btn.setText("Pause")
        self._update_timer.start()
        self.speed_combo.setCurrentIndex(self.SPEED_OPTIONS.index(1.0))

    # ---- Next Episode ---------------------------------------------------------------------

    def _play_next_episode(self):
        if not self._has_next_episode():
            return
        # Save current position first
        self._save_position()
        if self._media_player:
            self._media_player.stop()
        self._current_ep_index += 1
        next_ep = self._episode_list[self._current_ep_index]
        # Reload the episode from DB for fresh position data
        self.episode = next_ep
        display = f"{self._show_title} - " if self._show_title else ""
        display += f"E{next_ep.episode_number}"
        if next_ep.title:
            display += f": {next_ep.title}"
        self.movie_title_label.setText(display)

        ep_abs = os.path.join(get_library_root(), normalize_path(next_ep.movie_path))
        self._media = self._vlc_instance.media_new(ep_abs)
        self._media_player.set_media(self._media)
        self._media_player.play()
        self._is_playing = True
        self.play_pause_btn.setText("Pause")
        self._duration = 0
        self._update_timer.start()
        self.speed_combo.setCurrentIndex(self.SPEED_OPTIONS.index(1.0))
        QTimer.singleShot(1000, self._populate_tracks)
        self._update_episode_controls()

    def _on_autoplay_toggled(self, checked):
        self._autoplay = checked

    # ---- Playback Controls ----------------------------------------------------------------

    def stop(self):
        if self._media_player:
            self._save_position()
            self._media_player.stop()
        self._is_playing = False
        self._update_timer.stop()
        self._hide_timer.stop()
        self.play_pause_btn.setText("Play")

    def toggle_play_pause(self):
        if not self._media_player:
            return
        self._show_controls()
        if self._is_playing:
            self._media_player.pause()
            self._is_playing = False
            self.play_pause_btn.setText("Play")
        else:
            self._media_player.play()
            self._is_playing = True
            self.play_pause_btn.setText("Pause")

    def skip_forward(self):
        if self._media_player:
            self._show_controls()
            c = self._media_player.get_time()
            if c >= 0:
                self._media_player.set_time(c + self.SKIP_SECONDS * 1000)

    def skip_backward(self):
        if self._media_player:
            self._show_controls()
            c = self._media_player.get_time()
            if c >= 0:
                self._media_player.set_time(max(0, c - self.SKIP_SECONDS * 1000))

    def toggle_fullscreen(self):
        window = self.window()
        if self._is_fullscreen:
            window.showNormal()
            self._is_fullscreen = False
            self.fullscreen_btn.setText("Fullscreen")
            self._hide_timer.stop()
            self._show_controls()
        else:
            window.showFullScreen()
            self._is_fullscreen = True
            self.fullscreen_btn.setText("Exit FS")
            self._hide_timer.start()

    def cleanup(self):
        self._update_timer.stop()
        self._hide_timer.stop()
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
        if not self._media_player:
            return
        ms = self._media_player.get_time()
        dur = self._media_player.get_length()

        if self.movie and ms > 0:
            self.db.update_playback_position(self.movie.id, ms / 1000.0)
            if dur > 0 and self.movie.duration == 0:
                self.db.update_duration(self.movie.id, dur / 1000.0)
        elif self.episode and ms > 0:
            self.db.update_episode_position(self.episode.id, ms / 1000.0)
            if dur > 0 and self.episode.duration == 0:
                self.db.update_episode_duration(self.episode.id, dur / 1000.0)

    def _populate_tracks(self):
        self._populate_subtitles()
        self._populate_audio_tracks()

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

    def _populate_audio_tracks(self):
        if not self._media_player:
            return
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        try:
            tracks = self._media_player.audio_get_track_description()
            if tracks:
                for tid, tname in tracks:
                    name = tname.decode() if isinstance(tname, bytes) else tname
                    if tid == -1:
                        self.audio_combo.addItem("Off", -1)
                    else:
                        self.audio_combo.addItem(name, tid)
                # Select the currently active track
                current = self._media_player.audio_get_track()
                for i in range(self.audio_combo.count()):
                    if self.audio_combo.itemData(i) == current:
                        self.audio_combo.setCurrentIndex(i)
                        break
            else:
                self.audio_combo.addItem("Default", -1)
        except Exception:
            self.audio_combo.addItem("Default", -1)
        self.audio_combo.blockSignals(False)
        # Hide if only one real track (no choice to make)
        real_tracks = self.audio_combo.count() - (
            1 if self.audio_combo.itemData(0) == -1 else 0)
        self.audio_combo.setVisible(real_tracks > 1)
        # Also hide the label
        parent_layout = self.audio_combo.parentWidget()
        if parent_layout:
            # Find the Audio: label right before the combo
            layout = self.audio_combo.parent().layout()
            if layout:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() == self.audio_combo and i > 0:
                        prev = layout.itemAt(i - 1)
                        if prev and prev.widget():
                            prev.widget().setVisible(real_tracks > 1)
                        break

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

    def _on_audio_changed(self, index):
        tid = self.audio_combo.currentData()
        if self._media_player and tid is not None:
            self._media_player.audio_set_track(tid)

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
            self.play_pause_btn.setText("Play")
            self._update_timer.stop()
            if self.movie:
                self.db.update_playback_position(self.movie.id, 0)
            elif self.episode:
                self.db.update_episode_position(self.episode.id, 0)
                # Autoplay next episode
                if self._autoplay and self._has_next_episode():
                    QTimer.singleShot(1500, self._play_next_episode)
        if self._is_playing:
            self._save_position()
