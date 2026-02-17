"""
Database layer for BebeFlix catalog.
Uses SQLite for zero-dependency portable storage.
Supports both movies and TV shows.
"""

import sqlite3
import os
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

from utils.paths import get_db_path


@dataclass
class Movie:
    """Represents a movie in the catalog."""
    id: int = 0
    title: str = ""
    movie_path: str = ""
    thumb_path: str = ""
    date_added: str = ""
    last_position: float = 0.0
    duration: float = 0.0
    subtitle_paths: list = field(default_factory=list)


@dataclass
class Episode:
    """Represents a single TV show episode."""
    id: int = 0
    season_id: int = 0
    episode_number: int = 0
    title: str = ""
    movie_path: str = ""
    last_position: float = 0.0
    duration: float = 0.0
    date_added: str = ""


@dataclass
class Season:
    """Represents a season of a TV show."""
    id: int = 0
    show_id: int = 0
    season_number: int = 1
    date_added: str = ""
    episodes: List[Episode] = field(default_factory=list)


@dataclass
class Show:
    """Represents a TV show in the catalog."""
    id: int = 0
    title: str = ""
    thumb_path: str = ""
    date_added: str = ""
    seasons: List[Season] = field(default_factory=list)


class Database:
    """SQLite database manager for the movie and show catalog."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS movies (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    movie_path  TEXT NOT NULL,
                    thumb_path  TEXT NOT NULL,
                    date_added  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_position REAL DEFAULT 0,
                    duration    REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS subtitles (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_id    INTEGER NOT NULL,
                    sub_path    TEXT NOT NULL,
                    label       TEXT DEFAULT '',
                    is_embedded BOOLEAN DEFAULT 0,
                    track_index INTEGER DEFAULT 0,
                    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS shows (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    thumb_path  TEXT NOT NULL,
                    date_added  DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS seasons (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_id       INTEGER NOT NULL,
                    season_number INTEGER NOT NULL DEFAULT 1,
                    date_added    DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (show_id) REFERENCES shows(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    season_id       INTEGER NOT NULL,
                    episode_number  INTEGER NOT NULL,
                    title           TEXT NOT NULL DEFAULT '',
                    movie_path      TEXT NOT NULL,
                    last_position   REAL DEFAULT 0,
                    duration        REAL DEFAULT 0,
                    date_added      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE
                );
            """)
            conn.commit()
        finally:
            conn.close()

    # ---- Movies ------------------------------------------------------------------------------------------

    def add_movie(self, title: str, movie_path: str, thumb_path: str,
                  subtitle_entries: list = None) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO movies (title, movie_path, thumb_path) VALUES (?, ?, ?)",
                (title, movie_path, thumb_path)
            )
            movie_id = cursor.lastrowid
            if subtitle_entries:
                for sub in subtitle_entries:
                    conn.execute(
                        """INSERT INTO subtitles (movie_id, sub_path, label, is_embedded, track_index)
                           VALUES (?, ?, ?, ?, ?)""",
                        (movie_id, sub.get("sub_path", ""),
                         sub.get("label", ""), sub.get("is_embedded", False),
                         sub.get("track_index", 0))
                    )
            conn.commit()
            return movie_id
        finally:
            conn.close()

    def get_all_movies(self, sort_by: str = "date_added", ascending: bool = False) -> list:
        order = "ASC" if ascending else "DESC"
        if sort_by == "title":
            order_clause = f"LOWER(title) {order}"
        else:
            order_clause = f"date_added {order}"

        conn = self._get_conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM movies ORDER BY {order_clause}"
            ).fetchall()

            movies = []
            for row in rows:
                movie = Movie(
                    id=row["id"], title=row["title"],
                    movie_path=row["movie_path"], thumb_path=row["thumb_path"],
                    date_added=row["date_added"], last_position=row["last_position"],
                    duration=row["duration"]
                )
                subs = conn.execute(
                    "SELECT sub_path, label, is_embedded, track_index FROM subtitles WHERE movie_id = ?",
                    (row["id"],)
                ).fetchall()
                movie.subtitle_paths = [(s["sub_path"], s["label"]) for s in subs]
                movies.append(movie)
            return movies
        finally:
            conn.close()

    def search_movies(self, query: str, sort_by: str = "date_added", ascending: bool = False) -> list:
        order = "ASC" if ascending else "DESC"
        if sort_by == "title":
            order_clause = f"LOWER(title) {order}"
        else:
            order_clause = f"date_added {order}"

        conn = self._get_conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM movies WHERE title LIKE ? ORDER BY {order_clause}",
                (f"%{query}%",)
            ).fetchall()

            movies = []
            for row in rows:
                movie = Movie(
                    id=row["id"], title=row["title"],
                    movie_path=row["movie_path"], thumb_path=row["thumb_path"],
                    date_added=row["date_added"], last_position=row["last_position"],
                    duration=row["duration"]
                )
                subs = conn.execute(
                    "SELECT sub_path, label FROM subtitles WHERE movie_id = ?",
                    (row["id"],)
                ).fetchall()
                movie.subtitle_paths = [(s["sub_path"], s["label"]) for s in subs]
                movies.append(movie)
            return movies
        finally:
            conn.close()

    def get_movie(self, movie_id: int) -> Optional[Movie]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM movies WHERE id = ?", (movie_id,)
            ).fetchone()
            if not row:
                return None
            movie = Movie(
                id=row["id"], title=row["title"],
                movie_path=row["movie_path"], thumb_path=row["thumb_path"],
                date_added=row["date_added"], last_position=row["last_position"],
                duration=row["duration"]
            )
            subs = conn.execute(
                "SELECT sub_path, label FROM subtitles WHERE movie_id = ?",
                (movie_id,)
            ).fetchall()
            movie.subtitle_paths = [(s["sub_path"], s["label"]) for s in subs]
            return movie
        finally:
            conn.close()

    def update_playback_position(self, movie_id: int, position: float):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE movies SET last_position = ? WHERE id = ?",
                (position, movie_id)
            )
            conn.commit()
        finally:
            conn.close()

    def update_duration(self, movie_id: int, duration: float):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE movies SET duration = ? WHERE id = ?",
                (duration, movie_id)
            )
            conn.commit()
        finally:
            conn.close()

    def delete_movie(self, movie_id: int) -> Optional[Movie]:
        movie = self.get_movie(movie_id)
        if not movie:
            return None
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
            conn.commit()
            return movie
        finally:
            conn.close()

    def get_movie_count(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM movies").fetchone()
            return row["cnt"]
        finally:
            conn.close()

    # ---- Shows --------------------------------------------------------------------------------------------

    def add_show(self, title: str, thumb_path: str) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO shows (title, thumb_path) VALUES (?, ?)",
                (title, thumb_path)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_season(self, show_id: int, season_number: int) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO seasons (show_id, season_number) VALUES (?, ?)",
                (show_id, season_number)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_episode(self, season_id: int, episode_number: int,
                    title: str, movie_path: str) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO episodes (season_id, episode_number, title, movie_path)
                   VALUES (?, ?, ?, ?)""",
                (season_id, episode_number, title, movie_path)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_all_shows(self, sort_by: str = "date_added", ascending: bool = False) -> list:
        order = "ASC" if ascending else "DESC"
        if sort_by == "title":
            order_clause = f"LOWER(title) {order}"
        else:
            order_clause = f"date_added {order}"

        conn = self._get_conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM shows ORDER BY {order_clause}"
            ).fetchall()
            shows = []
            for row in rows:
                show = Show(
                    id=row["id"], title=row["title"],
                    thumb_path=row["thumb_path"], date_added=row["date_added"]
                )
                show.seasons = self._get_seasons(conn, show.id)
                shows.append(show)
            return shows
        finally:
            conn.close()

    def search_shows(self, query: str, sort_by: str = "date_added", ascending: bool = False) -> list:
        order = "ASC" if ascending else "DESC"
        if sort_by == "title":
            order_clause = f"LOWER(title) {order}"
        else:
            order_clause = f"date_added {order}"

        conn = self._get_conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM shows WHERE title LIKE ? ORDER BY {order_clause}",
                (f"%{query}%",)
            ).fetchall()
            shows = []
            for row in rows:
                show = Show(
                    id=row["id"], title=row["title"],
                    thumb_path=row["thumb_path"], date_added=row["date_added"]
                )
                show.seasons = self._get_seasons(conn, show.id)
                shows.append(show)
            return shows
        finally:
            conn.close()

    def get_show(self, show_id: int) -> Optional[Show]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM shows WHERE id = ?", (show_id,)
            ).fetchone()
            if not row:
                return None
            show = Show(
                id=row["id"], title=row["title"],
                thumb_path=row["thumb_path"], date_added=row["date_added"]
            )
            show.seasons = self._get_seasons(conn, show.id)
            return show
        finally:
            conn.close()

    def _get_seasons(self, conn, show_id: int) -> List[Season]:
        rows = conn.execute(
            "SELECT * FROM seasons WHERE show_id = ? ORDER BY season_number ASC",
            (show_id,)
        ).fetchall()
        seasons = []
        for row in rows:
            season = Season(
                id=row["id"], show_id=row["show_id"],
                season_number=row["season_number"], date_added=row["date_added"]
            )
            eps = conn.execute(
                "SELECT * FROM episodes WHERE season_id = ? ORDER BY episode_number ASC",
                (row["id"],)
            ).fetchall()
            season.episodes = [
                Episode(
                    id=e["id"], season_id=e["season_id"],
                    episode_number=e["episode_number"], title=e["title"],
                    movie_path=e["movie_path"], last_position=e["last_position"],
                    duration=e["duration"], date_added=e["date_added"]
                ) for e in eps
            ]
            seasons.append(season)
        return seasons

    def get_show_count(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM shows").fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def get_existing_show_titles(self) -> list:
        """Return list of (id, title) for all existing shows."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, title FROM shows ORDER BY LOWER(title) ASC"
            ).fetchall()
            return [(r["id"], r["title"]) for r in rows]
        finally:
            conn.close()

    def get_next_season_number(self, show_id: int) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT MAX(season_number) as mx FROM seasons WHERE show_id = ?",
                (show_id,)
            ).fetchone()
            return (row["mx"] or 0) + 1
        finally:
            conn.close()

    def update_episode_position(self, episode_id: int, position: float):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE episodes SET last_position = ? WHERE id = ?",
                (position, episode_id)
            )
            conn.commit()
        finally:
            conn.close()

    def update_episode_duration(self, episode_id: int, duration: float):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE episodes SET duration = ? WHERE id = ?",
                (duration, episode_id)
            )
            conn.commit()
        finally:
            conn.close()

    def delete_show(self, show_id: int) -> Optional[Show]:
        show = self.get_show(show_id)
        if not show:
            return None
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM shows WHERE id = ?", (show_id,))
            conn.commit()
            return show
        finally:
            conn.close()
