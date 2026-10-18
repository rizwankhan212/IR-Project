"""Persistent search history for ResearchSphere.

Uses a separate table in the project's SQLite database and does not modify
the research_papers schema.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/research_papers.db")


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_history():
    """Create the search history table if it does not already exist."""
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                method TEXT NOT NULL,
                year_filter TEXT NOT NULL,
                top_k INTEGER NOT NULL,
                document_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_search(query, method, year_filter, top_k, document_count):
    """Save one user-submitted search."""
    if not query or not query.strip():
        return

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO search_history
                (query, method, year_filter, top_k, document_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                query.strip(),
                method,
                str(year_filter),
                int(top_k),
                int(document_count),
            ),
        )


def get_search_history(limit=100):
    """Return the newest searches first."""
    limit = max(1, min(int(limit), 500))

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, query, method, year_filter, top_k,
                   document_count, created_at
            FROM search_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def clear_search_history():
    """Remove saved search history without touching the paper collection."""
    with _connect() as connection:
        connection.execute("DELETE FROM search_history")
