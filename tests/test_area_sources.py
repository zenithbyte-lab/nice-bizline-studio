import unittest

import httpx

from bizdir_crawler.area_sources import collect_company_urls_for_area, load_area_terms, parse_area_terms, parse_term_listing
from bizdir_crawler.http_client import HttpxFetcher
from bizdir_crawler.models import AreaTerm, FetchResult


AREA_HTML = """
<div class="item-list"><ul>
  <li><a href="/taxonomy/term/57">Bundang-Gu</a></li>
  <li><a href="/taxonomy/term/2">Busan</a></li>
</ul></div>
"""

TERM_HTML = """
<div class="item-list"><ol>
  <li><a href="/node/14">21C HI-TECH CO., LTD.</a></li>
  <li><a href="/node/33">316 STEEL CO., LTD.</a></li>
</ol></div>
<ul class="pager">
  <li class="pager-current">Page 1</li>
  <li class="pager-next"><a href="/taxonomy/term/2?page=1">››</a></li>
</ul>
"""

AREA_PAGE_ONE = """
<div class="item-list"><ul>
  <li><a href="/taxonomy/term/57">Bundang-Gu</a></li>
  <li><a href="/taxonomy/term/2">Busan</a></li>
</ul></div>
<ul class="pager">
  <li class="pager-current">Page 1</li>
  <li class="pager-next"><a href="/area?page=1">››</a></li>
</ul>
"""

AREA_PAGE_TWO = """
<div class="item-list"><ul>
  <li><a href="/taxonomy/term/35">Chollabuk-Do</a></li>
</ul></div>
<ul class="pager">
  <li class="pager-current">Page 2</li>
  <li class="pager-next"><a href="/area?page=2">››</a></li>
</ul>
"""

AREA_EMPTY_PAGE_WITH_PAGER = """
<div class="view-empty">No terms</div>
<ul class="pager">
  <li class="pager-current">Page 3</li>
  <li class="pager-next"><a href="/area?page=3">››</a></li>
</ul>
"""

TERM_PAGE_TWO = """
<div class="item-list"><ol>
  <li><a href="/node/95">505 TOYS LTD.</a></li>
  <li><a href="/node/100">88 BUNKERING CO., LTD.</a></li>
</ol></div>
"""


class AreaSourceTests(unittest.TestCase):
    def test_parse_area_terms(self):
        areas = parse_area_terms(AREA_HTML, "https://kor.bizdirlib.com/area")
        self.assertEqual(
            areas,
            [
                AreaTerm(term_id=57, name="Bundang-Gu", url="https://kor.bizdirlib.com/taxonomy/term/57"),
                AreaTerm(term_id=2, name="Busan", url="https://kor.bizdirlib.com/taxonomy/term/2"),
            ],
        )

    def test_parse_term_listing(self):
        listing = parse_term_listing(TERM_HTML, "https://kor.bizdirlib.com/taxonomy/term/2")
        self.assertEqual(
            listing.company_urls,
            [
                "https://kor.bizdirlib.com/node/14",
                "https://kor.bizdirlib.com/node/33",
            ],
        )
        self.assertTrue(listing.has_next_page)

    def test_load_area_terms_follows_area_pagination(self):
        payloads = {
            "https://kor.bizdirlib.com/area": AREA_PAGE_ONE,
            "https://kor.bizdirlib.com/area?page=1": AREA_PAGE_TWO,
            "https://kor.bizdirlib.com/area?page=2": "<div class='view-empty'>done</div>",
        }

        def fake_fetch(url: str) -> FetchResult:
            return FetchResult(status_code=200, text=payloads[url])

        areas = load_area_terms(fake_fetch, "https://kor.bizdirlib.com/area")

        self.assertEqual([area.name for area in areas], ["Bundang-Gu", "Busan", "Chollabuk-Do"])

    def test_load_area_terms_stops_when_paginated_page_has_no_new_terms(self):
        payloads = {
            "https://kor.bizdirlib.com/area": AREA_PAGE_ONE,
            "https://kor.bizdirlib.com/area?page=1": AREA_PAGE_TWO,
            "https://kor.bizdirlib.com/area?page=2": AREA_EMPTY_PAGE_WITH_PAGER,
        }
        seen_urls = []

        def fake_fetch(url: str) -> FetchResult:
            seen_urls.append(url)
            return FetchResult(status_code=200, text=payloads[url])

        areas = load_area_terms(fake_fetch, "https://kor.bizdirlib.com/area")

        self.assertEqual([area.name for area in areas], ["Bundang-Gu", "Busan", "Chollabuk-Do"])
        self.assertEqual(
            seen_urls,
            [
                "https://kor.bizdirlib.com/area",
                "https://kor.bizdirlib.com/area?page=1",
                "https://kor.bizdirlib.com/area?page=2",
            ],
        )

    def test_collect_company_urls_for_area_auto_paginates_until_company_limit(self):
        payloads = {
            "https://kor.bizdirlib.com/taxonomy/term/2": TERM_HTML,
            "https://kor.bizdirlib.com/taxonomy/term/2?page=1": TERM_PAGE_TWO,
        }

        def fake_fetch(url: str) -> FetchResult:
            return FetchResult(status_code=200, text=payloads[url])

        urls = collect_company_urls_for_area(
            fetch_document=fake_fetch,
            area=AreaTerm(term_id=2, name="Busan", url="https://kor.bizdirlib.com/taxonomy/term/2"),
            page_limit=0,
            company_limit=3,
        )

        self.assertEqual(
            urls,
            [
                "https://kor.bizdirlib.com/node/14",
                "https://kor.bizdirlib.com/node/33",
                "https://kor.bizdirlib.com/node/95",
            ],
        )


class HttpxFetcherTests(unittest.TestCase):
    def test_routes_through_origin_and_host_header(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["host"] = request.headers["host"]
            return httpx.Response(200, text="ok")

        fetcher = HttpxFetcher(
            timeout=10,
            user_agent="test-agent",
            insecure=True,
            origin_base_url="https://test.databasesets.com",
            host_header="kor.bizdirlib.com",
            transport=httpx.MockTransport(handler),
        )
        result = fetcher.fetch("https://kor.bizdirlib.com/taxonomy/term/2")
        self.assertEqual(result.text, "ok")
        self.assertEqual(seen["url"], "https://test.databasesets.com/taxonomy/term/2")
        self.assertEqual(seen["host"], "kor.bizdirlib.com")


if __name__ == "__main__":
    unittest.main()
