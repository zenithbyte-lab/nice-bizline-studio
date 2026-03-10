from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .http_client import fetch_with_retry
from .models import DetailRow, FetchResult
from .parsing import extract_detail_urls, extract_sitemap_page_urls, parse_detail_payload


def collect_detail_urls(
    sitemap_index_url: str,
    max_sitemaps: int | None,
    stop_after_empty: int,
    fetch_document: Callable[[str], FetchResult],
) -> list[str]:
    index_result = fetch_document(sitemap_index_url)
    sitemap_urls = extract_sitemap_page_urls(index_result.text, sitemap_index_url)
    if max_sitemaps is not None:
        sitemap_urls = sitemap_urls[:max_sitemaps]

    collected: list[str] = []
    empty_streak = 0
    for sitemap_url in sitemap_urls:
        sitemap_result = fetch_document(sitemap_url)
        detail_urls = extract_detail_urls(sitemap_result.text, sitemap_url)
        if not detail_urls:
            empty_streak += 1
            if empty_streak >= max(1, stop_after_empty):
                break
            continue
        empty_streak = 0
        collected.extend(detail_urls)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in collected:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _to_fetch_result(payload: tuple[int, str] | FetchResult) -> FetchResult:
    if isinstance(payload, FetchResult):
        return payload
    status_code, text = payload
    return FetchResult(status_code=status_code, text=text)


def fetch_details_with_threads(
    urls: list[str],
    fetch_detail: Callable[[str], tuple[int, str] | FetchResult],
    workers: int,
    retries: int,
    retry_backoff: float = 0.3,
    start_index: int = 0,
    limit: int | None = None,
) -> list[DetailRow]:
    selected = urls[start_index:]
    if limit is not None:
        selected = selected[:limit]

    indexed_urls = list(enumerate(selected, start=start_index))
    if not indexed_urls:
        return []

    def run_one(index: int, url: str) -> tuple[int, DetailRow | None]:
        def fetch_once(target_url: str) -> FetchResult:
            return _to_fetch_result(fetch_detail(target_url))

        result = fetch_with_retry(fetch_once, url, retries=retries, retry_backoff=retry_backoff)
        if result.status_code >= 400:
            return index, None
        return index, parse_detail_payload(result.text, url)

    output: dict[int, DetailRow] = {}
    max_workers = max(1, min(workers, len(indexed_urls)))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(run_one, idx, url) for idx, url in indexed_urls]
        for future in as_completed(futures):
            index, row = future.result()
            if row is not None:
                output[index] = row

    return [output[index] for index, _ in indexed_urls if index in output]
