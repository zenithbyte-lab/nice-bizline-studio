from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import DetailRow


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_state(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"next_index": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, next_index: int) -> None:
    ensure_parent(path)
    payload = {"next_index": next_index}
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def write_urls(path: Path, urls: Iterable[str]) -> None:
    ensure_parent(path)
    lines = [f"{url}\n" for url in urls]
    path.write_text("".join(lines), encoding="utf-8")


def read_urls(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_rows(path: Path, rows: list[DetailRow]) -> None:
    ensure_parent(path)
    existed = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["detail_url", "company_name", "contact", "website", "area"],
        )
        if not existed:
            writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "detail_url": row.detail_url,
                    "company_name": row.company_name,
                    "contact": row.contact,
                    "website": row.website,
                    "area": row.area,
                }
            )
        handle.flush()
