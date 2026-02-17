"""
Card widget for the library grid.
Supports both movies and TV shows.
"""

import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                                QGraphicsDropShadowEffect, QMenu)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QCursor, QAction, QColor

from database import Movie, Show
from utils.paths import get_library_root

POSTER_WIDTH = 180
POSTER_HEIGHT = 270


class MovieCard(QWidget):
    clicked = Signal(Movie)
    delete_requested = Signal(Movie)

    def __init__(self, movie: Movie, parent=None):
        super().__init__(parent)
        self.movie = movie
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(POSTER_WIDTH + 10, POSTER_HEIGHT + 45)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setToolTip(f"Click to play: {self.movie.title}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        self.poster_label.setAlignment(Qt.AlignCenter)
        self.poster_label.setStyleSheet("""
            QLabel { border-radius: 10px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }
        """)
        self._load_thumbnail()
        layout.addWidget(self.poster_label, alignment=Qt.AlignCenter)

        self.title_label = QLabel(self.movie.title)
        self.title_label.setObjectName("movieTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumWidth(POSTER_WIDTH)
        self.title_label.setMaximumHeight(36)
        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(244, 143, 177, 80))
        self.poster_label.setGraphicsEffect(shadow)

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
        delete_action = QAction(f"Delete \"{self.movie.title}\"", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.movie))
        menu.addAction(delete_action)
        menu.exec(event.globalPos())


class ShowCard(QWidget):
    """Card for a TV show in the grid."""
    clicked = Signal(Show)
    delete_requested = Signal(Show)

    def __init__(self, show: Show, parent=None):
        super().__init__(parent)
        self.show = show
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(POSTER_WIDTH + 10, POSTER_HEIGHT + 45)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        ep_count = sum(len(s.episodes) for s in self.show.seasons)
        self.setToolTip(
            f"{self.show.title}\n"
            f"{len(self.show.seasons)} season(s), {ep_count} episode(s)"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        self.poster_label.setAlignment(Qt.AlignCenter)
        self.poster_label.setStyleSheet("""
            QLabel { border-radius: 10px; background-color: #F5F5F5; border: 2px solid #F0F0F0; }
        """)
        self._load_thumbnail()
        layout.addWidget(self.poster_label, alignment=Qt.AlignCenter)

        # Title with "TV" badge
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        self.title_label = QLabel(self.show.title)
        self.title_label.setObjectName("movieTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumWidth(POSTER_WIDTH)
        self.title_label.setMaximumHeight(36)
        title_layout.addWidget(self.title_label)

        layout.addWidget(title_widget, alignment=Qt.AlignCenter)

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
        delete_action = QAction(f"Delete \"{self.show.title}\"", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.show))
        menu.addAction(delete_action)
        menu.exec(event.globalPos())
