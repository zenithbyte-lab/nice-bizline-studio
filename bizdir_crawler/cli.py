from __future__ import annotations

import argparse
from pathlib import Path

from .constants import DEFAULT_SITEMAP_URL, DEFAULT_USER_AGENT
from .http_client import HttpxFetcher, build_opener, fetch_via_curl, fetch_via_urllib
from .models import FetchResult
from .pipeline import collect_detail_urls, fetch_details_with_threads
from .storage import append_rows, load_state, read_urls, save_state, write_urls
from .web import AppSettings, create_app


class _FetcherAdapter:
    def __init__(self, fetch):
        self.fetch = fetch

    def close(self) -> None:
        return None


def add_origin_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--origin-base-url", default=None)
    parser.add_argument("--origin-host-header", default=None)


def add_common_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--transport", choices=["httpx", "curl", "urllib"], default="httpx")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    add_origin_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BizDirLib non-browser crawler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect-urls", help="Collect detail URLs from sitemap")
    collect.add_argument("--sitemap-index-url", default=DEFAULT_SITEMAP_URL)
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--max-sitemaps", type=int, default=None)
    collect.add_argument("--stop-after-empty", type=int, default=2)
    add_common_network_args(collect)

    fetch = subparsers.add_parser("fetch-details", help="Fetch detail pages into CSV")
    fetch.add_argument("--input-urls", type=Path, required=True)
    fetch.add_argument("--output-csv", type=Path, required=True)
    fetch.add_argument("--resume-state", type=Path, required=True)
    fetch.add_argument("--workers", type=int, default=8)
    fetch.add_argument("--limit", type=int, default=None)
    add_common_network_args(fetch)

    serve = subparsers.add_parser("serve", help="Run the SQLite + FastAPI web app")
    serve.add_argument("--db-path", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--page-limit", type=int, default=0)
    serve.add_argument("--company-limit", type=int, default=20)
    serve.add_argument("--workers", type=int, default=8)
    serve.add_argument("--timeout", type=float, default=20.0)
    serve.add_argument("--insecure", action="store_true")
    serve.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    add_origin_args(serve)

    saramin = subparsers.add_parser("saramin", help="Crawl Saramin company listings by region")
    saramin.add_argument("--output-csv", type=Path, required=True, help="Output CSV file path")
    saramin.add_argument("--regions", nargs="+", default=["101000"], help="Region codes (e.g. 101000 for Seoul)")
    saramin.add_argument("--company-limit", type=int, default=20, help="Max companies per region")
    saramin.add_argument("--workers", type=int, default=4)
    saramin.add_argument("--timeout", type=float, default=20.0)
    saramin.add_argument("--insecure", action="store_true")
    saramin.add_argument("--user-agent", default=DEFAULT_USER_AGENT)

    return parser


def make_fetcher(args: argparse.Namespace):
    if args.transport == "httpx":
        return HttpxFetcher(
            timeout=args.timeout,
            user_agent=args.user_agent,
            insecure=args.insecure,
            origin_base_url=args.origin_base_url,
            host_header=args.origin_host_header,
        )
    if args.transport == "curl":
        return _FetcherAdapter(
            lambda url: fetch_via_curl(
                url=url,
                timeout=args.timeout,
                origin_base_url=args.origin_base_url,
                host_header=args.origin_host_header,
                insecure=args.insecure,
            )
        )

    opener = build_opener(user_agent=args.user_agent, insecure=args.insecure)
    return _FetcherAdapter(
        lambda url: fetch_via_urllib(
            opener=opener,
            url=url,
            timeout=args.timeout,
            origin_base_url=args.origin_base_url,
            host_header=args.origin_host_header,
        )
    )


def run_collect(args: argparse.Namespace) -> int:
    fetch_document = make_fetcher(args)

    def fetch_with_retries(url: str) -> FetchResult:
        from .http_client import fetch_with_retry

        return fetch_with_retry(fetch_document.fetch, url, retries=args.retries, retry_backoff=args.retry_backoff)

    try:
        urls = collect_detail_urls(
            sitemap_index_url=args.sitemap_index_url,
            max_sitemaps=args.max_sitemaps,
            stop_after_empty=args.stop_after_empty,
            fetch_document=fetch_with_retries,
        )
        write_urls(args.output, urls)
        print(f"wrote {len(urls)} detail URLs to {args.output}")
        return 0
    finally:
        fetch_document.close()


def run_fetch(args: argparse.Namespace) -> int:
    urls = read_urls(args.input_urls)
    state = load_state(args.resume_state)
    start_index = state.get("next_index", 0)
    fetch_document = make_fetcher(args)

    try:
        rows = fetch_details_with_threads(
            urls=urls,
            fetch_detail=fetch_document.fetch,
            workers=max(1, args.workers),
            retries=max(1, args.retries),
            retry_backoff=max(0.0, args.retry_backoff),
            start_index=max(0, start_index),
            limit=args.limit,
        )

        append_rows(args.output_csv, rows)
        next_index = start_index + (args.limit if args.limit is not None else len(urls[start_index:]))
        if args.limit is None:
            next_index = len(urls)
        save_state(args.resume_state, min(next_index, len(urls)))

        print(f"wrote {len(rows)} rows to {args.output_csv}")
        print(f"resume next_index={min(next_index, len(urls))}")
        return 0
    finally:
        fetch_document.close()


def run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    app = create_app(
        AppSettings(
            db_path=args.db_path,
            origin_base_url=args.origin_base_url,
            origin_host_header=args.origin_host_header,
            page_limit=args.page_limit,
            company_limit=args.company_limit,
            workers=args.workers,
            timeout=args.timeout,
            insecure=args.insecure,
            user_agent=args.user_agent,
        )
    )
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def run_saramin_cli(args: argparse.Namespace) -> int:
    import csv

    from .http_client import fetch_with_retry
    from .saramin_constants import SARAMIN_REGIONS
    from .saramin_parsing import parse_company_detail, parse_list_page
    from .saramin_constants import BASE_ORIGIN, LIST_ENDPOINT

    fetcher = HttpxFetcher(timeout=args.timeout, user_agent=args.user_agent, insecure=args.insecure)
    region_map = {r["code"]: r["name"] for r in SARAMIN_REGIONS}
    all_rows = []

    try:
        for region_code in args.regions:
            region_name = region_map.get(region_code, region_code)
            print(f"Scanning region {region_name} ({region_code})...")
            list_url: str | None = (
                f"{BASE_ORIGIN}{LIST_ENDPOINT}?"
                f"loc_mcd={region_code}&panel_type=&search_optional_item=n"
                f"&search_done=y&panel_count=y&preview=y"
            )
            company_urls: list[str] = []
            page_count = 0

            while list_url:
                page_count += 1
                try:
                    result = fetch_with_retry(fetcher.fetch, list_url, retries=3, retry_backoff=0.5)
                except Exception as exc:
                    print(f"  List page {page_count} failed: {exc}")
                    break
                urls, next_page = parse_list_page(result.text)
                company_urls.extend(urls)
                print(f"  Page {page_count}: found {len(urls)} companies (total {len(company_urls)})")
                if args.company_limit and len(company_urls) >= args.company_limit:
                    company_urls = company_urls[:args.company_limit]
                    break
                list_url = next_page

            print(f"  Fetching {len(company_urls)} company details...")
            for ci, cu in enumerate(company_urls, 1):
                try:
                    detail_result = fetch_with_retry(fetcher.fetch, cu, retries=2, retry_backoff=0.3)
                    row = parse_company_detail(detail_result.text, cu)
                    if row:
                        all_rows.append(row)
                except Exception as exc:
                    print(f"  Detail {ci}/{len(company_urls)} failed: {exc}")

        # Write CSV
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source_url", "company_name", "ceo_name", "website"])
            for row in all_rows:
                writer.writerow([row.source_url, row.company_name, row.ceo_name, row.website])

        print(f"Wrote {len(all_rows)} rows to {args.output_csv}")
        return 0
    finally:
        fetcher.close()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if hasattr(args, "origin_base_url") and args.origin_base_url:
        from urllib.parse import urlsplit

        parsed = urlsplit(args.origin_base_url)
        if not parsed.scheme or not parsed.netloc:
            parser.error("--origin-base-url must include scheme and host")
    if args.command == "serve" and (not args.origin_base_url or not args.origin_host_header):
        parser.error("serve requires --origin-base-url and --origin-host-header")

    if args.command == "collect-urls":
        return run_collect(args)
    if args.command == "fetch-details":
        return run_fetch(args)
    if args.command == "serve":
        return run_serve(args)
    if args.command == "saramin":
        return run_saramin_cli(args)

    parser.error(f"unsupported command: {args.command}")
    return 2
