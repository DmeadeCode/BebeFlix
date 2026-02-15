"""
Main window for BebeFlix.
Contains the library browser grid and manages navigation to the player.
"""

import os
import shutil
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QLineEdit, QPushButton, QComboBox,
                                QScrollArea, QGridLayout, QStackedWidget,
                                QMessageBox, QFrame, QSizePolicy,
                                QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, QTimer, Slot, QSize
from PySide6.QtGui import QFont, QColor

from database import Database, Movie
from ui.movie_card import MovieCard, POSTER_WIDTH
from ui.player_widget import PlayerWidget
from ui.add_movie_dialog import AddMovieDialog
from utils.paths import get_library_root


class FlowLayout(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(20)
        self._layout.setContentsMargins(24, 16, 24, 24)
        self._layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._cards = []
        self._columns = 4

    def clear(self):
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def add_card(self, card: MovieCard):
        self._cards.append(card)
        self._rearrange()

    def _rearrange(self):
        parent = self.parentWidget()
        if parent:
            avail_width = parent.width() - 60
            card_width = POSTER_WIDTH + 30
            self._columns = max(2, avail_width // card_width)
        for i, card in enumerate(self._cards):
            row = i // self._columns
            col = i % self._columns
            self._layout.addWidget(card, row, col, Qt.AlignTop | Qt.AlignHCenter)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rearrange()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BebeFlix")
        self.setMinimumSize(900, 600)
        self.resize(1200, 800)
        self.setContentsMargins(0, 0, 0, 0)

        self.db = Database()
        self._sort_by = "date_added"
        self._sort_ascending = False
        self._search_query = ""

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._setup_library_page()
        self._setup_player_page()
        self._refresh_library()

    def _setup_library_page(self):
        library_page = QWidget()
        library_page.setStyleSheet("background-color: #FFFFFF;")
        layout = QVBoxLayout(library_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Compact header toolbar
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

        title_label = QLabel("\U0001F380 BebeFlix")
        title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #C2185B; background: transparent;")
        header_layout.addWidget(title_label)

        self.count_label = QLabel("0 movies")
        self.count_label.setStyleSheet("""
            font-size: 12px; color: #D81B60; font-weight: 600;
            background: #FCE4EC; padding: 4px 14px; border-radius: 12px;
        """)
        header_layout.addWidget(self.count_label)

        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("\U0001F50D  Search movies...")
        self.search_input.setFixedWidth(260)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #F5F5F5; color: #2C2C2C;
                border: 2px solid #E0E0E0; border-radius: 18px;
                padding: 7px 18px; font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #F48FB1; background-color: #FFFFFF; }
            QLineEdit::placeholder { color: #BDBDBD; }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self.search_input)

        sort_label = QLabel("Sort:")
        sort_label.setStyleSheet("color: #9E9E9E; font-weight: 600; font-size: 12px; background: transparent;")
        header_layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background-color: #F5F5F5; border: 2px solid #E0E0E0;
                border-radius: 14px; padding: 5px 14px; min-width: 130px; font-size: 12px;
            }
            QComboBox:hover { border-color: #F48FB1; }
        """)
        self.sort_combo.addItem("Newest First", ("date_added", False))
        self.sort_combo.addItem("Oldest First", ("date_added", True))
        self.sort_combo.addItem("Title A \u2192 Z", ("title", True))
        self.sort_combo.addItem("Title Z \u2192 A", ("title", False))
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        header_layout.addWidget(self.sort_combo)

        self.add_btn = QPushButton("\u2795  Add Movie")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #EC407A; color: #FFFFFF; border: none;
                border-radius: 16px; padding: 8px 22px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #D81B60; }
            QPushButton:pressed { background-color: #C2185B; }
        """)
        self.add_btn.clicked.connect(self._on_add_movie)
        header_layout.addWidget(self.add_btn)
        layout.addWidget(header)

        # Scrollable movie grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #FFFFFF; }")

        self.grid_container = FlowLayout()
        self.grid_container.setStyleSheet("background-color: #FFFFFF;")
        self.scroll_area.setWidget(self.grid_container)
        layout.addWidget(self.scroll_area)

        # Empty state
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)

        empty_icon = QLabel("\U0001F3AC")
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setStyleSheet("font-size: 64px; background: transparent;")
        empty_layout.addWidget(empty_icon)

        self.empty_label = QLabel("Your library is empty!")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #EC407A; background: transparent; margin-top: 8px;")
        empty_layout.addWidget(self.empty_label)

        self.empty_subtitle = QLabel("Click \"\u2795 Add Movie\" to get started")
        self.empty_subtitle.setAlignment(Qt.AlignCenter)
        self.empty_subtitle.setStyleSheet("font-size: 14px; color: #9E9E9E; background: transparent; margin-top: 4px;")
        empty_layout.addWidget(self.empty_subtitle)

        self.empty_widget.setVisible(False)
        layout.addWidget(self.empty_widget)
        self.stack.addWidget(library_page)

    def _setup_player_page(self):
        self.player = PlayerWidget(self.db)
        self.player.back_requested.connect(self._show_library)
        self.stack.addWidget(self.player)

    def _refresh_library(self):
        self.grid_container.clear()
        if self._search_query:
            movies = self.db.search_movies(self._search_query, self._sort_by, self._sort_ascending)
        else:
            movies = self.db.get_all_movies(self._sort_by, self._sort_ascending)

        if not movies:
            self.empty_widget.setVisible(True)
            self.scroll_area.setVisible(False)
            if self._search_query:
                self.empty_label.setText(f"No results for \"{self._search_query}\"")
                self.empty_subtitle.setText("Try a different search term")
            else:
                self.empty_label.setText("Your library is empty!")
                self.empty_subtitle.setText("Click \"\u2795 Add Movie\" to get started")
        else:
            self.empty_widget.setVisible(False)
            self.scroll_area.setVisible(True)
            for movie in movies:
                card = MovieCard(movie)
                card.clicked.connect(self._on_movie_clicked)
                card.delete_requested.connect(self._on_delete_requested)
                self.grid_container.add_card(card)

        total = self.db.get_movie_count()
        showing = len(movies)
        if self._search_query:
            self.count_label.setText(f"{showing} of {total} movies")
        else:
            self.count_label.setText(f"{total} movie{'s' if total != 1 else ''}")

    @Slot()
    def _on_search_changed(self):
        self._search_query = self.search_input.text().strip()
        if not hasattr(self, '_search_timer'):
            self._search_timer = QTimer(self)
            self._search_timer.setSingleShot(True)
            self._search_timer.timeout.connect(self._refresh_library)
        self._search_timer.start(200)

    @Slot(int)
    def _on_sort_changed(self, index):
        data = self.sort_combo.currentData()
        if data:
            self._sort_by, self._sort_ascending = data
            self._refresh_library()

    @Slot(Movie)
    def _on_movie_clicked(self, movie):
        self.stack.setCurrentIndex(1)
        self.player.load_movie(movie)

    @Slot(Movie)
    def _on_delete_requested(self, movie):
        reply = QMessageBox.question(
            self, "Delete Movie",
            f"Are you sure you want to permanently delete \"{movie.title}\"?\n\n"
            f"This will remove the movie file and all associated data.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._delete_movie(movie)

    def _delete_movie(self, movie):
        deleted = self.db.delete_movie(movie.id)
        if not deleted:
            return
        movie_abs = os.path.join(get_library_root(), movie.movie_path)
        movie_dir = os.path.dirname(movie_abs)
        try:
            if os.path.exists(movie_dir):
                shutil.rmtree(movie_dir)
        except Exception as e:
            QMessageBox.warning(self, "Warning",
                f"Movie removed from library but some files could not be deleted:\n{e}")
        self._refresh_library()

    @Slot()
    def _on_add_movie(self):
        dialog = AddMovieDialog(self.db, self)
        dialog.movie_added.connect(lambda _: self._refresh_library())
        dialog.exec()

    @Slot()
    def _show_library(self):
        self.stack.setCurrentIndex(0)
        self._refresh_library()

    def closeEvent(self, event):
        self.player.cleanup()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'grid_container'):
            self.grid_container._rearrange()
