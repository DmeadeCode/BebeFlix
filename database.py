"""
Database layer for BebeFlix movie catalog.
Uses SQLite for zero-dependency portable storage.
"""

import sqlite3
import os
from dataclasses import dataclass, field
from typing import Optional
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


class Database:
    """SQLite database manager for the movie catalog."""

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
            """)
            conn.commit()
        finally:
            conn.close()

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
                    id=row["id"],
                    title=row["title"],
                    movie_path=row["movie_path"],
                    thumb_path=row["thumb_path"],
                    date_added=row["date_added"],
                    last_position=row["last_position"],
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
                    id=row["id"],
                    title=row["title"],
                    movie_path=row["movie_path"],
                    thumb_path=row["thumb_path"],
                    date_added=row["date_added"],
                    last_position=row["last_position"],
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
                id=row["id"],
                title=row["title"],
                movie_path=row["movie_path"],
                thumb_path=row["thumb_path"],
                date_added=row["date_added"],
                last_position=row["last_position"],
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
