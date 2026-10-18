
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/research_papers.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                authors TEXT,
                publication_year INTEGER,
                abstract TEXT,
                keywords TEXT,
                file_name TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL,
                full_text TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(research_papers)"
            )
        }

        if "pages_json" not in columns:
            conn.execute("""
                ALTER TABLE research_papers
                ADD COLUMN pages_json TEXT DEFAULT '[]'
            """)


def save_paper(metadata, file_name, file_path, full_text, pages=None):
    pages_json = json.dumps(pages or [])

    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO research_papers (
                title, authors, publication_year,
                abstract, keywords, file_name,
                file_path, full_text, pages_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata.get("title") or "Unknown",
            metadata.get("authors") or "Unknown",
            metadata.get("publication_year"),
            metadata.get("abstract") or "",
            metadata.get("keywords") or "",
            file_name,
            str(file_path),
            full_text,
            pages_json
        ))

        return cursor.rowcount > 0


def get_all_papers():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM research_papers
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]


def get_paper_by_id(paper_id):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM research_papers
            WHERE id = ?
        """, (paper_id,)).fetchone()

        return dict(row) if row else None


def update_paper_metadata(paper_id, metadata):
    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE research_papers
            SET title = ?, authors = ?, publication_year = ?,
                abstract = ?, keywords = ?
            WHERE id = ?
        """, (
            metadata.get("title") or "Unknown",
            metadata.get("authors") or "Unknown",
            metadata.get("publication_year"),
            metadata.get("abstract") or "",
            metadata.get("keywords") or "",
            paper_id
        ))

        return cursor.rowcount > 0


if __name__ == "__main__":
    create_table()
    print("Database ready.")
