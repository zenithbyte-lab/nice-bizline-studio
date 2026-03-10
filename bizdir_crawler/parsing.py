from __future__ import annotations

import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .constants import BLOCKED_MARKERS, DETAIL_NODE_RE, DETAIL_STOP_MARKERS, FIELD_PATTERN, LOC_TAG_RE, SITEMAP_PAGE_RE
from .models import DetailRow


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        stripped = data.strip()
        if stripped:
            self._chunks.append(stripped)

    def text(self) -> str:
        return " ".join(self._chunks)


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.links.append(value.strip())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _parse_loc_values(document_text: str) -> list[str]:
    try:
        root = ET.fromstring(document_text)
        values = [elem.text.strip() for elem in root.iter() if elem.tag.endswith("loc") and elem.text]
        if values:
            return values
    except ET.ParseError:
        pass

    values = []
    for match in LOC_TAG_RE.finditer(document_text):
        candidate = html.unescape(match.group(1)).strip()
        if candidate:
            values.append(candidate)
    return values


def _parse_links(document_text: str, base_url: str) -> list[str]:
    parser = _HrefParser()
    parser.feed(document_text)
    return [urllib.parse.urljoin(base_url, link) for link in parser.links]


def extract_sitemap_page_urls(document_text: str, base_url: str) -> list[str]:
    xml_urls = [urllib.parse.urljoin(base_url, url) for url in _parse_loc_values(document_text)]
    sitemap_urls = [url for url in xml_urls if SITEMAP_PAGE_RE.search(url)]
    if sitemap_urls:
        return _dedupe(sitemap_urls)

    fallback_urls = [url for url in _parse_links(document_text, base_url) if SITEMAP_PAGE_RE.search(url)]
    return _dedupe(fallback_urls)


def extract_detail_urls(document_text: str, base_url: str) -> list[str]:
    xml_urls = [urllib.parse.urljoin(base_url, url) for url in _parse_loc_values(document_text)]
    detail_urls = [url for url in xml_urls if DETAIL_NODE_RE.search(url)]
    if detail_urls:
        return _dedupe(detail_urls)

    fallback_urls = [url for url in _parse_links(document_text, base_url) if DETAIL_NODE_RE.search(url)]
    return _dedupe(fallback_urls)


def _html_to_text(document_text: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(document_text)
    return re.sub(r"\s+", " ", parser.text()).strip()


def _trim_value(value: str) -> str:
    trimmed = value.strip(" :")
    for marker in DETAIL_STOP_MARKERS:
        marker_index = trimmed.find(marker)
        if marker_index >= 0:
            trimmed = trimmed[:marker_index].rstrip(" :")
    return trimmed


def parse_detail_payload(document_text: str, detail_url: str) -> DetailRow | None:
    lowered = document_text.lower()
    if any(marker in lowered for marker in BLOCKED_MARKERS):
        return None

    text = _html_to_text(document_text)
    matches = list(FIELD_PATTERN.finditer(text))
    if not matches:
        return None

    values: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        values[label] = _trim_value(text[start:end])

    row = DetailRow(
        detail_url=detail_url,
        company_name=values.get("Company Name", ""),
        contact=values.get("Contact", ""),
        website=values.get("Website", ""),
        area=values.get("Area", ""),
    )
    if not any([row.company_name, row.contact, row.website, row.area]):
        return None
    return row
