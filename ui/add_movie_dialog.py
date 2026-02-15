"""
Add Movie dialog for BebeFlix.
"""

import os
import shutil
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QComboBox, QFileDialog,
                                QProgressBar, QCheckBox, QMessageBox, QGroupBox,
                                QSizePolicy)
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from database import Database
from utils.paths import (get_movies_dir, get_library_root, slugify,
                         make_movie_dir, get_drive_free_space, format_file_size)
from utils.compression import (PRESETS, PRESET_ORDER, CompressionWorker,
                                get_embedded_subtitles)


class AddMovieDialog(QDialog):
    movie_added = Signal(int)

    VIDEO_EXTENSIONS = "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.wmv *.m4v *.flv);;All Files (*)"
    IMAGE_EXTENSIONS = "Image Files (*.jpg *.jpeg *.png *.webp *.bmp);;All Files (*)"
    SUBTITLE_EXTENSIONS = "Subtitle Files (*.srt *.ass *.ssa *.sub *.vtt);;All Files (*)"

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._movie_path = ""
        self._thumb_path = ""
        self._subtitle_paths = []
        self._embedded_subs = []
        self._compression_worker = CompressionWorker()
        self._is_processing = False

        self.setWindowTitle("Add Movie \u2014 BebeFlix")
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("\U0001F3AC  Add a Movie")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #D81B60;")
        layout.addWidget(header)

        subtitle = QLabel("Add a new movie to your BebeFlix library")
        subtitle.setStyleSheet("font-size: 12px; color: #9E9E9E; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Title:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter movie title...")
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("Movie File:"))
        movie_row = QHBoxLayout()
        self.movie_path_label = QLabel("No file selected")
        self.movie_path_label.setObjectName("subtitleLabel")
        self.movie_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        movie_row.addWidget(self.movie_path_label)
        self.movie_browse_btn = QPushButton("Browse...")
        self.movie_browse_btn.clicked.connect(self._browse_movie)
        movie_row.addWidget(self.movie_browse_btn)
        layout.addLayout(movie_row)

        layout.addWidget(QLabel("Poster / Thumbnail:"))
        thumb_row = QHBoxLayout()
        self.thumb_path_label = QLabel("No file selected")
        self.thumb_path_label.setObjectName("subtitleLabel")
        self.thumb_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        thumb_row.addWidget(self.thumb_path_label)
        self.thumb_browse_btn = QPushButton("Browse...")
        self.thumb_browse_btn.clicked.connect(self._browse_thumbnail)
        thumb_row.addWidget(self.thumb_browse_btn)
        layout.addLayout(thumb_row)

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
        layout.addWidget(sub_group)

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

    def _browse_subtitles(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Subtitle Files", "", self.SUBTITLE_EXTENSIONS)
        if paths:
            self._subtitle_paths = paths
            self.sub_path_label.setText(", ".join(os.path.basename(p) for p in paths))

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

    def _validate(self):
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "Missing Title", "Please enter a movie title.")
            return False
        if not self._movie_path or not os.path.exists(self._movie_path):
            QMessageBox.warning(self, "Missing Movie", "Please select a valid movie file.")
            return False
        if not self._thumb_path or not os.path.exists(self._thumb_path):
            QMessageBox.warning(self, "Missing Thumbnail", "Please select a poster/thumbnail image.")
            return False
        try:
            file_size = os.path.getsize(self._movie_path)
            free_space = get_drive_free_space()
            if file_size > free_space:
                QMessageBox.warning(self, "Insufficient Space",
                    f"The movie file ({format_file_size(file_size)}) exceeds "
                    f"available drive space ({format_file_size(free_space)}).")
                return False
        except Exception:
            pass
        return True

    def _on_add(self):
        if self._is_processing or not self._validate():
            return
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
            "title": title, "rel_movie": rel_movie, "rel_thumb": rel_thumb,
            "subtitle_entries": subtitle_entries, "movie_dir": movie_dir
        }
        self._compression_worker.compress(
            self._movie_path, movie_dest, preset_key,
            on_progress=self._on_progress, on_complete=self._on_compression_complete
        )

    @Slot(float)
    def _on_progress(self, percent):
        QTimer.singleShot(0, lambda: self._update_progress(percent))

    def _update_progress(self, percent):
        self.progress_bar.setValue(int(percent))
        if percent < 100:
            self.status_label.setText(f"Processing: {percent:.1f}%")

    @Slot(bool, str)
    def _on_compression_complete(self, success, message):
        QTimer.singleShot(0, lambda: self._finish_add(success, message))

    def _finish_add(self, success, message):
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
        self.status_label.setText("Movie added successfully! \U0001F389")
        self.movie_added.emit(movie_id)
        QTimer.singleShot(800, self.accept)

    def _on_cancel(self):
        if self._is_processing:
            self._compression_worker.cancel()
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
