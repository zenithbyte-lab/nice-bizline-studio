from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable

from .area_sources import collect_company_urls_for_area, load_area_terms
from .db import insert_job_rows, insert_saramin_rows, list_areas, save_areas, update_job, update_job_area
from .db_events import append_job_event
from .http_client import fetch_with_retry
from .models import AreaTerm, FetchResult
from .pipeline import fetch_details_with_threads
from .saramin_constants import BASE_ORIGIN, LIST_ENDPOINT
from .saramin_parsing import parse_company_detail, parse_list_page


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


def run_saramin_job(
    db_path,
    job_id: str,
    region_codes: list[str],
    settings,
    fetch_document: Callable[[str], FetchResult],
) -> None:
    from .saramin_constants import SARAMIN_REGIONS

    region_map = {r["code"]: r["name"] for r in SARAMIN_REGIONS}
    selected = [(code, region_map.get(code, code)) for code in region_codes if code in region_map]

    discovered_total = 0
    saved_total = 0
    update_job(db_path, job_id, status="running", message="Saramin crawl starting")
    append_job_event(db_path, job_id, "info", "Saramin job started")

    for index, (region_code, region_name) in enumerate(selected, start=1):
        update_job_area(db_path, job_id, int(region_code), status="running")
        append_job_event(db_path, job_id, "info", f"Scanning Saramin region {region_name}")

        list_url = (
            f"{BASE_ORIGIN}{LIST_ENDPOINT}?"
            f"loc_mcd={region_code}&panel_type=&search_optional_item=n"
            f"&search_done=y&panel_count=y&preview=y"
        )

        company_urls: list[str] = []
        page_count = 0
        company_limit = settings.company_limit

        while list_url:
            page_count += 1
            try:
                result = fetch_with_retry(fetch_document, list_url, retries=3, retry_backoff=0.5)
            except Exception:
                break

            urls, next_page = parse_list_page(result.text)
            company_urls.extend(urls)
            append_job_event(db_path, job_id, "info", f"{region_name} page {page_count}: found {len(urls)} companies")

            if company_limit and len(company_urls) >= company_limit:
                company_urls = company_urls[:company_limit]
                break
            list_url = next_page

        append_job_event(db_path, job_id, "info", f"{region_name}: total {len(company_urls)} company URLs")

        saramin_rows = []
        for cu in company_urls:
            try:
                detail_result = fetch_with_retry(fetch_document, cu, retries=2, retry_backoff=0.3)
                row = parse_company_detail(detail_result.text, cu)
                if row:
                    saramin_rows.append(row)
            except Exception:
                pass

        saved = insert_saramin_rows(db_path, job_id, saramin_rows)
        discovered_total += len(company_urls)
        saved_total += saved

        update_job_area(
            db_path, job_id, int(region_code),
            status="done",
            discovered_count=len(company_urls),
            saved_count=saved,
        )
        update_job(
            db_path, job_id,
            processed_count=index,
            discovered_count=discovered_total,
            saved_count=saved_total,
            message=f"Processed {region_name}",
        )
        append_job_event(db_path, job_id, "info", f"{region_name}: saved {saved} row(s)")

    update_job(db_path, job_id, status="completed", message="Saramin crawl finished")
    append_job_event(db_path, job_id, "info", f"Saramin job finished with {saved_total} saved row(s)")


class ThreadedJobRunner:
    def __init__(self, db_path, fetcher_factory: Callable[[], object], max_jobs: int = 2) -> None:
        self.db_path = db_path
        self.fetcher_factory = fetcher_factory
        self.executor = ThreadPoolExecutor(max_workers=max_jobs)

    def start(self, job_id: str, area_ids: list[int], settings, source: str = "bizdir") -> None:
        self.executor.submit(self._run, job_id, area_ids, settings, source)

    def _run(self, job_id: str, area_ids: list[int], settings, source: str = "bizdir") -> None:
        fetcher = self.fetcher_factory()
        try:
            if source == "saramin":
                region_codes = [str(aid) for aid in area_ids]
                run_saramin_job(self.db_path, job_id, region_codes, settings, fetcher.fetch)
            else:
                run_job(self.db_path, job_id, area_ids, settings, fetcher.fetch)
        except Exception as exc:
            update_job(self.db_path, job_id, status="failed", message=str(exc))
            append_job_event(self.db_path, job_id, "error", str(exc))
        finally:
            close = getattr(fetcher, "close", None)
            if callable(close):
                close()
