# Kor Area Crawler Web App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a simple FastAPI + SQLite web app that lets the user select Kor BizDirLib areas, limit crawl scope, run a non-browser crawl through the exposed origin, track progress, and download CSV results.

**Architecture:** Keep the crawler as a small Python package. Use origin-routed HTTP requests with persistent `httpx` clients for speed, store jobs/rows in SQLite, and run crawl jobs in a background thread pool. Serve a minimal Jinja2 frontend with an editorial-style dashboard, checkbox area selection, job progress, and CSV export.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, SQLite, httpx, unittest.

### Task 1: Add failing parser and transport tests

**Files:**
- Create: `tests/test_area_sources.py`
- Modify: `bizdir_crawler/parsing.py`
- Modify: `bizdir_crawler/http_client.py`

**Step 1: Write the failing test**

Add tests for:
- parsing `/area` into area terms
- parsing `/taxonomy/term/{id}` into company detail URLs
- parsing pager state / next-page availability
- persistent `httpx` fetcher routing through origin + host header

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_area_sources.py -v`
Expected: FAIL because the new parser/fetcher APIs do not exist yet.

**Step 3: Write minimal implementation**

Add area list parsing, term pager helpers, and `httpx` pooled fetch support.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_area_sources.py -v`
Expected: PASS

### Task 2: Add failing storage and job-runner tests

**Files:**
- Create: `tests/test_job_store.py`
- Create: `bizdir_crawler/db.py`
- Create: `bizdir_crawler/jobs.py`

**Step 1: Write the failing test**

Add tests for:
- SQLite schema bootstrap
- saving/refeshing area cache
- creating a job with selected areas
- updating job progress and storing detail rows
- exporting a job to CSV rows

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_job_store.py -v`
Expected: FAIL because the DB and job APIs do not exist yet.

**Step 3: Write minimal implementation**

Add SQLite schema helpers and repository functions used by the runner.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_job_store.py -v`
Expected: PASS

### Task 3: Add failing web route tests

**Files:**
- Create: `tests/test_web_app.py`
- Create: `bizdir_crawler/web.py`
- Create: `bizdir_crawler/templates/base.html`
- Create: `bizdir_crawler/templates/index.html`
- Create: `bizdir_crawler/templates/job.html`
- Create: `bizdir_crawler/static/app.css`

**Step 1: Write the failing test**

Add tests for:
- `GET /` renders area list and recent jobs
- `POST /jobs` creates a job and redirects
- `GET /jobs/{id}` returns progress
- `GET /jobs/{id}/download.csv` returns CSV content

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_web_app.py -v`
Expected: FAIL because the web app is not implemented yet.

**Step 3: Write minimal implementation**

Add FastAPI app factory, background runner wiring, templates, and static CSS.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_web_app.py -v`
Expected: PASS

### Task 4: Wire CLI + docs

**Files:**
- Modify: `bizdir_crawler/cli.py`
- Modify: `kor_bizdirlib_fetch.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Step 1: Write the failing test**

Extend web/CLI tests to cover a `serve` command and default transport selection.

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL until CLI wiring is complete.

**Step 3: Write minimal implementation**

Add `serve` subcommand, document the startup command, and set project dependencies.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS

### Task 5: Live verification and benchmark

**Files:**
- Modify: `bizdir_crawler/http_client.py`
- Modify: `README.md`

**Step 1: Verify live crawl**

Run the web-backed crawler path against `https://test.databasesets.com` with `Host: kor.bizdirlib.com` and confirm rows are stored in SQLite.

**Step 2: Benchmark**

Compare `curl` subprocess requests against pooled `httpx` requests for the same taxonomy page and record median/average timings.

**Step 3: Final verification**

Run:
- `python3 -m unittest discover -s tests -v`
- `python3 kor_bizdirlib_fetch.py serve --help`

Expected: Tests pass; serve command available; live crawl stores rows; benchmark data supports the chosen default transport.
