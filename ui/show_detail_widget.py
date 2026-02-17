"""
Show detail widget for BebeFlix.
Displays seasons and episodes for a TV show, with ability to add more seasons.
"""

import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QScrollArea, QFrame,
                                QSizePolicy, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor

from database import Show, Episode, Database
from utils.paths import get_library_root


class EpisodeRow(QFrame):
    """A clickable row representing a single episode."""
    clicked = Signal(Episode)

    def __init__(self, episode: Episode, parent=None):
        super().__init__(parent)
        self.episode = episode
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52)
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF; border: 1px solid #F0F0F0;
                border-radius: 8px; margin: 2px 0px;
            }
            QFrame:hover { background-color: #FFF0F5; border-color: #F48FB1; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        ep_num = QLabel(f"E{episode.episode_number}")
        ep_num.setFixedWidth(40)
        ep_num.setStyleSheet("font-size: 14px; font-weight: 700; color: #D81B60;")
        layout.addWidget(ep_num)

        title = episode.title or f"Episode {episode.episode_number}"
        ep_title = QLabel(title)
        ep_title.setStyleSheet("font-size: 14px; color: #2C2C2C;")
        layout.addWidget(ep_title)

        layout.addStretch()

        if episode.last_position > 0 and episode.duration > 0:
            pct = int((episode.last_position / episode.duration) * 100)
            progress = QLabel(f"{pct}%")
            progress.setStyleSheet("font-size: 11px; color: #9E9E9E;")
            layout.addWidget(progress)
        elif episode.last_position > 0:
            resume = QLabel("Resume")
            resume.setStyleSheet("font-size: 11px; color: #EC407A; font-weight: 600;")
            layout.addWidget(resume)

        play_label = QLabel(">>")
        play_label.setStyleSheet("font-size: 14px; color: #F48FB1;")
        layout.addWidget(play_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.episode)
        super().mousePressEvent(event)


class ShowDetailWidget(QWidget):
    """Full-page view for a TV show's seasons and episodes."""
    back_requested = Signal()
    play_episode = Signal(Episode, str)  # episode, show_title
    add_season_requested = Signal(Show)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.show = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-bottom: 2px solid #F8BBD0;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(16)

        self.back_btn = QPushButton("<- Library")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #D81B60; border: 2px solid #F8BBD0;
                border-radius: 16px; padding: 6px 14px; font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background-color: #FCE4EC; border-color: #EC407A; }
        """)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.back_btn)

        self.show_title_label = QLabel("")
        self.show_title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #C2185B; background: transparent;")
        header_layout.addWidget(self.show_title_label)

        header_layout.addStretch()

        self.add_season_btn = QPushButton("+ Add Season")
        self.add_season_btn.setCursor(Qt.PointingHandCursor)
        self.add_season_btn.setStyleSheet("""
            QPushButton {
                background-color: #EC407A; color: #FFFFFF; border: none;
                border-radius: 16px; padding: 8px 22px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #D81B60; }
        """)
        self.add_season_btn.clicked.connect(self._on_add_season)
        header_layout.addWidget(self.add_season_btn)

        layout.addWidget(header)

        # Scrollable content
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: #FAFAFA; }")
        layout.addWidget(self.scroll)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(32, 24, 32, 24)
        self.content_layout.setSpacing(24)
        self.scroll.setWidget(self.content)

    def load_show(self, show: Show):
        self.show = show
        self.show_title_label.setText(show.title)

        # Clear old content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not show.seasons:
            empty = QLabel("No seasons yet. Click '+ Add Season' to get started.")
            empty.setStyleSheet("font-size: 14px; color: #9E9E9E; padding: 40px;")
            empty.setAlignment(Qt.AlignCenter)
            self.content_layout.addWidget(empty)
        else:
            for season in show.seasons:
                self._add_season_section(season)

        self.content_layout.addStretch()

    def _add_season_section(self, season):
        """Add a season header + episode list."""
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(8)

        # Season header
        header = QLabel(f"Season {season.season_number}")
        header.setStyleSheet("""
            font-size: 16px; font-weight: 700; color: #D81B60;
            padding: 8px 0px; border-bottom: 1px solid #F8BBD0;
        """)
        section_layout.addWidget(header)

        ep_count = QLabel(f"{len(season.episodes)} episode{'s' if len(season.episodes) != 1 else ''}")
        ep_count.setStyleSheet("font-size: 12px; color: #9E9E9E; margin-bottom: 4px;")
        section_layout.addWidget(ep_count)

        # Episode rows
        if not season.episodes:
            empty = QLabel("No episodes in this season.")
            empty.setStyleSheet("font-size: 13px; color: #BDBDBD; padding: 12px 0;")
            section_layout.addWidget(empty)
        else:
            for ep in season.episodes:
                row = EpisodeRow(ep)
                row.clicked.connect(lambda e, s=self.show: self.play_episode.emit(e, s.title))
                section_layout.addWidget(row)

        self.content_layout.addWidget(section)

    def _on_add_season(self):
        if self.show:
            self.add_season_requested.emit(self.show)
