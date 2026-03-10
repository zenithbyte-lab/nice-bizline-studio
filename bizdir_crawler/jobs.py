from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable

from .area_sources import collect_company_urls_for_area, load_area_terms
from .db import insert_job_rows, list_areas, save_areas, update_job, update_job_area
from .db_events import append_job_event
from .http_client import fetch_with_retry
from .models import AreaTerm, FetchResult
from .pipeline import fetch_details_with_threads


def sync_areas(
    db_path,
    area_index_url: str,
    fetch_document: Callable[[str], FetchResult],
) -> list[AreaTerm]:
    def fetch_listing(url: str) -> FetchResult:
        return fetch_with_retry(fetch_document, url, retries=3, retry_backoff=0.4)

    areas = load_area_terms(fetch_listing, area_index_url)
    save_areas(db_path, areas)
    return areas


def run_job(
    db_path,
    job_id: str,
    area_ids: list[int],
    settings,
    fetch_document: Callable[[str], FetchResult],
) -> None:
    areas_by_id = {area.term_id: area for area in list_areas(db_path)}
    selected = [areas_by_id[area_id] for area_id in area_ids if area_id in areas_by_id]
    discovered_total = 0
    saved_total = 0
    update_job(db_path, job_id, status="running", message="Collecting companies")
    append_job_event(db_path, job_id, "info", "Job started")

    for index, area in enumerate(selected, start=1):
        update_job_area(db_path, job_id, area.term_id, status="running")
        append_job_event(db_path, job_id, "info", f"Scanning area {area.name}")

        def fetch_listing(url: str) -> FetchResult:
            return fetch_with_retry(fetch_document, url, retries=3, retry_backoff=0.4)

        company_urls = collect_company_urls_for_area(
            fetch_document=fetch_listing,
            area=area,
            page_limit=settings.page_limit,
            company_limit=settings.company_limit,
        )
        append_job_event(db_path, job_id, "info", f"{area.name}: discovered {len(company_urls)} company url(s)")
        rows = fetch_details_with_threads(
            urls=company_urls,
            fetch_detail=fetch_document,
            workers=settings.workers,
            retries=3,
            retry_backoff=0.4,
        )
        saved = insert_job_rows(db_path, job_id, area.name, rows)
        discovered_total += len(company_urls)
        saved_total += saved
        update_job_area(
            db_path,
            job_id,
            area.term_id,
            status="done",
            discovered_count=len(company_urls),
            saved_count=saved,
        )
        update_job(
            db_path,
            job_id,
            processed_count=index,
            discovered_count=discovered_total,
            saved_count=saved_total,
            message=f"Processed {area.name}",
        )
        append_job_event(db_path, job_id, "info", f"{area.name}: saved {saved} row(s)")

    update_job(db_path, job_id, status="completed", message="Crawl finished")
    append_job_event(db_path, job_id, "info", f"Job finished with {saved_total} saved row(s)")


class ThreadedJobRunner:
    def __init__(self, db_path, fetcher_factory: Callable[[], object], max_jobs: int = 2) -> None:
        self.db_path = db_path
        self.fetcher_factory = fetcher_factory
        self.executor = ThreadPoolExecutor(max_workers=max_jobs)

    def start(self, job_id: str, area_ids: list[int], settings) -> None:
        self.executor.submit(self._run, job_id, area_ids, settings)

    def _run(self, job_id: str, area_ids: list[int], settings) -> None:
        fetcher = self.fetcher_factory()
        try:
            run_job(self.db_path, job_id, area_ids, settings, fetcher.fetch)
        except Exception as exc:
            update_job(self.db_path, job_id, status="failed", message=str(exc))
            append_job_event(self.db_path, job_id, "error", str(exc))
        finally:
            close = getattr(fetcher, "close", None)
            if callable(close):
                close()
