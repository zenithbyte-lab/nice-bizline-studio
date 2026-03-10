# KorBizDir Studio

A small non-browser crawler project for `kor.bizdirlib.com` with both CLI and web UI.

## Features

- Non-browser only, routed through the exposed origin with a custom `Host` header
- Faster default transport with pooled `httpx` clients; `curl` and `urllib` still available as fallbacks
- `/area` based workflow: select one or more areas, limit pages / companies, then crawl detail pages
- SQLite storage for jobs, progress, and rows
- Single-page FastAPI dashboard: left controls, right live log panel, CSV download
- Windows launcher entry for packaged `.exe`: clears the default port, starts the app, opens the browser
- CLI for sitemap mode, detail mode, and `serve`
- Core source files all kept under 200 lines

## Quick Start

Start the web app:

```bash
python3 kor_bizdirlib_fetch.py serve \
  --db-path data/kor_bizdir.sqlite3 \
  --origin-base-url https://test.databasesets.com \
  --origin-host-header kor.bizdirlib.com \
  --host 127.0.0.1 \
  --port 8000 \
  --insecure
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Windows EXE Build

The repo now includes a GitHub Actions workflow at `.github/workflows/build-windows-exe.yml`.
On `workflow_dispatch` or a push to `main` / `master`, it builds a Windows `.exe` with PyInstaller and uploads `KorBizDirStudio-windows.zip` as an artifact.

The packaged launcher:

- binds to `127.0.0.1:8000`
- clears any existing Windows process already listening on port `8000`
- starts the FastAPI app
- opens the browser automatically once the local server is ready

If you want the original sitemap flow, collect detail URLs first:

```bash
python3 kor_bizdirlib_fetch.py collect-urls \
  --sitemap-index-url https://kor.bizdirlib.com/sitemap.xml \
  --output tmp/urls.txt \
  --origin-base-url https://test.databasesets.com \
  --origin-host-header kor.bizdirlib.com \
  --transport httpx --insecure
```

Then fetch detail pages into CSV:

```bash
python3 kor_bizdirlib_fetch.py fetch-details \
  --input-urls tmp/urls.txt \
  --output-csv tmp/details.csv \
  --resume-state tmp/state.json \
  --workers 8 --limit 100 \
  --origin-base-url https://test.databasesets.com \
  --origin-host-header kor.bizdirlib.com \
  --transport httpx --insecure
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Project Layout

- `bizdir_crawler/area_sources.py`: area and taxonomy page parsing
- `bizdir_crawler/http_client.py`: origin routing and pooled HTTP fetchers
- `bizdir_crawler/db.py`: SQLite schema and job persistence
- `bizdir_crawler/jobs.py`: background crawl runner
- `bizdir_crawler/web.py`: FastAPI app factory
- `bizdir_crawler/templates/`: frontend templates
- `bizdir_crawler/static/app.css`: frontend styles
