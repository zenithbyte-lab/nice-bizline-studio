"""Saramin HTML parsing – list pages and company detail pages.

Uses only stdlib HTMLParser + regex. No BeautifulSoup dependency.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from html.parser import HTMLParser

from .models import SaraminRow
from .saramin_constants import (
    BASE_ORIGIN,
    COMPANY_INFO_PATH,
    MISSING,
    OFFICIAL_WEB_HOST_EXCLUDES,
)


# ---------------------------------------------------------------------------
# List-page parsing: extract company-info URLs from search result HTML
# ---------------------------------------------------------------------------

_RECRUIT_ITEM_RE = re.compile(
    r'<a\s[^>]*?href=["\']([^"\']*?/zf_user/jobs/relay/view[^"\']*?)["\']',
    re.I,
)

_COMPANY_NM_RE = re.compile(
    r'<a\s[^>]*?href=["\']([^"\']*?/zf_user/company-info/view[^"\']*?)["\']',
    re.I,
)

_NEXT_PAGE_RE = re.compile(
    r'<a\s[^>]*?class=["\'][^"\']*?\bpg_next\b[^"\']*?["\'][^>]*?href=["\']([^"\']+?)["\']',
    re.I,
)


class _ListPageParser(HTMLParser):
    """Extract company-info hrefs from a Saramin search results page."""

    def __init__(self) -> None:
        super().__init__()
        self.company_urls: list[str] = []
        self.next_page_url: str | None = None
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = (attrs_dict.get("href") or "").strip()
        if not href:
            return

        # Company info link
        if COMPANY_INFO_PATH in href:
            full_url = urllib.parse.urljoin(BASE_ORIGIN, href)
            if full_url not in self._seen:
                self._seen.add(full_url)
                self.company_urls.append(full_url)

        # Next-page link
        css_class = attrs_dict.get("class") or ""
        if "pg_next" in css_class and href != "#":
            self.next_page_url = urllib.parse.urljoin(BASE_ORIGIN, href)


def parse_list_page(html_text: str) -> tuple[list[str], str | None]:
    """Return (company_info_urls, next_page_url_or_None)."""
    parser = _ListPageParser()
    parser.feed(html_text)

    # Fallback: regex for company-info links if parser found none
    if not parser.company_urls:
        for m in _COMPANY_NM_RE.finditer(html_text):
            url = urllib.parse.urljoin(BASE_ORIGIN, m.group(1))
            if url not in parser._seen:
                parser._seen.add(url)
                parser.company_urls.append(url)

    # Fallback: regex for next-page
    if parser.next_page_url is None:
        m = _NEXT_PAGE_RE.search(html_text)
        if m:
            parser.next_page_url = urllib.parse.urljoin(BASE_ORIGIN, m.group(1))

    return parser.company_urls, parser.next_page_url


# ---------------------------------------------------------------------------
# Company-info detail page parsing
# ---------------------------------------------------------------------------

class _VisibleTextParser(HTMLParser):
    """Collect visible text, skip <script>/<style>/<noscript>."""

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


class _CompanyLinkParser(HTMLParser):
    """Extract all <a href=...> links from company info page."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.links.append(value.strip())


# Regex patterns for field extraction from visible text
_CEO_RE = re.compile(r"대표(?:자|이사)?\s*[:：\s]\s*(\S+)")
_COMPANY_NAME_RE = re.compile(
    r'<(?:h1|h2|strong|span)[^>]*class=["\'][^"\']*?company[_-]?name[^"\']*?["\'][^>]*>(.*?)</(?:h1|h2|strong|span)>',
    re.I | re.S,
)
_HOMEPAGE_RE = re.compile(
    r'<a\s[^>]*?href=["\'](["\']|[^"\']*?)["\'][^>]*?class=["\'][^"\']*?homepage[^"\']*?["\']',
    re.I,
)
_HOMEPAGE2_RE = re.compile(
    r'class=["\'][^"\']*?homepage[^"\']*?["\'][^>]*?href=["\']([^"\']+?)["\']',
    re.I,
)

# LD+JSON company schema
_LDJSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


def _extract_from_ldjson(html_text: str) -> tuple[str, str, str]:
    """Try to pull company_name, ceo, url from ld+json."""
    for m in _LDJSON_RE.finditer(html_text):
        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            continue
        otype = data.get("@type", "")
        if otype in ("Organization", "Corporation", "LocalBusiness", "Company"):
            name = data.get("name", "")
            ceo = ""
            founder = data.get("founder") or data.get("ceo") or ""
            if isinstance(founder, dict):
                ceo = founder.get("name", "")
            elif isinstance(founder, str):
                ceo = founder
            url = data.get("url", "")
            return str(name), str(ceo), str(url)
    return "", "", ""


def _extract_website_from_links(html_text: str) -> str:
    """Find the first external http(s) link that isn't a social/Saramin site."""
    # Try homepage class links first
    for pat in (_HOMEPAGE_RE, _HOMEPAGE2_RE):
        m = pat.search(html_text)
        if m:
            href = m.group(1).strip()
            if href and href.startswith("http"):
                return href

    # Fallback: parse all <a> links and pick the first external one
    parser = _CompanyLinkParser()
    parser.feed(html_text)
    for link in parser.links:
        if not link.startswith("http"):
            continue
        try:
            host = urllib.parse.urlsplit(link).hostname or ""
        except Exception:
            continue
        host_lower = host.lower()
        if any(excl in host_lower for excl in OFFICIAL_WEB_HOST_EXCLUDES):
            continue
        return link
    return ""


def _extract_company_name(html_text: str) -> str:
    """Extract company name from HTML class-based tags."""
    m = _COMPANY_NAME_RE.search(html_text)
    if m:
        raw = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if raw:
            return raw
    return ""


def _extract_ceo(visible_text: str) -> str:
    m = _CEO_RE.search(visible_text)
    if m:
        return m.group(1).strip()
    return ""


def parse_company_detail(html_text: str, source_url: str) -> SaraminRow | None:
    """Parse a Saramin company-info page into a SaraminRow."""
    if not html_text or len(html_text) < 50:
        return None

    # Try LD+JSON first
    ld_name, ld_ceo, ld_url = _extract_from_ldjson(html_text)

    # HTML-based extraction
    html_name = _extract_company_name(html_text)
    html_website = _extract_website_from_links(html_text)

    # Visible text for CEO
    text_parser = _VisibleTextParser()
    text_parser.feed(html_text)
    visible = text_parser.text()
    html_ceo = _extract_ceo(visible)

    # Merge: prefer non-empty values
    company_name = ld_name or html_name or MISSING
    ceo_name = ld_ceo or html_ceo or MISSING
    website = ld_url or html_website or MISSING

    # If we got nothing useful, skip
    if company_name == MISSING and ceo_name == MISSING and website == MISSING:
        return None

    return SaraminRow(
        company_name=company_name,
        ceo_name=ceo_name,
        website=website,
        source_url=source_url,
    )
