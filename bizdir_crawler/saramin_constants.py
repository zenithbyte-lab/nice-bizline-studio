from __future__ import annotations

BASE_ORIGIN = "https://www.saramin.co.kr"
LIST_ENDPOINT = "/zf_user/jobs/list/domestic"
COMPANY_INFO_PATH = "/zf_user/company-info/view"
RELAY_VIEW_AJAX_PATH = "/zf_user/jobs/relay/view-ajax"
TRACK_HOMEPAGE_PATH = "/zf_user/track-apply-form/render-homepage"

DEFAULT_START_URL = (
    f"{BASE_ORIGIN}{LIST_ENDPOINT}?"
    "loc_mcd=101000&panel_type=&search_optional_item=n&search_done=y&panel_count=y&preview=y"
)

SARAMIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8,zh-CN;q=0.7",
    "Accept": "application/json, text/javascript, */*;q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_ORIGIN,
    "Referer": f"{BASE_ORIGIN}/",
}

MISSING = "无"
RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}

OFFICIAL_WEB_HOST_EXCLUDES = {
    "saramin.co.kr",
    "hiring.saramin.co.kr",
    "career.saramin.co.kr",
    "billing.saramin.co.kr",
    "business.saramin.co.kr",
    "map.kakao.com",
    "kakaomap.com",
    "smartstore.naver.com",
    "blog.naver.com",
    "cafe.naver.com",
    "m.blog.naver.com",
    "naver.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "youtube-nocookie.com",
    "x.com",
    "twitter.com",
    "kakao.com",
    "facebook.co.kr",
    "instagram.co.kr",
    "youtube.co.kr",
    "twitter.co.kr",
    "linkedin.com",
}

# Saramin region codes for the web UI
SARAMIN_REGIONS = [
    {"code": "101000", "name": "서울"},
    {"code": "102000", "name": "경기"},
    {"code": "103000", "name": "인천"},
    {"code": "104000", "name": "대구"},
    {"code": "105000", "name": "강원"},
    {"code": "106000", "name": "부산"},
    {"code": "107000", "name": "광주"},
    {"code": "108000", "name": "울산"},
    {"code": "109000", "name": "경남"},
    {"code": "110000", "name": "경북"},
    {"code": "111000", "name": "전남"},
    {"code": "112000", "name": "전북"},
    {"code": "113000", "name": "충북"},
    {"code": "114000", "name": "충남"},
    {"code": "115000", "name": "대전"},
    {"code": "116000", "name": "제주"},
    {"code": "117000", "name": "세종"},
]
