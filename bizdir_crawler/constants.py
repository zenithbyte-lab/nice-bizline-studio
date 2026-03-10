from __future__ import annotations

import re

DEFAULT_SITEMAP_URL = "https://kor.bizdirlib.com/sitemap.xml"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)

SITEMAP_PAGE_RE = re.compile(r"sitemap\.xml\?page=\d+$")
DETAIL_NODE_RE = re.compile(r"/node/\d+$")
LOC_TAG_RE = re.compile(r"<loc(?:\s+[^>]*)?>\s*(.*?)\s*</loc>", re.IGNORECASE | re.DOTALL)

FIELD_LABELS = [
    "International Area Code",
    "Year of Establish",
    "Category Activities",
    "City/Province",
    "Company Name",
    "Product List",
    "Website",
    "Contact",
    "Country",
    "Address",
    "Mobile",
    "Phone",
    "Email",
    "Fax",
    "Type",
    "Area",
]
FIELD_PATTERN = re.compile(
    r"(" + "|".join(re.escape(label) for label in FIELD_LABELS) + r")\s*:\s*"
)

DETAIL_STOP_MARKERS = [
    "More Links",
    "Log in to post comments",
    "Languages",
    "Get South Korea Company Credit Report",
    "Series Websites",
]

BLOCKED_MARKERS = [
    "error 1015",
    "you are being rate limited",
    "used cloudflare to restrict access",
    "just a moment",
]
