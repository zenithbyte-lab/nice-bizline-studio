from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetailRow:
    detail_url: str
    company_name: str
    contact: str
    website: str
    area: str


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    text: str


@dataclass(frozen=True)
class AreaTerm:
    term_id: int
    name: str
    url: str


@dataclass(frozen=True)
class TermListing:
    company_urls: list[str]
    has_next_page: bool


@dataclass(frozen=True)
class JobRecord:
    id: str
    status: str
    page_limit: int
    company_limit: int | None
    workers: int
    selected_count: int
    processed_count: int
    discovered_count: int
    saved_count: int
    message: str
    created_at: str
    finished_at: str | None


@dataclass(frozen=True)
class JobAreaRecord:
    area_id: int
    area_name: str
    area_url: str
    status: str
    discovered_count: int
    saved_count: int
