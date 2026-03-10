#!/usr/bin/env python3
"""Entrypoint for BizDirLib non-browser crawler."""

from __future__ import annotations

from bizdir_crawler.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
