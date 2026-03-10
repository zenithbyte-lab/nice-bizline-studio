# Non-Browser Crawler Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the monolithic browser-capable script with a clean non-browser crawler project, modularized so each source file stays under 200 lines, then verify multithreaded data extraction against origin-routed targets.

**Architecture:** Build a small Python package (`bizdir_crawler`) with isolated modules for parsing, transport, pipeline, persistence, and CLI. Keep runtime mode non-browser only, support origin routing (`origin base URL + Host header`), and provide `urllib` plus `curl` transports for reliability. Use thread pool workers for detail fetch.

**Tech Stack:** Python 3.14, standard library (`argparse`, `concurrent.futures`, `urllib`, `ssl`, `csv`), optional local `curl` binary for transport fallback, `unittest`.

### Task 1: Add Failing Tests First

**Files:**
- Modify: `tests/test_kor_bizdirlib_fetch.py`

Steps:
1. Add tests asserting origin-routed request behavior and CLI origin flags.
2. Add tests asserting noisy sitemap XML parsing and non-browser rate behavior.
3. Run the test module and confirm failures before implementation.

### Task 2: Implement Modular Package

**Files:**
- Create: `bizdir_crawler/__init__.py`
- Create: `bizdir_crawler/constants.py`
- Create: `bizdir_crawler/models.py`
- Create: `bizdir_crawler/parsing.py`
- Create: `bizdir_crawler/http_client.py`
- Create: `bizdir_crawler/storage.py`
- Create: `bizdir_crawler/pipeline.py`
- Create: `bizdir_crawler/cli.py`
- Modify: `kor_bizdirlib_fetch.py`

Steps:
1. Move parsing and data models into dedicated modules.
2. Implement HTTP transports (urllib/curl) with origin routing and retry.
3. Implement URL collection + threaded detail fetch pipeline.
4. Keep each file under 200 lines.
5. Replace root script with thin entrypoint delegating to package CLI.

### Task 3: Remove Unused Browser/Console Artifacts

**Files:**
- Delete obsolete browser/console scripts, legacy docs, and unrelated tests.

Steps:
1. Remove browser-only runtime code and helper scripts.
2. Remove unrelated modules and their tests.
3. Keep only crawler-focused docs/tests/artifacts.

### Task 4: Verify End-to-End

**Files:**
- Verify outputs under `tmp/`.

Steps:
1. Run unit tests (`python3 -m unittest discover -s tests -v`).
2. Run non-browser `collect-urls` against origin routing.
3. Run multithread `fetch-details` with small `--limit` and verify CSV rows are produced.
4. Summarize result counts and sample fields.
