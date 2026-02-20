"""
Main window for BebeFlix.
Contains the library browser grid with continue watching section,
dark mode toggle, and manages navigation to player and show detail.
"""

import os
import shutil
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QLineEdit, QPushButton, QComboBox,
                                QScrollArea, QGridLayout, QStackedWidget,
                                QMessageBox, QFrame, QSizePolicy,
                                QGraphicsDropShadowEffect, QInputDialog)
from PySide6.QtCore import Qt, QTimer, Slot, QSize
from PySide6.QtGui import QFont, QColor

from database import Database, Movie, Show, Episode
from ui.movie_card import MovieCard, ShowCard, ContinueCard, POSTER_WIDTH
from ui.player_widget import PlayerWidget
from ui.add_movie_dialog import AddMovieDialog
from ui.show_detail_widget import ShowDetailWidget
from ui.styles import LIGHT_THEME, DARK_THEME
from utils.paths import get_library_root, get_movies_dir


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

    def add_card(self, card):
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
    # Stack indices
    PAGE_LIBRARY = 0
    PAGE_PLAYER = 1
    PAGE_SHOW_DETAIL = 2

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
        self._dark_mode = self.db.get_setting("dark_mode", "0") == "1"

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._setup_library_page()
        self._setup_player_page()
        self._setup_show_detail_page()
        self._apply_theme()
        self._refresh_library()

    def _apply_theme(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if self._dark_mode:
            app.setStyleSheet(DARK_THEME)
            self.dark_mode_btn.setText("Light")
        else:
            app.setStyleSheet(LIGHT_THEME)
            self.dark_mode_btn.setText("Dark")

    def _toggle_dark_mode(self):
        self._dark_mode = not self._dark_mode
        self.db.set_setting("dark_mode", "1" if self._dark_mode else "0")
        self._apply_theme()
        self._refresh_library()

    def _setup_library_page(self):
        library_page = QWidget()
        layout = QVBoxLayout(library_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Compact header toolbar
        header = QWidget()
        header.setFixedHeight(56)
        header.setObjectName("libraryHeader")
        header.setStyleSheet("""
            QWidget#libraryHeader {
                border-bottom: 2px solid #F8BBD0;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(12)

        title_label = QLabel("BebeFlix")
        title_label.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #C2185B; background: transparent;")
        header_layout.addWidget(title_label)

        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet("""
            font-size: 12px; color: #D81B60; font-weight: 600;
            background: #FCE4EC; padding: 4px 14px; border-radius: 12px;
        """)
        header_layout.addWidget(self.count_label)

        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search library...")
        self.search_input.setFixedWidth(240)
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
        sort_label.setStyleSheet(
            "color: #9E9E9E; font-weight: 600; font-size: 12px; background: transparent;")
        header_layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background-color: #F5F5F5; border: 2px solid #E0E0E0;
                border-radius: 14px; padding: 5px 14px; min-width: 120px; font-size: 12px;
            }
            QComboBox:hover { border-color: #F48FB1; }
        """)
        self.sort_combo.addItem("Newest First", ("date_added", False))
        self.sort_combo.addItem("Oldest First", ("date_added", True))
        self.sort_combo.addItem("Title A -> Z", ("title", True))
        self.sort_combo.addItem("Title Z -> A", ("title", False))
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        header_layout.addWidget(self.sort_combo)

        # Dark mode toggle
        self.dark_mode_btn = QPushButton("Dark")
        self.dark_mode_btn.setCursor(Qt.PointingHandCursor)
        self.dark_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5; color: #757575; border: 2px solid #E0E0E0;
                border-radius: 14px; padding: 6px 14px; font-size: 12px; font-weight: 600;
                min-width: 50px;
            }
            QPushButton:hover { border-color: #F48FB1; color: #D81B60; }
        """)
        self.dark_mode_btn.clicked.connect(self._toggle_dark_mode)
        header_layout.addWidget(self.dark_mode_btn)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #EC407A; color: #FFFFFF; border: none;
                border-radius: 16px; padding: 8px 22px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #D81B60; }
            QPushButton:pressed { background-color: #C2185B; }
        """)
        self.add_btn.clicked.connect(self._on_add_content)
        header_layout.addWidget(self.add_btn)
        layout.addWidget(header)

        # Main scroll area (contains continue watching + grid)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)

        # Continue Watching section
        self.cw_section = QWidget()
        cw_layout = QVBoxLayout(self.cw_section)
        cw_layout.setContentsMargins(24, 16, 24, 0)
        cw_layout.setSpacing(8)

        cw_header = QLabel("Continue Watching")
        cw_header.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #C2185B; background: transparent;")
        cw_layout.addWidget(cw_header)

        self.cw_scroll = QScrollArea()
        self.cw_scroll.setFixedHeight(240)
        self.cw_scroll.setWidgetResizable(True)
        self.cw_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cw_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cw_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cw_container = QWidget()
        self.cw_container.setStyleSheet("background: transparent;")
        self.cw_row_layout = QHBoxLayout(self.cw_container)
        self.cw_row_layout.setContentsMargins(0, 0, 0, 0)
        self.cw_row_layout.setSpacing(12)
        self.cw_row_layout.setAlignment(Qt.AlignLeft)
        self.cw_scroll.setWidget(self.cw_container)
        cw_layout.addWidget(self.cw_scroll)

        cw_divider = QFrame()
        cw_divider.setFixedHeight(1)
        cw_divider.setStyleSheet("background-color: #F0F0F0; border: none;")
        cw_layout.addWidget(cw_divider)

        self.cw_section.setVisible(False)
        self.scroll_layout.addWidget(self.cw_section)

        # Library label
        self.library_section_label = QLabel("Library")
        self.library_section_label.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #C2185B; "
            "background: transparent; padding: 16px 24px 4px 24px;")
        self.library_section_label.setVisible(False)
        self.scroll_layout.addWidget(self.library_section_label)

        # Grid
        self.grid_container = FlowLayout()
        self.scroll_layout.addWidget(self.grid_container)
        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(scroll_content)
        layout.addWidget(self.scroll_area)

        # Empty state
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)

        empty_icon = QLabel("(empty)")
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setStyleSheet("font-size: 48px; background: transparent; color: #E0E0E0;")
        empty_layout.addWidget(empty_icon)

        self.empty_label = QLabel("Your library is empty!")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #EC407A; "
            "background: transparent; margin-top: 8px;")
        empty_layout.addWidget(self.empty_label)

        self.empty_subtitle = QLabel("Click '+ Add' to add movies or TV shows")
        self.empty_subtitle.setAlignment(Qt.AlignCenter)
        self.empty_subtitle.setStyleSheet(
            "font-size: 14px; color: #9E9E9E; background: transparent; margin-top: 4px;")
        empty_layout.addWidget(self.empty_subtitle)

        self.empty_widget.setVisible(False)
        layout.addWidget(self.empty_widget)
        self.stack.addWidget(library_page)

    def _setup_player_page(self):
        self.player = PlayerWidget(self.db)
        self.player.back_requested.connect(self._show_library)
        self.stack.addWidget(self.player)

    def _setup_show_detail_page(self):
        self.show_detail = ShowDetailWidget(self.db)
        self.show_detail.back_requested.connect(self._show_library)
        self.show_detail.play_episode.connect(self._on_play_episode)
        self.show_detail.add_season_requested.connect(self._on_add_season)
        self.stack.addWidget(self.show_detail)

    # ---- Continue Watching -----------------------------------------------------------------------

    def _refresh_continue_watching(self):
        # Clear existing cards
        while self.cw_row_layout.count():
            item = self.cw_row_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cw_items = self.db.get_continue_watching()
        if not cw_items:
            self.cw_section.setVisible(False)
            self.library_section_label.setVisible(False)
            return

        self.cw_section.setVisible(True)
        self.library_section_label.setVisible(True)

        for cw_item in cw_items:
            card = ContinueCard(cw_item)
            card.clicked.connect(self._on_continue_clicked)
            self.cw_row_layout.addWidget(card)

    @Slot(dict)
    def _on_continue_clicked(self, cw_item):
        if cw_item["type"] == "movie":
            movie = cw_item["item"]
            # Refresh from DB for latest position
            fresh = self.db.get_movie(movie.id)
            if fresh:
                self.stack.setCurrentIndex(self.PAGE_PLAYER)
                self.player.load_movie(fresh)
        else:
            # Episode - load the show, then play the episode
            ep = cw_item["item"]
            show_id = cw_item.get("show_id")
            show_title = cw_item.get("show_title", "")
            show = self.db.get_show(show_id) if show_id else None

            episode_list = []
            ep_index = -1
            if show:
                for season in show.seasons:
                    for s_ep in season.episodes:
                        if s_ep.id == ep.id:
                            ep_index = len(episode_list)
                        episode_list.append(s_ep)

            self.stack.setCurrentIndex(self.PAGE_PLAYER)
            # Use the fresh episode from the show data if available
            fresh_ep = episode_list[ep_index] if 0 <= ep_index < len(episode_list) else ep
            self.player.load_episode(fresh_ep, show_title, episode_list, ep_index)

    # ---- Library Refresh -------------------------------------------------------------------------

    def _refresh_library(self):
        self._refresh_continue_watching()
        self.grid_container.clear()

        if self._search_query:
            movies = self.db.search_movies(
                self._search_query, self._sort_by, self._sort_ascending)
            shows = self.db.search_shows(
                self._search_query, self._sort_by, self._sort_ascending)
        else:
            movies = self.db.get_all_movies(self._sort_by, self._sort_ascending)
            shows = self.db.get_all_shows(self._sort_by, self._sort_ascending)

        # Merge and sort together
        items = []
        for m in movies:
            items.append(("movie", m, m.date_added, m.title))
        for s in shows:
            items.append(("show", s, s.date_added, s.title))

        if self._sort_by == "title":
            items.sort(key=lambda x: x[3].lower(), reverse=not self._sort_ascending)
        else:
            items.sort(key=lambda x: x[2] or "", reverse=not self._sort_ascending)

        total_items = len(items)

        if not items:
            self.empty_widget.setVisible(True)
            self.scroll_area.setVisible(False)
            if self._search_query:
                self.empty_label.setText(f"No results for \"{self._search_query}\"")
                self.empty_subtitle.setText("Try a different search term")
            else:
                self.empty_label.setText("Your library is empty!")
                self.empty_subtitle.setText("Click '+ Add' to add movies or TV shows")
        else:
            self.empty_widget.setVisible(False)
            self.scroll_area.setVisible(True)
            for kind, item, _, _ in items:
                if kind == "movie":
                    card = MovieCard(item)
                    card.clicked.connect(self._on_movie_clicked)
                    card.delete_requested.connect(self._on_delete_movie)
                    card.rename_requested.connect(self._on_rename_movie)
                    self.grid_container.add_card(card)
                else:
                    card = ShowCard(item)
                    card.clicked.connect(self._on_show_clicked)
                    card.delete_requested.connect(self._on_delete_show)
                    card.rename_requested.connect(self._on_rename_show)
                    self.grid_container.add_card(card)

        movie_count = self.db.get_movie_count()
        show_count = self.db.get_show_count()
        parts = []
        if movie_count:
            parts.append(f"{movie_count} movie{'s' if movie_count != 1 else ''}")
        if show_count:
            parts.append(f"{show_count} show{'s' if show_count != 1 else ''}")
        if self._search_query:
            self.count_label.setText(
                f"{total_items} result{'s' if total_items != 1 else ''}")
        else:
            self.count_label.setText(", ".join(parts) if parts else "Empty")

    # ---- Event Handlers --------------------------------------------------------------------------

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
        self.stack.setCurrentIndex(self.PAGE_PLAYER)
        self.player.load_movie(movie)

    @Slot(Show)
    def _on_show_clicked(self, show):
        self.show_detail.load_show(show)
        self.stack.setCurrentIndex(self.PAGE_SHOW_DETAIL)

    @Slot(Episode, str)
    def _on_play_episode(self, episode, show_title):
        episode_list = []
        ep_index = -1
        show = self.show_detail.show
        if show:
            for season in show.seasons:
                for ep in season.episodes:
                    if ep.id == episode.id:
                        ep_index = len(episode_list)
                    episode_list.append(ep)
        self.stack.setCurrentIndex(self.PAGE_PLAYER)
        self.player.load_episode(episode, show_title, episode_list, ep_index)

    @Slot(Show)
    def _on_add_season(self, show):
        next_season = self.db.get_next_season_number(show.id)
        dialog = AddMovieDialog(
            self.db, self, mode="show",
            existing_show=show, season_number=next_season
        )
        dialog.show_added.connect(lambda _: self._on_show_updated(show.id))
        dialog.exec()

    def _on_show_updated(self, show_id):
        show = self.db.get_show(show_id)
        if show:
            self.show_detail.load_show(show)
        self._refresh_library()

    # ---- Rename ----------------------------------------------------------------------------------

    @Slot(Movie)
    def _on_rename_movie(self, movie):
        new_title, ok = QInputDialog.getText(
            self, "Rename Movie", "New title:", text=movie.title
        )
        if ok and new_title.strip():
            self.db.rename_movie(movie.id, new_title.strip())
            self._refresh_library()

    @Slot(Show)
    def _on_rename_show(self, show):
        new_title, ok = QInputDialog.getText(
            self, "Rename Show", "New title:", text=show.title
        )
        if ok and new_title.strip():
            self.db.rename_show(show.id, new_title.strip())
            self._refresh_library()

    # ---- Delete ----------------------------------------------------------------------------------

    @Slot(Movie)
    def _on_delete_movie(self, movie):
        reply = QMessageBox.question(
            self, "Delete Movie",
            f"Are you sure you want to permanently delete \"{movie.title}\"?\n\n"
            f"This will remove the movie file and all associated data.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            deleted = self.db.delete_movie(movie.id)
            if deleted:
                movie_abs = os.path.join(get_library_root(), movie.movie_path)
                movie_dir = os.path.dirname(movie_abs)
                try:
                    if os.path.exists(movie_dir):
                        shutil.rmtree(movie_dir)
                except Exception as e:
                    QMessageBox.warning(self, "Warning",
                        f"Removed from library but some files could not be deleted:\n{e}")
            self._refresh_library()

    @Slot(Show)
    def _on_delete_show(self, show):
        ep_count = sum(len(s.episodes) for s in show.seasons)
        reply = QMessageBox.question(
            self, "Delete Show",
            f"Are you sure you want to permanently delete \"{show.title}\"?\n\n"
            f"This will remove {len(show.seasons)} season(s) and {ep_count} episode(s).",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            dirs_to_delete = set()
            for season in show.seasons:
                for ep in season.episodes:
                    ep_abs = os.path.join(get_library_root(), ep.movie_path)
                    dirs_to_delete.add(os.path.dirname(ep_abs))

            if show.thumb_path:
                thumb_abs = os.path.join(get_library_root(), show.thumb_path)
                dirs_to_delete.add(os.path.dirname(thumb_abs))

            self.db.delete_show(show.id)

            for d in dirs_to_delete:
                try:
                    if os.path.exists(d):
                        shutil.rmtree(d)
                except Exception:
                    pass

            show_slug_dir = os.path.join(
                get_movies_dir(), show.title.lower().replace(" ", "-"))
            try:
                if os.path.isdir(show_slug_dir) and not os.listdir(show_slug_dir):
                    os.rmdir(show_slug_dir)
            except Exception:
                pass

            self._refresh_library()

    @Slot()
    def _on_add_content(self):
        dialog = AddMovieDialog(self.db, self)
        dialog.movie_added.connect(lambda _: self._refresh_library())
        dialog.show_added.connect(lambda _: self._refresh_library())
        dialog.exec()

    @Slot()
    def _show_library(self):
        self.stack.setCurrentIndex(self.PAGE_LIBRARY)
        self._refresh_library()

    def closeEvent(self, event):
        self.player.cleanup()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'grid_container'):
            self.grid_container._rearrange()
