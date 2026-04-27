import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Summary:
    id: str
    url: str
    source: str
    model: str
    summary: str
    created_at: int


def _db_path() -> Path:
    override = os.getenv("GLANCE_DB")
    if override:
        return Path(override).expanduser()
    return Path(os.getenv("XDG_CACHE_HOME", "~/.cache")).expanduser() / "glance" / "glance.db"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summaries (
          id          TEXT PRIMARY KEY,
          url         TEXT NOT NULL,
          source      TEXT NOT NULL,
          model       TEXT NOT NULL,
          summary     TEXT NOT NULL,
          created_at  INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        DELETE FROM summaries
        WHERE rowid IN (
          SELECT old.rowid
          FROM summaries AS old
          JOIN summaries AS newer
            ON newer.url = old.url
           AND (
             newer.created_at > old.created_at
             OR (newer.created_at = old.created_at AND newer.rowid > old.rowid)
           )
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON summaries(created_at DESC)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_url_unique ON summaries(url)")
    return conn


def _row_to_summary(row: sqlite3.Row) -> Summary:
    return Summary(
        id=row["id"],
        url=row["url"],
        source=row["source"],
        model=row["model"],
        summary=row["summary"],
        created_at=row["created_at"],
    )


def get_by_id(id: str) -> Summary | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM summaries WHERE id = ?", (id,)).fetchone()
    return _row_to_summary(row) if row else None


def put(url: str, source: str, model: str, summary: str) -> str:
    sid = secrets.token_urlsafe(8)
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO summaries (id, url, source, model, summary, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(url) DO UPDATE SET "
            "source = excluded.source, "
            "model = excluded.model, "
            "summary = excluded.summary, "
            "created_at = excluded.created_at",
            (sid, url, source, model, summary, now),
        )
        row = conn.execute("SELECT id FROM summaries WHERE url = ?", (url,)).fetchone()
    return row["id"]


def list_recent(limit: int = 50, query: str | None = None) -> list[Summary]:
    sql = "SELECT * FROM summaries"
    params: tuple = ()
    if query:
        sql += " WHERE url LIKE ? OR summary LIKE ?"
        like = f"%{query}%"
        params = (like, like)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params = params + (limit,)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_summary(r) for r in rows]
