"""
Card widget for the library grid.
Supports both movies and TV shows, with progress bars and rename.
"""

import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                                QGraphicsDropShadowEffect, QMenu, QFrame)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QCursor, QAction, QColor

from database import Movie, Show
from utils.paths import get_library_root

POSTER_WIDTH = 180
POSTER_HEIGHT = 270


class MovieCard(QWidget):
    clicked = Signal(Movie)
    delete_requested = Signal(Movie)
    rename_requested = Signal(Movie)

    def __init__(self, movie: Movie, parent=None):
        super().__init__(parent)
        self.movie = movie
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(POSTER_WIDTH + 10, POSTER_HEIGHT + 65)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setToolTip(f"Click to play: {self.movie.title}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        # Poster container
        poster_container = QWidget()
        poster_container.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        poster_container.setStyleSheet("background: transparent;")
        poster_inner = QVBoxLayout(poster_container)
        poster_inner.setContentsMargins(0, 0, 0, 0)
        poster_inner.setSpacing(0)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT - 4)
        self.poster_label.setAlignment(Qt.AlignCenter)
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 10px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }")
        self._load_thumbnail()
        poster_inner.addWidget(self.poster_label)

        # Progress bar at bottom of poster
        self.progress_bar = QFrame()
        self.progress_bar.setFixedHeight(4)
        self._update_progress()
        poster_inner.addWidget(self.progress_bar)

        layout.addWidget(poster_container, alignment=Qt.AlignCenter)

        self.title_label = QLabel(self.movie.title)
        self.title_label.setObjectName("movieTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumWidth(POSTER_WIDTH)
        self.title_label.setMaximumHeight(54)
        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(244, 143, 177, 80))
        self.poster_label.setGraphicsEffect(shadow)

    def _update_progress(self):
        if self.movie.duration > 0 and self.movie.last_position > 0:
            pct = min(self.movie.last_position / self.movie.duration, 1.0) * 100
            self.progress_bar.setStyleSheet(
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                f"stop:0 #EC407A, stop:{pct/100:.3f} #EC407A, "
                f"stop:{pct/100 + 0.001:.3f} #40404040, stop:1 #40404040); "
                f"border: none; border-radius: 2px;")
        else:
            self.progress_bar.setStyleSheet("background-color: transparent; border: none;")

    def _load_thumbnail(self):
        thumb_abs = os.path.join(get_library_root(), self.movie.thumb_path)
        if os.path.exists(thumb_abs):
            pixmap = QPixmap(thumb_abs)
            if not pixmap.isNull():
                scaled = pixmap.scaled(POSTER_WIDTH, POSTER_HEIGHT,
                    Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                if scaled.width() > POSTER_WIDTH or scaled.height() > POSTER_HEIGHT:
                    x = (scaled.width() - POSTER_WIDTH) // 2
                    y = (scaled.height() - POSTER_HEIGHT) // 2
                    scaled = scaled.copy(x, y, POSTER_WIDTH, POSTER_HEIGHT)
                self.poster_label.setPixmap(scaled)
                return

        self.poster_label.setText(self.movie.title)
        self.poster_label.setStyleSheet("""
            QLabel {
                border-radius: 10px; background-color: #FCE4EC; color: #C2185B;
                font-size: 14px; font-weight: bold; padding: 20px; border: 2px solid #F8BBD0;
            }
        """)

    def enterEvent(self, event):
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 10px; background-color: #F5F5F5; border: 3px solid #F48FB1; }")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 10px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.movie)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self.rename_requested.emit(self.movie))
        menu.addAction(rename_action)
        menu.addSeparator()
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.movie))
        menu.addAction(delete_action)
        menu.exec(event.globalPos())


class ShowCard(QWidget):
    """Card for a TV show in the grid."""
    clicked = Signal(Show)
    delete_requested = Signal(Show)
    rename_requested = Signal(Show)

    def __init__(self, show: Show, parent=None):
        super().__init__(parent)
        self.show = show
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(POSTER_WIDTH + 10, POSTER_HEIGHT + 65)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        ep_count = sum(len(s.episodes) for s in self.show.seasons)
        self.setToolTip(
            f"{self.show.title}\n"
            f"{len(self.show.seasons)} season(s), {ep_count} episode(s)"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        self.poster_label.setAlignment(Qt.AlignCenter)
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 10px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }")
        self._load_thumbnail()
        layout.addWidget(self.poster_label, alignment=Qt.AlignCenter)

        self.title_label = QLabel(self.show.title)
        self.title_label.setObjectName("movieTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumWidth(POSTER_WIDTH)
        self.title_label.setMaximumHeight(54)
        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(244, 143, 177, 80))
        self.poster_label.setGraphicsEffect(shadow)

    def _load_thumbnail(self):
        thumb_abs = os.path.join(get_library_root(), self.show.thumb_path)
        if os.path.exists(thumb_abs):
            pixmap = QPixmap(thumb_abs)
            if not pixmap.isNull():
                scaled = pixmap.scaled(POSTER_WIDTH, POSTER_HEIGHT,
                    Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                if scaled.width() > POSTER_WIDTH or scaled.height() > POSTER_HEIGHT:
                    x = (scaled.width() - POSTER_WIDTH) // 2
                    y = (scaled.height() - POSTER_HEIGHT) // 2
                    scaled = scaled.copy(x, y, POSTER_WIDTH, POSTER_HEIGHT)
                self.poster_label.setPixmap(scaled)
                return

        self.poster_label.setText(f"{self.show.title}\n\n[TV Show]")
        self.poster_label.setStyleSheet("""
            QLabel {
                border-radius: 10px; background-color: #E8F5E9; color: #2E7D32;
                font-size: 14px; font-weight: bold; padding: 20px; border: 2px solid #A5D6A7;
            }
        """)

    def enterEvent(self, event):
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 10px; background-color: #F5F5F5; border: 3px solid #F48FB1; }")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 10px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.show)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self.rename_requested.emit(self.show))
        menu.addAction(rename_action)
        menu.addSeparator()
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.show))
        menu.addAction(delete_action)
        menu.exec(event.globalPos())


class ContinueCard(QWidget):
    """Smaller horizontal card for Continue Watching row."""
    clicked = Signal(dict)  # emits the full continue-watching dict

    def __init__(self, cw_item: dict, parent=None):
        super().__init__(parent)
        self.cw_item = cw_item
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(140, 220)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(132, 180)
        self.poster_label.setAlignment(Qt.AlignCenter)
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 8px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }")
        self._load_thumbnail()
        layout.addWidget(self.poster_label, alignment=Qt.AlignCenter)

        # Progress bar
        self.progress_bar = QFrame()
        self.progress_bar.setFixedHeight(3)
        self._update_progress()
        layout.addWidget(self.progress_bar)

        # Title
        item = self.cw_item["item"]
        if self.cw_item["type"] == "movie":
            label_text = item.title
            self.setToolTip(item.title)
        else:
            show_title = self.cw_item.get("show_title", "")
            label_text = f"S{self.cw_item.get('season_number', 0)}E{item.episode_number}"
            self.setToolTip(f"{show_title} - {label_text}: {item.title}")

        self.title_label = QLabel(label_text)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setMaximumWidth(132)
        self.title_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; background: transparent;")
        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)

    def _update_progress(self):
        item = self.cw_item["item"]
        if item.duration > 0 and item.last_position > 0:
            pct = min(item.last_position / item.duration, 1.0) * 100
            self.progress_bar.setStyleSheet(
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                f"stop:0 #EC407A, stop:{pct/100:.3f} #EC407A, "
                f"stop:{pct/100 + 0.001:.3f} #40404040, stop:1 #40404040); "
                f"border: none; border-radius: 1px;")
        else:
            self.progress_bar.setStyleSheet("background-color: transparent; border: none;")

    def _load_thumbnail(self):
        if self.cw_item["type"] == "movie":
            thumb_rel = self.cw_item["item"].thumb_path
        else:
            thumb_rel = self.cw_item.get("show_thumb", "")

        thumb_abs = os.path.join(get_library_root(), thumb_rel)
        if os.path.exists(thumb_abs):
            pixmap = QPixmap(thumb_abs)
            if not pixmap.isNull():
                scaled = pixmap.scaled(132, 180,
                    Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                if scaled.width() > 132 or scaled.height() > 180:
                    x = (scaled.width() - 132) // 2
                    y = (scaled.height() - 180) // 2
                    scaled = scaled.copy(x, y, 132, 180)
                self.poster_label.setPixmap(scaled)
                return

        item = self.cw_item["item"]
        if self.cw_item["type"] == "movie":
            self.poster_label.setText(item.title[:20])
        else:
            self.poster_label.setText(self.cw_item.get("show_title", "")[:20])
        self.poster_label.setStyleSheet("""
            QLabel {
                border-radius: 8px; background-color: #FCE4EC; color: #C2185B;
                font-size: 11px; font-weight: bold; padding: 10px; border: 2px solid #F8BBD0;
            }
        """)

    def enterEvent(self, event):
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 8px; background-color: #F5F5F5; border: 3px solid #F48FB1; }")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.poster_label.setStyleSheet(
            "QLabel { border-radius: 8px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.cw_item)
        super().mousePressEvent(event)
