from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def _session(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_event_store(db_path: Path) -> None:
    with _session(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id TEXT NOT NULL,
              level TEXT NOT NULL,
              message TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )


def append_job_event(db_path: Path, job_id: str, level: str, message: str) -> None:
    with _session(db_path) as conn:
        conn.execute(
            "INSERT INTO job_events(job_id, level, message, created_at) VALUES(?, ?, ?, ?)",
            (job_id, level, message, _now()),
        )


def list_job_events(db_path: Path, job_id: str, limit: int = 80) -> list[dict[str, str]]:
    with _session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT level, message, created_at FROM job_events
            WHERE job_id=? ORDER BY id DESC LIMIT ?
            """,
            (job_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
