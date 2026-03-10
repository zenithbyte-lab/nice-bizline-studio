from __future__ import annotations

import csv
import io
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .db_events import append_job_event, init_event_store, list_job_events
from .models import AreaTerm, DetailRow, JobAreaRecord, JobRecord
def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def _session(db_path: Path):
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with _session(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS areas (
              term_id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              url TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              page_limit INTEGER NOT NULL,
              company_limit INTEGER,
              workers INTEGER NOT NULL,
              selected_count INTEGER NOT NULL,
              processed_count INTEGER NOT NULL DEFAULT 0,
              discovered_count INTEGER NOT NULL DEFAULT 0,
              saved_count INTEGER NOT NULL DEFAULT 0,
              message TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS job_areas (
              job_id TEXT NOT NULL,
              area_id INTEGER NOT NULL,
              area_name TEXT NOT NULL,
              area_url TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'queued',
              discovered_count INTEGER NOT NULL DEFAULT 0,
              saved_count INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (job_id, area_id)
            );
            CREATE TABLE IF NOT EXISTS job_rows (
              job_id TEXT NOT NULL,
              detail_url TEXT NOT NULL,
              company_name TEXT NOT NULL,
              contact TEXT NOT NULL,
              website TEXT NOT NULL,
              area TEXT NOT NULL,
              source_area_name TEXT NOT NULL,
              PRIMARY KEY (job_id, detail_url)
            );
            """
        )
    init_event_store(db_path)
def save_areas(db_path: Path, areas: list[AreaTerm]) -> None:
    with _session(db_path) as conn:
        conn.execute("DELETE FROM areas")
        conn.executemany(
            "INSERT INTO areas(term_id, name, url, updated_at) VALUES(?, ?, ?, ?)",
            [(area.term_id, area.name, area.url, _now()) for area in areas],
        )


def list_areas(db_path: Path) -> list[AreaTerm]:
    with _session(db_path) as conn:
        rows = conn.execute("SELECT term_id, name, url FROM areas ORDER BY name").fetchall()
    return [AreaTerm(term_id=row["term_id"], name=row["name"], url=row["url"]) for row in rows]


def create_job(db_path: Path, area_ids: list[int], page_limit: int, company_limit: int | None, workers: int) -> str:
    areas = {area.term_id: area for area in list_areas(db_path)}
    selected = [areas[area_id] for area_id in area_ids if area_id in areas]
    if not selected:
        raise ValueError("no valid areas selected")
    job_id = uuid.uuid4().hex
    with _session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs(id, status, page_limit, company_limit, workers, selected_count, created_at)
            VALUES(?, 'queued', ?, ?, ?, ?, ?)
            """,
            (job_id, page_limit, company_limit, workers, len(selected), _now()),
        )
        conn.executemany(
            "INSERT INTO job_areas(job_id, area_id, area_name, area_url) VALUES(?, ?, ?, ?)",
            [(job_id, area.term_id, area.name, area.url) for area in selected],
        )
    append_job_event(db_path, job_id, "info", f"Queued {len(selected)} area(s)")
    return job_id


def update_job(db_path: Path, job_id: str, **fields: int | str | None) -> None:
    if not fields:
        return
    if fields.get("status") in {"completed", "failed"} and "finished_at" not in fields:
        fields["finished_at"] = _now()
    columns = ", ".join(f"{name}=?" for name in fields)
    with _session(db_path) as conn:
        conn.execute(f"UPDATE jobs SET {columns} WHERE id=?", [*fields.values(), job_id])


def update_job_area(db_path: Path, job_id: str, area_id: int, **fields: int | str) -> None:
    if not fields:
        return
    columns = ", ".join(f"{name}=?" for name in fields)
    with _session(db_path) as conn:
        conn.execute(
            f"UPDATE job_areas SET {columns} WHERE job_id=? AND area_id=?",
            [*fields.values(), job_id, area_id],
        )


def insert_job_rows(db_path: Path, job_id: str, source_area_name: str, rows: list[DetailRow]) -> int:
    payload = [(job_id, row.detail_url, row.company_name, row.contact, row.website, row.area, source_area_name) for row in rows]
    with _session(db_path) as conn:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO job_rows(job_id, detail_url, company_name, contact, website, area, source_area_name)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        return conn.total_changes - before


def get_job(db_path: Path, job_id: str) -> JobRecord:
    with _session(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)
    return JobRecord(**dict(row))


def list_job_areas(db_path: Path, job_id: str) -> list[JobAreaRecord]:
    with _session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT area_id, area_name, area_url, status, discovered_count, saved_count
            FROM job_areas WHERE job_id=? ORDER BY area_name
            """,
            (job_id,),
        ).fetchall()
    return [JobAreaRecord(**dict(row)) for row in rows]


def list_job_rows(db_path: Path, job_id: str, limit: int = 30) -> list[dict[str, str]]:
    query = "SELECT * FROM job_rows WHERE job_id=? ORDER BY company_name LIMIT ?"
    with _session(db_path) as conn:
        rows = conn.execute(query, (job_id, limit)).fetchall()
    return [dict(row) for row in rows]


def list_jobs(db_path: Path, limit: int = 8) -> list[JobRecord]:
    with _session(db_path) as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [JobRecord(**dict(row)) for row in rows]


def export_job_csv(db_path: Path, job_id: str) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["detail_url", "company_name", "contact", "website", "area", "source_area_name"])
    with _session(db_path) as conn:
        rows = conn.execute(
            "SELECT detail_url, company_name, contact, website, area, source_area_name FROM job_rows WHERE job_id=? ORDER BY company_name",
            (job_id,),
        ).fetchall()
    writer.writerows([tuple(row) for row in rows])
    return output.getvalue()
