import sqlite3
from pathlib import Path
from typing import Set

DB_PATH = Path(__file__).parent / "cocktails.db"

def init_db() -> None:
    """Initialize the SQLite database and create tables if they don't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                slug TEXT NOT NULL,
                PRIMARY KEY (user_id, slug)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_cache (
                slug TEXT PRIMARY KEY,
                file_id TEXT NOT NULL
            )
        """)
        conn.commit()

def add_favorite(user_id: int, slug: str) -> bool:
    """
    Add a cocktail to favorites.
    Returns True if added, False if already existed.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO favorites (user_id, slug) VALUES (?, ?)", (user_id, slug))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def remove_favorite(user_id: int, slug: str) -> bool:
    """
    Remove a cocktail from favorites.
    Returns True if removed, False if it wasn't there.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE user_id = ? AND slug = ?", (user_id, slug))
        conn.commit()
        return cursor.rowcount > 0

def toggle_favorite(user_id: int, slug: str) -> bool:
    """
    Toggles favorite status.
    Returns True if it is now a favorite (added), False if removed.
    """
    if is_favorite(user_id, slug):
        remove_favorite(user_id, slug)
        return False
    else:
        add_favorite(user_id, slug)
        return True

def get_user_favorites(user_id: int) -> Set[str]:
    """Return a set of slugs that are in the user's favorites."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT slug FROM favorites WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return {row[0] for row in rows}

def is_favorite(user_id: int, slug: str) -> bool:
    """Check if a slug is in user's favorites."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM favorites WHERE user_id = ? AND slug = ?", (user_id, slug))
        return cursor.fetchone() is not None


# --- Video Cache Functions ---

def save_video_file_id(slug: str, file_id: str) -> None:
    """Save Telegram file_id for a video to enable instant re-sending."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO video_cache (slug, file_id) VALUES (?, ?)",
            (slug, file_id)
        )
        conn.commit()


def get_video_file_id(slug: str) -> str | None:
    """Get cached Telegram file_id for a video. Returns None if not cached."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_id FROM video_cache WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        return row[0] if row else None
