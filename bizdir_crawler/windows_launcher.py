from __future__ import annotations

import ctypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .web import AppSettings, create_app

DEFAULT_PORT = 8000
DEFAULT_COMPANY_LIMIT = 50
DEFAULT_WORKERS = 8
DEFAULT_ORIGIN_BASE_URL = "https://test.databasesets.com"
DEFAULT_ORIGIN_HOST_HEADER = "kor.bizdirlib.com"
APP_TITLE = "KorBizDir Studio"


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def build_runtime_settings(base_dir: Path, port: int = DEFAULT_PORT) -> AppSettings:
    db_path = base_dir / "data" / "kor_bizdir.sqlite3"
    return AppSettings(
        db_path=db_path,
        origin_base_url=os.getenv("KOR_BIZDIR_ORIGIN_BASE_URL", DEFAULT_ORIGIN_BASE_URL),
        origin_host_header=os.getenv("KOR_BIZDIR_ORIGIN_HOST_HEADER", DEFAULT_ORIGIN_HOST_HEADER),
        page_limit=0,
        company_limit=int(os.getenv("KOR_BIZDIR_COMPANY_LIMIT", str(DEFAULT_COMPANY_LIMIT))),
        workers=int(os.getenv("KOR_BIZDIR_WORKERS", str(DEFAULT_WORKERS))),
    )


def parse_listening_pids(netstat_output: str, port: int) -> list[int]:
    pattern = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.MULTILINE | re.IGNORECASE)
    return sorted({int(pid) for pid in pattern.findall(netstat_output)})


def cleanup_port(port: int) -> list[int]:
    if os.name != "nt":
        return []
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = [pid for pid in parse_listening_pids(completed.stdout, port) if pid != os.getpid()]
    cleaned: list[int] = []
    for pid in pids:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            cleaned.append(pid)
    return cleaned


def wait_for_server(host: str, port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def open_browser_when_ready(url: str, host: str, port: int) -> None:
    if wait_for_server(host, port):
        webbrowser.open(url)


def show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)


def run_windows_app(port: int = DEFAULT_PORT) -> int:
    base_dir = app_base_dir()
    settings = build_runtime_settings(base_dir, port=port)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    cleanup_port(port)
    url = f"http://127.0.0.1:{port}"
    threading.Thread(
        target=open_browser_when_ready,
        args=(url, "127.0.0.1", port),
        daemon=True,
    ).start()
    app = create_app(settings)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


def main() -> int:
    port = int(os.getenv("KOR_BIZDIR_PORT", str(DEFAULT_PORT)))
    try:
        return run_windows_app(port=port)
    except Exception as exc:  # pragma: no cover - runtime safety for packaged app
        show_error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
