"""Tests for saramin_parsing module."""

from __future__ import annotations

from bizdir_crawler.saramin_parsing import parse_company_detail, parse_list_page


# ---------------------------------------------------------------------------
# List-page parsing
# ---------------------------------------------------------------------------


SAMPLE_LIST_HTML = """
<html>
<body>
<div class="content">
  <div class="list_item">
    <a href="/zf_user/company-info/view?csn=abc123" class="str_tit">회사A</a>
  </div>
  <div class="list_item">
    <a href="/zf_user/company-info/view?csn=def456" class="str_tit">회사B</a>
  </div>
  <div class="list_item">
    <a href="/zf_user/company-info/view?csn=abc123" class="str_tit">회사A dup</a>
  </div>
  <div class="pagination">
    <a href="/zf_user/jobs/list/domestic?page=2&loc_mcd=101000" class="pg_next">다음</a>
  </div>
</div>
</body>
</html>
"""


def test_parse_list_page_extracts_company_urls():
    urls, next_page = parse_list_page(SAMPLE_LIST_HTML)
    # abc123 appears twice but should be deduped, plus def456 = 2 unique URLs
    assert len(urls) == 2
    assert all("company-info/view" in u for u in urls)
    assert next_page is not None
    assert "page=2" in next_page


def test_parse_list_page_no_next():
    html = """
    <html><body>
    <a href="/zf_user/company-info/view?csn=xyz789">Company</a>
    </body></html>
    """
    urls, next_page = parse_list_page(html)
    assert len(urls) == 1
    assert next_page is None


def test_parse_list_page_empty():
    urls, next_page = parse_list_page("<html><body>No results</body></html>")
    assert urls == []
    assert next_page is None


# ---------------------------------------------------------------------------
# Company detail parsing
# ---------------------------------------------------------------------------


SAMPLE_DETAIL_HTML = """
<html>
<head>
<script type="application/ld+json">
{
  "@type": "Organization",
  "name": "테스트 주식회사",
  "url": "https://example.com",
  "founder": {"@type": "Person", "name": "김철수"}
}
</script>
</head>
<body>
<h1 class="company_name">테스트 주식회사</h1>
<p>대표자 : 김철수</p>
<a href="https://example.com" class="homepage">홈페이지</a>
</body>
</html>
"""


def test_parse_company_detail_with_ldjson():
    row = parse_company_detail(SAMPLE_DETAIL_HTML, "https://saramin.co.kr/view/123")
    assert row is not None
    assert row.company_name == "테스트 주식회사"
    assert row.ceo_name == "김철수"
    assert row.website == "https://example.com"
    assert row.source_url == "https://saramin.co.kr/view/123"


def test_parse_company_detail_html_only():
    html = """
    <html><body>
    <h2 class="company_name">HTML회사</h2>
    <p>대표이사 : 박영희</p>
    <a href="https://htmlcompany.kr">방문</a>
    </body></html>
    """
    row = parse_company_detail(html, "https://saramin.co.kr/view/456")
    assert row is not None
    assert row.company_name == "HTML회사"
    assert row.ceo_name == "박영희"


def test_parse_company_detail_returns_none_for_empty():
    assert parse_company_detail("", "url") is None
    assert parse_company_detail("short", "url") is None


def test_parse_company_detail_returns_none_for_no_data():
    html = "<html><body><p>" + ("Lorem ipsum dolor sit amet. " * 10) + "</p></body></html>"
    result = parse_company_detail(html, "url")
    # No company info found → should be None
    assert result is None


def test_parse_company_detail_missing_field_defaults():
    html = """
    <html><body>
    <span class="company_name">OnlyNameCo</span>
    <p>일반 텍스트입니다. 아무 정보도 없습니다.</p>
    </body></html>
    """
    row = parse_company_detail(html, "https://saramin.co.kr/test")
    assert row is not None
    assert row.company_name == "OnlyNameCo"
    assert row.ceo_name == "无"  # MISSING default
