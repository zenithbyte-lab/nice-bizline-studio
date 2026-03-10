import csv
import tempfile
import unittest
from pathlib import Path

from bizdir_crawler.http_client import route_request
from bizdir_crawler.parsing import extract_detail_urls, extract_sitemap_page_urls, parse_detail_payload
from bizdir_crawler.pipeline import fetch_details_with_threads
from bizdir_crawler.storage import append_rows


SITEMAP_INDEX_NOISY = """noise before xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://kor.bizdirlib.com/sitemap.xml?page=1</loc></sitemap>
  <sitemap><loc>https://kor.bizdirlib.com/sitemap.xml?page=2</loc></sitemap>
</sitemapindex>
"""

SITEMAP_PAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://kor.bizdirlib.com/node/11</loc></url>
  <url><loc>https://kor.bizdirlib.com/node/12</loc></url>
</urlset>
"""

DETAIL_HTML = """<!DOCTYPE html><html><body>
Company Information
Company Name: ACME CO., LTD.
Country: South Korea
Contact: Jane Doe
Website: www.acme.example
Type: Export
Area: Seoul
</body></html>"""


class RoutingTests(unittest.TestCase):
    def test_route_request_uses_origin_and_host(self):
        routed_url, host = route_request(
            url="https://kor.bizdirlib.com/sitemap.xml?page=7",
            origin_base_url="https://test.databasesets.com",
            host_header="kor.bizdirlib.com",
        )
        self.assertEqual(routed_url, "https://test.databasesets.com/sitemap.xml?page=7")
        self.assertEqual(host, "kor.bizdirlib.com")


class ParsingTests(unittest.TestCase):
    def test_extract_sitemap_page_urls_supports_noisy_xml(self):
        urls = extract_sitemap_page_urls(SITEMAP_INDEX_NOISY, "https://kor.bizdirlib.com/sitemap.xml")
        self.assertEqual(
            urls,
            [
                "https://kor.bizdirlib.com/sitemap.xml?page=1",
                "https://kor.bizdirlib.com/sitemap.xml?page=2",
            ],
        )

    def test_extract_detail_urls_from_xml(self):
        urls = extract_detail_urls(SITEMAP_PAGE_XML, "https://kor.bizdirlib.com/sitemap.xml?page=1")
        self.assertEqual(urls, ["https://kor.bizdirlib.com/node/11", "https://kor.bizdirlib.com/node/12"])

    def test_parse_detail_payload(self):
        row = parse_detail_payload(DETAIL_HTML, "https://kor.bizdirlib.com/node/11")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.company_name, "ACME CO., LTD.")
        self.assertEqual(row.contact, "Jane Doe")
        self.assertEqual(row.website, "www.acme.example")
        self.assertEqual(row.area, "Seoul")


class PipelineTests(unittest.TestCase):
    def test_fetch_details_with_threads_and_write_csv(self):
        def fake_fetch(url: str):
            return 200, DETAIL_HTML.replace("ACME", f"ACME-{url.rsplit('/', 1)[-1]}")

        urls = [
            "https://kor.bizdirlib.com/node/21",
            "https://kor.bizdirlib.com/node/22",
            "https://kor.bizdirlib.com/node/23",
        ]
        rows = fetch_details_with_threads(urls=urls, fetch_detail=fake_fetch, workers=3, retries=1)
        self.assertEqual(len(rows), 3)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "details.csv"
            append_rows(output, rows)
            with output.open("r", encoding="utf-8", newline="") as handle:
                result_rows = list(csv.DictReader(handle))
        self.assertEqual(len(result_rows), 3)
        self.assertEqual(result_rows[0]["detail_url"], "https://kor.bizdirlib.com/node/21")


if __name__ == "__main__":
    unittest.main()
