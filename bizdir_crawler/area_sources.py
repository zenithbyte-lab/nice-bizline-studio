from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable

from .models import AreaTerm, FetchResult, TermListing
from .parsing import extract_detail_urls

TERM_LINK_RE = re.compile(r'href=["\']([^"\']*/taxonomy/term/(\d+)[^"\']*)["\'][^>]*>(.*?)</a>', re.I | re.S)
PAGER_NEXT_RE = re.compile(r'class=["\'][^"\']*pager-next[^"\']*["\']', re.I)


def _clean_label(raw_html: str) -> str:
    label = re.sub(r"<[^>]+>", "", raw_html)
    return " ".join(label.split()).strip()


def parse_area_terms(document_text: str, base_url: str) -> list[AreaTerm]:
    seen: set[int] = set()
    areas: list[AreaTerm] = []
    for href, term_id_text, label_html in TERM_LINK_RE.findall(document_text):
        term_id = int(term_id_text)
        if term_id in seen:
            continue
        seen.add(term_id)
        label = _clean_label(label_html)
        if not label:
            continue
        areas.append(
            AreaTerm(
                term_id=term_id,
                name=label,
                url=urllib.parse.urljoin(base_url, href),
            )
        )
    return areas


def parse_term_listing(document_text: str, base_url: str) -> TermListing:
    return TermListing(
        company_urls=extract_detail_urls(document_text, base_url),
        has_next_page=bool(PAGER_NEXT_RE.search(document_text)),
    )


def build_listing_page_url(listing_url: str, page_index: int) -> str:
    if page_index <= 0:
        return listing_url
    parsed = urllib.parse.urlsplit(listing_url)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, f"page={page_index}", "")
    )


def load_area_terms(
    fetch_document: Callable[[str], FetchResult],
    area_index_url: str,
) -> list[AreaTerm]:
    seen: set[int] = set()
    areas: list[AreaTerm] = []
    page_index = 0

    while True:
        page_url = build_listing_page_url(area_index_url, page_index)
        result = fetch_document(page_url)
        page_areas = parse_area_terms(result.text, page_url)
        new_count = 0
        for area in page_areas:
            if area.term_id in seen:
                continue
            seen.add(area.term_id)
            areas.append(area)
            new_count += 1
        if not page_areas or new_count == 0:
            break
        if not PAGER_NEXT_RE.search(result.text):
            break
        page_index += 1

    return areas


def collect_company_urls_for_area(
    fetch_document: Callable[[str], FetchResult],
    area: AreaTerm,
    page_limit: int,
    company_limit: int | None,
) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    max_pages = page_limit if page_limit and page_limit > 0 else None
    page_index = 0

    while True:
        if max_pages is not None and page_index >= max_pages:
            break
        page_url = build_listing_page_url(area.url, page_index)
        result = fetch_document(page_url)
        listing = parse_term_listing(result.text, page_url)
        if not listing.company_urls:
            break
        new_count = 0
        for url in listing.company_urls:
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            new_count += 1
            if company_limit is not None and len(urls) >= company_limit:
                return urls[:company_limit]
        if new_count == 0:
            break
        if not listing.has_next_page:
            break
        page_index += 1
    return urls
