from __future__ import annotations

import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable

import httpx

from .constants import DEFAULT_USER_AGENT
from .models import FetchResult


def route_request(
    url: str,
    origin_base_url: str | None,
    host_header: str | None,
) -> tuple[str, str | None]:
    request_host = host_header.strip() if isinstance(host_header, str) and host_header.strip() else None
    if not origin_base_url:
        return url, request_host

    origin = urllib.parse.urlsplit(origin_base_url)
    if not origin.scheme or not origin.netloc:
        raise ValueError(f"invalid origin base url: {origin_base_url}")

    target = urllib.parse.urlsplit(url)
    routed_url = urllib.parse.urlunsplit(
        (origin.scheme, origin.netloc, target.path or "/", target.query, "")
    )
    return routed_url, request_host or target.netloc


def build_opener(user_agent: str = DEFAULT_USER_AGENT, insecure: bool = False) -> urllib.request.OpenerDirector:
    handlers: list[object] = []
    if insecure:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=context))

    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [
        ("User-Agent", user_agent),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "en-US,en;q=0.9"),
        ("Cache-Control", "no-cache"),
        ("Pragma", "no-cache"),
    ]
    return opener


def fetch_via_urllib(
    opener: urllib.request.OpenerDirector,
    url: str,
    timeout: float,
    origin_base_url: str | None,
    host_header: str | None,
) -> FetchResult:
    request_url, request_host = route_request(url, origin_base_url, host_header)
    request = urllib.request.Request(request_url, method="GET")
    if request_host:
        request.add_header("Host", request_host)

    with opener.open(request, timeout=timeout) as response:
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return FetchResult(status_code=response.getcode(), text=body.decode(charset, errors="replace"))


def fetch_via_curl(
    url: str,
    timeout: float,
    origin_base_url: str | None,
    host_header: str | None,
    insecure: bool,
) -> FetchResult:
    request_url, request_host = route_request(url, origin_base_url, host_header)
    cmd = [
        "curl",
        "-sS",
        "-L",
        "--http1.1",
        "--max-time",
        str(int(max(1, timeout))),
        "--retry",
        "3",
        "--retry-delay",
        "1",
        "--retry-all-errors",
    ]
    if insecure:
        cmd.append("-k")
    if request_host:
        cmd.extend(["-H", f"Host: {request_host}"])
    cmd.append(request_url)

    completed = subprocess.run(cmd, check=False, capture_output=True)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl failed({completed.returncode}) for {request_url}: {stderr}")

    text = completed.stdout.decode("utf-8", errors="replace")
    if not text.strip():
        raise RuntimeError(f"curl returned empty body for {request_url}")
    return FetchResult(status_code=200, text=text)


class HttpxFetcher:
    def __init__(
        self,
        timeout: float,
        user_agent: str = DEFAULT_USER_AGENT,
        insecure: bool = False,
        origin_base_url: str | None = None,
        host_header: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.insecure = insecure
        self.origin_base_url = origin_base_url
        self.host_header = host_header
        self.transport = transport
        self._local = threading.local()
        self._clients: list[httpx.Client] = []
        self._lock = threading.Lock()

    def _build_client(self) -> httpx.Client:
        client = httpx.Client(
            verify=not self.insecure,
            timeout=self.timeout,
            http2=False,
            transport=self.transport,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            follow_redirects=True,
        )
        with self._lock:
            self._clients.append(client)
        return client

    def _client(self) -> httpx.Client:
        client = getattr(self._local, "client", None)
        if client is None:
            client = self._build_client()
            self._local.client = client
        return client

    def fetch(self, url: str) -> FetchResult:
        request_url, request_host = route_request(url, self.origin_base_url, self.host_header)
        headers = {"Host": request_host} if request_host else None
        response = self._client().get(request_url, headers=headers)
        return FetchResult(status_code=response.status_code, text=response.text)

    def close(self) -> None:
        with self._lock:
            clients = self._clients[:]
            self._clients.clear()
        for client in clients:
            client.close()


def fetch_with_retry(
    fetch_once: Callable[[str], FetchResult],
    url: str,
    retries: int,
    retry_backoff: float,
) -> FetchResult:
    max_attempts = max(1, retries)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fetch_once(url)
        except Exception as exc:  # pragma: no cover - network dependent
            last_error = exc
            if attempt < max_attempts and retry_backoff > 0:
                time.sleep(retry_backoff)
    assert last_error is not None
    raise RuntimeError(f"failed to fetch {url} after {max_attempts} attempts: {last_error}")
