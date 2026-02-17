"""
Add Movie / TV Show dialog for BebeFlix.
Toggle between movie mode and show mode.
"""

import os
import re
import shutil
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QComboBox, QFileDialog,
                                QProgressBar, QCheckBox, QMessageBox, QGroupBox,
                                QSizePolicy, QSpinBox, QListWidget, QListWidgetItem,
                                QRadioButton, QButtonGroup, QWidget)
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from database import Database
from utils.paths import (get_movies_dir, get_library_root, slugify,
                         make_movie_dir, get_drive_free_space, format_file_size)
from utils.compression import (PRESETS, PRESET_ORDER, CompressionThread,
                                get_embedded_subtitles)


class AddMovieDialog(QDialog):
    movie_added = Signal(int)
    show_added = Signal(int)

    VIDEO_EXTENSIONS = "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.wmv *.m4v *.flv);;All Files (*)"
    IMAGE_EXTENSIONS = "Image Files (*.jpg *.jpeg *.png *.webp *.bmp);;All Files (*)"
    SUBTITLE_EXTENSIONS = "Subtitle Files (*.srt *.ass *.ssa *.sub *.vtt);;All Files (*)"

    def __init__(self, db: Database, parent=None, mode="movie",
                 existing_show=None, season_number=None):
        super().__init__(parent)
        self.db = db
        self._movie_path = ""
        self._thumb_path = ""
        self._subtitle_paths = []
        self._embedded_subs = []
        self._episode_paths = []
        self._compression_thread = None
        self._is_processing = False
        self._mode = mode
        self._existing_show = existing_show
        self._forced_season = season_number
        self._episode_queue = []
        self._current_ep_index = 0

        self.setWindowTitle("Add Content - BebeFlix")
        self.setMinimumWidth(560)
        self.setMinimumHeight(580)
        self._setup_ui()

        # If adding season to existing show, lock to show mode
        if self._existing_show:
            self.show_radio.setChecked(True)
            self._on_mode_changed()
            self.movie_radio.setEnabled(False)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("Add to Library")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #D81B60;")
        layout.addWidget(header)

        # Mode toggle
        mode_row = QHBoxLayout()
        self.movie_radio = QRadioButton("Movie")
        self.show_radio = QRadioButton("TV Show")
        self.movie_radio.setStyleSheet("font-size: 13px; font-weight: 600; color: #2C2C2C;")
        self.show_radio.setStyleSheet("font-size: 13px; font-weight: 600; color: #2C2C2C;")

        if self._mode == "show":
            self.show_radio.setChecked(True)
        else:
            self.movie_radio.setChecked(True)

        self.movie_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.movie_radio)
        mode_row.addWidget(self.show_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ---- Movie-specific widgets ----
        self.movie_widgets = QWidget()
        movie_layout = QVBoxLayout(self.movie_widgets)
        movie_layout.setContentsMargins(0, 0, 0, 0)
        movie_layout.setSpacing(10)

        movie_layout.addWidget(QLabel("Title:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter movie title...")
        movie_layout.addWidget(self.title_input)

        movie_layout.addWidget(QLabel("Movie File:"))
        movie_row = QHBoxLayout()
        self.movie_path_label = QLabel("No file selected")
        self.movie_path_label.setObjectName("subtitleLabel")
        self.movie_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        movie_row.addWidget(self.movie_path_label)
        self.movie_browse_btn = QPushButton("Browse...")
        self.movie_browse_btn.clicked.connect(self._browse_movie)
        movie_row.addWidget(self.movie_browse_btn)
        movie_layout.addLayout(movie_row)

        movie_layout.addWidget(QLabel("Poster / Thumbnail:"))
        thumb_row = QHBoxLayout()
        self.thumb_path_label = QLabel("No file selected")
        self.thumb_path_label.setObjectName("subtitleLabel")
        self.thumb_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        thumb_row.addWidget(self.thumb_path_label)
        self.thumb_browse_btn = QPushButton("Browse...")
        self.thumb_browse_btn.clicked.connect(self._browse_thumbnail)
        thumb_row.addWidget(self.thumb_browse_btn)
        movie_layout.addLayout(thumb_row)

        sub_group = QGroupBox("Subtitles (Optional)")
        sub_layout = QVBoxLayout(sub_group)
        sub_file_row = QHBoxLayout()
        self.sub_path_label = QLabel("No subtitle files selected")
        self.sub_path_label.setObjectName("subtitleLabel")
        self.sub_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sub_file_row.addWidget(self.sub_path_label)
        self.sub_browse_btn = QPushButton("Browse...")
        self.sub_browse_btn.clicked.connect(self._browse_subtitles)
        sub_file_row.addWidget(self.sub_browse_btn)
        sub_layout.addLayout(sub_file_row)
        self.embedded_check = QCheckBox("Auto-detect embedded subtitles")
        self.embedded_check.setChecked(True)
        sub_layout.addWidget(self.embedded_check)
        self.embedded_info = QLabel("")
        self.embedded_info.setObjectName("subtitleLabel")
        sub_layout.addWidget(self.embedded_info)
        movie_layout.addWidget(sub_group)
        layout.addWidget(self.movie_widgets)

        # ---- Show-specific widgets ----
        self.show_widgets = QWidget()
        show_layout = QVBoxLayout(self.show_widgets)
        show_layout.setContentsMargins(0, 0, 0, 0)
        show_layout.setSpacing(10)

        # Existing or new show
        show_layout.addWidget(QLabel("Show:"))
        self.show_selector = QComboBox()
        self.show_selector.addItem("-- New Show --", None)
        for sid, stitle in self.db.get_existing_show_titles():
            self.show_selector.addItem(stitle, sid)
        self.show_selector.currentIndexChanged.connect(self._on_show_selected)
        show_layout.addWidget(self.show_selector)

        # Pre-select existing show if provided
        if self._existing_show:
            for i in range(self.show_selector.count()):
                if self.show_selector.itemData(i) == self._existing_show.id:
                    self.show_selector.setCurrentIndex(i)
                    break

        # New show fields
        self.new_show_group = QWidget()
        new_show_layout = QVBoxLayout(self.new_show_group)
        new_show_layout.setContentsMargins(0, 0, 0, 0)
        new_show_layout.setSpacing(8)

        new_show_layout.addWidget(QLabel("Show Title:"))
        self.show_title_input = QLineEdit()
        self.show_title_input.setPlaceholderText("Enter show name...")
        self.show_title_input.setMinimumHeight(36)
        new_show_layout.addWidget(self.show_title_input)

        new_show_layout.addWidget(QLabel("Show Poster:"))
        show_thumb_row = QHBoxLayout()
        self.show_thumb_label = QLabel("No file selected")
        self.show_thumb_label.setObjectName("subtitleLabel")
        self.show_thumb_label.setMinimumHeight(36)
        self.show_thumb_label.setStyleSheet("""
            QLabel {
                background-color: #F5F5F5; border: 1px solid #E0E0E0;
                border-radius: 6px; padding: 8px 12px; font-size: 12px; color: #757575;
            }
        """)
        self.show_thumb_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        show_thumb_row.addWidget(self.show_thumb_label)
        self.show_thumb_btn = QPushButton("Browse...")
        self.show_thumb_btn.setMinimumHeight(36)
        self.show_thumb_btn.setFixedWidth(100)
        self.show_thumb_btn.clicked.connect(self._browse_show_thumbnail)
        show_thumb_row.addWidget(self.show_thumb_btn)
        new_show_layout.addLayout(show_thumb_row)
        show_layout.addWidget(self.new_show_group)

        # Season number
        season_row = QHBoxLayout()
        season_row.addWidget(QLabel("Season Number:"))
        self.season_spin = QSpinBox()
        self.season_spin.setRange(1, 99)
        self.season_spin.setValue(self._forced_season or 1)
        if self._forced_season:
            self.season_spin.setEnabled(False)
        season_row.addWidget(self.season_spin)
        season_row.addStretch()
        show_layout.addLayout(season_row)

        # Episode files
        show_layout.addWidget(QLabel("Episode Files:"))
        ep_info = QLabel("Select files in order. They will be numbered E1, E2, E3...")
        ep_info.setStyleSheet("font-size: 11px; color: #9E9E9E;")
        show_layout.addWidget(ep_info)

        ep_row = QHBoxLayout()
        self.episode_list = QListWidget()
        self.episode_list.setMinimumHeight(140)
        self.episode_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E0E0E0; border-radius: 8px;
                background-color: #FAFAFA; font-size: 13px; padding: 4px;
            }
            QListWidget::item { padding: 4px 8px; }
            QListWidget::item:hover { background-color: #FFF0F5; }
        """)
        ep_row.addWidget(self.episode_list)

        ep_btn_col = QVBoxLayout()
        self.ep_browse_btn = QPushButton("Add Files...")
        self.ep_browse_btn.setMinimumHeight(36)
        self.ep_browse_btn.setFixedWidth(100)
        self.ep_browse_btn.clicked.connect(self._browse_episodes)
        ep_btn_col.addWidget(self.ep_browse_btn)
        self.ep_clear_btn = QPushButton("Clear All")
        self.ep_clear_btn.setMinimumHeight(36)
        self.ep_clear_btn.setFixedWidth(100)
        self.ep_clear_btn.clicked.connect(self._clear_episodes)
        ep_btn_col.addWidget(self.ep_clear_btn)
        ep_btn_col.addStretch()
        ep_row.addLayout(ep_btn_col)
        show_layout.addLayout(ep_row)

        self.show_widgets.setVisible(False)
        layout.addWidget(self.show_widgets)

        # ---- Shared widgets ----
        layout.addWidget(QLabel("Compression:"))
        self.preset_combo = QComboBox()
        for key in PRESET_ORDER:
            self.preset_combo.addItem(str(PRESETS[key]), key)
        self.preset_combo.setCurrentIndex(0)
        layout.addWidget(self.preset_combo)

        self.space_label = QLabel("")
        self.space_label.setObjectName("subtitleLabel")
        self._update_space_label()
        layout.addWidget(self.space_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subtitleLabel")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.cancel_btn)
        self.add_btn = QPushButton("Add to Library")
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self.add_btn)
        layout.addLayout(btn_row)

    # ---- Mode switching --------------------------------------------------------------------------

    def _on_mode_changed(self):
        is_show = self.show_radio.isChecked()
        self.movie_widgets.setVisible(not is_show)
        self.show_widgets.setVisible(is_show)
        if is_show:
            self._on_show_selected()

    def _on_show_selected(self):
        show_id = self.show_selector.currentData()
        is_new = show_id is None
        self.new_show_group.setVisible(is_new)
        if not is_new and not self._forced_season:
            next_season = self.db.get_next_season_number(show_id)
            self.season_spin.setValue(next_season)

    # ---- Browse handlers ------------------------------------------------------------------------

    def _browse_movie(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Movie File", "", self.VIDEO_EXTENSIONS)
        if path:
            self._movie_path = path
            filename = os.path.basename(path)
            size = format_file_size(os.path.getsize(path))
            self.movie_path_label.setText(f"{filename} ({size})")
            if not self.title_input.text().strip():
                name_no_ext = os.path.splitext(filename)[0]
                clean = name_no_ext.replace(".", " ").replace("_", " ").replace("-", " ")
                self.title_input.setText(clean.strip())
            if self.embedded_check.isChecked():
                self._detect_embedded_subs(path)
            self._update_space_label()

    def _browse_thumbnail(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Thumbnail Image", "", self.IMAGE_EXTENSIONS)
        if path:
            self._thumb_path = path
            self.thumb_path_label.setText(os.path.basename(path))

    def _browse_show_thumbnail(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Show Poster", "", self.IMAGE_EXTENSIONS)
        if path:
            self._thumb_path = path
            self.show_thumb_label.setText(os.path.basename(path))

    def _browse_subtitles(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Subtitle Files", "", self.SUBTITLE_EXTENSIONS)
        if paths:
            self._subtitle_paths = paths
            self.sub_path_label.setText(", ".join(os.path.basename(p) for p in paths))

    def _browse_episodes(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Episode Files", "", self.VIDEO_EXTENSIONS)
        if paths:
            # Sort naturally by filename (Episode 1, 2, 3...)
            paths.sort(key=lambda p: self._natural_sort_key(os.path.basename(p)))
            self._episode_paths.extend(paths)
            self._refresh_episode_list()

    def _clear_episodes(self):
        self._episode_paths.clear()
        self.episode_list.clear()

    def _refresh_episode_list(self):
        self.episode_list.clear()
        for i, path in enumerate(self._episode_paths):
            name = os.path.basename(path)
            self.episode_list.addItem(f"E{i+1}: {name}")

    @staticmethod
    def _natural_sort_key(s):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]

    def _detect_embedded_subs(self, movie_path):
        self._embedded_subs = get_embedded_subtitles(movie_path)
        if self._embedded_subs:
            labels = [s["label"] for s in self._embedded_subs]
            self.embedded_info.setText(f"Found {len(self._embedded_subs)} embedded track(s): {', '.join(labels)}")
        else:
            self.embedded_info.setText("No embedded subtitles detected.")

    def _update_space_label(self):
        try:
            free = get_drive_free_space()
            self.space_label.setText(f"Available drive space: {format_file_size(free)}")
        except Exception:
            self.space_label.setText("")

    # ---- Validation ----------------------------------------------------------------------------------

    def _validate_movie(self):
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "Missing Title", "Please enter a movie title.")
            return False
        if not self._movie_path or not os.path.exists(self._movie_path):
            QMessageBox.warning(self, "Missing Movie", "Please select a valid movie file.")
            return False
        if not self._thumb_path or not os.path.exists(self._thumb_path):
            QMessageBox.warning(self, "Missing Thumbnail", "Please select a poster/thumbnail image.")
            return False
        return True

    def _validate_show(self):
        show_id = self.show_selector.currentData()
        if show_id is None:
            # New show
            if not self.show_title_input.text().strip():
                QMessageBox.warning(self, "Missing Title", "Please enter a show name.")
                return False
            if not self._thumb_path or not os.path.exists(self._thumb_path):
                QMessageBox.warning(self, "Missing Poster", "Please select a poster image for the new show.")
                return False
        if not self._episode_paths:
            QMessageBox.warning(self, "No Episodes", "Please select at least one episode file.")
            return False
        return True

    # ---- Add logic ------------------------------------------------------------------------------------

    def _on_add(self):
        if self._is_processing:
            return

        if self.show_radio.isChecked():
            if not self._validate_show():
                return
            self._start_show_add()
        else:
            if not self._validate_movie():
                return
            self._start_movie_add()

    def _start_movie_add(self):
        self._is_processing = True
        self.add_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel Import")
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)

        title = self.title_input.text().strip()
        slug = slugify(title)
        movie_dir = make_movie_dir(slug)
        preset_key = self.preset_combo.currentData()
        ext = os.path.splitext(self._movie_path)[1] if preset_key == "copy" else ".mp4"

        movie_dest = os.path.join(movie_dir, f"movie{ext}")
        rel_movie = os.path.relpath(movie_dest, get_library_root())

        thumb_ext = os.path.splitext(self._thumb_path)[1]
        thumb_dest = os.path.join(movie_dir, f"thumbnail{thumb_ext}")
        rel_thumb = os.path.relpath(thumb_dest, get_library_root())
        try:
            shutil.copy2(self._thumb_path, thumb_dest)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy thumbnail: {e}")
            self._reset_ui()
            return

        subtitle_entries = []
        for i, sub_path in enumerate(self._subtitle_paths):
            sub_ext = os.path.splitext(sub_path)[1]
            sub_dest = os.path.join(movie_dir, f"subtitle_{i}{sub_ext}")
            try:
                shutil.copy2(sub_path, sub_dest)
                subtitle_entries.append({
                    "sub_path": os.path.relpath(sub_dest, get_library_root()),
                    "label": os.path.splitext(os.path.basename(sub_path))[0],
                    "is_embedded": False, "track_index": 0
                })
            except Exception:
                pass
        if self.embedded_check.isChecked():
            for emb in self._embedded_subs:
                subtitle_entries.append(emb)

        self.status_label.setText("Processing movie file...")
        self._pending_data = {
            "type": "movie",
            "title": title, "rel_movie": rel_movie, "rel_thumb": rel_thumb,
            "subtitle_entries": subtitle_entries, "movie_dir": movie_dir
        }

        preset = PRESETS.get(preset_key)
        self._compression_thread = CompressionThread(
            self._movie_path, movie_dest, preset, parent=self
        )
        self._compression_thread.progress.connect(self._update_progress)
        self._compression_thread.finished_signal.connect(self._on_single_complete)
        self._compression_thread.start()

    def _start_show_add(self):
        self._is_processing = True
        self.add_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel Import")
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)

        # Get or create show
        show_id = self.show_selector.currentData()
        if show_id is None:
            show_title = self.show_title_input.text().strip()
            show_slug = slugify(show_title)
            show_dir = make_movie_dir(show_slug)
            # Copy show thumbnail
            thumb_ext = os.path.splitext(self._thumb_path)[1]
            thumb_dest = os.path.join(show_dir, f"poster{thumb_ext}")
            rel_thumb = os.path.relpath(thumb_dest, get_library_root())
            try:
                shutil.copy2(self._thumb_path, thumb_dest)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to copy poster: {e}")
                self._reset_ui()
                return
            show_id = self.db.add_show(show_title, rel_thumb)
        else:
            show_title = self.show_selector.currentText()

        season_num = self.season_spin.value()
        season_id = self.db.add_season(show_id, season_num)
        show_slug = slugify(show_title)

        # Build episode queue
        preset_key = self.preset_combo.currentData()
        preset = PRESETS.get(preset_key)
        self._episode_queue = []

        for i, ep_path in enumerate(self._episode_paths):
            ep_num = i + 1
            ep_slug = f"s{season_num:02d}e{ep_num:02d}"
            ep_dir = os.path.join(get_movies_dir(), show_slug, ep_slug)
            os.makedirs(ep_dir, exist_ok=True)

            ext = os.path.splitext(ep_path)[1] if preset_key == "copy" else ".mp4"
            ep_dest = os.path.join(ep_dir, f"episode{ext}")
            rel_ep = os.path.relpath(ep_dest, get_library_root())

            # Try to extract episode title from filename
            ep_title = self._extract_episode_title(os.path.basename(ep_path))

            self._episode_queue.append({
                "source": ep_path, "dest": ep_dest,
                "rel_path": rel_ep, "season_id": season_id,
                "episode_number": ep_num, "title": ep_title,
                "preset": preset
            })

        self._pending_data = {"type": "show", "show_id": show_id}
        self._current_ep_index = 0
        self._process_next_episode()

    @staticmethod
    def _extract_episode_title(filename):
        """Try to get a clean title from episode filename."""
        name = os.path.splitext(filename)[0]
        name = name.replace(".", " ").replace("_", " ")
        # Remove common patterns like S01E01, 1x01, etc.
        name = re.sub(r'[Ss]\d+[Ee]\d+', '', name)
        name = re.sub(r'\d+[xX]\d+', '', name)
        name = re.sub(r'[\[\(].*?[\]\)]', '', name)
        name = re.sub(r'\s+', ' ', name).strip(" -")
        return name

    def _process_next_episode(self):
        if self._current_ep_index >= len(self._episode_queue):
            self._finish_show_add()
            return

        total = len(self._episode_queue)
        idx = self._current_ep_index
        ep_data = self._episode_queue[idx]
        self.status_label.setText(
            f"Processing episode {idx + 1} of {total}..."
        )

        self._compression_thread = CompressionThread(
            ep_data["source"], ep_data["dest"], ep_data["preset"], parent=self
        )
        self._compression_thread.progress.connect(
            lambda p: self._update_episode_progress(p, idx, total)
        )
        self._compression_thread.finished_signal.connect(self._on_episode_complete)
        self._compression_thread.start()

    def _update_episode_progress(self, percent, index, total):
        # Overall progress = (completed episodes + current fraction) / total
        overall = ((index + percent / 100.0) / total) * 100
        self.progress_bar.setValue(int(overall))
        self.status_label.setText(
            f"Processing episode {index + 1} of {total}: {percent:.1f}%"
        )

    @Slot(bool, str)
    def _on_episode_complete(self, success, message):
        if not success:
            QMessageBox.warning(self, "Episode Error",
                f"Episode {self._current_ep_index + 1} failed:\n{message}\n\nSkipping...")

        ep_data = self._episode_queue[self._current_ep_index]
        if success:
            self.db.add_episode(
                season_id=ep_data["season_id"],
                episode_number=ep_data["episode_number"],
                title=ep_data["title"],
                movie_path=ep_data["rel_path"]
            )

        self._current_ep_index += 1
        self._process_next_episode()

    def _finish_show_add(self):
        show_id = self._pending_data["show_id"]
        self.progress_bar.setValue(100)
        self.status_label.setText("Show added successfully!")
        self.show_added.emit(show_id)
        QTimer.singleShot(800, self.accept)

    # ---- Movie completion ----------------------------------------------------------------------

    @Slot(float)
    def _update_progress(self, percent):
        self.progress_bar.setValue(int(percent))
        if percent < 100:
            self.status_label.setText(f"Processing: {percent:.1f}%")

    @Slot(bool, str)
    def _on_single_complete(self, success, message):
        if not success:
            QMessageBox.critical(self, "Error", f"Failed to process movie:\n{message}")
            try:
                d = self._pending_data.get("movie_dir", "")
                if d and os.path.exists(d):
                    shutil.rmtree(d)
            except Exception:
                pass
            self._reset_ui()
            return

        data = self._pending_data
        movie_id = self.db.add_movie(
            title=data["title"], movie_path=data["rel_movie"],
            thumb_path=data["rel_thumb"], subtitle_entries=data["subtitle_entries"]
        )
        self.progress_bar.setValue(100)
        self.status_label.setText("Movie added successfully!")
        self.movie_added.emit(movie_id)
        QTimer.singleShot(800, self.accept)

    # ---- Cancel / Reset --------------------------------------------------------------------------

    def _on_cancel(self):
        if self._is_processing:
            if self._compression_thread:
                self._compression_thread.cancel()
                self._compression_thread.wait(2000)
                self._compression_thread = None
            self._is_processing = False
            self._reset_ui()
        else:
            self.reject()

    def _reset_ui(self):
        self._is_processing = False
        self.add_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel")
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(False)
