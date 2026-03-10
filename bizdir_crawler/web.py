from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .constants import DEFAULT_USER_AGENT
from .db import create_job, export_job_csv, get_job, init_db, list_areas, list_jobs, list_job_events
from .http_client import HttpxFetcher
from .jobs import ThreadedJobRunner, sync_areas


@dataclass(frozen=True)
class AppSettings:
    db_path: Path
    origin_base_url: str
    origin_host_header: str
    page_limit: int = 0
    company_limit: int | None = 20
    workers: int = 6
    area_index_url: str = "https://kor.bizdirlib.com/area"
    timeout: float = 20.0
    insecure: bool = True
    user_agent: str = DEFAULT_USER_AGENT


def _make_fetcher(settings: AppSettings) -> HttpxFetcher:
    return HttpxFetcher(
        timeout=settings.timeout,
        user_agent=settings.user_agent,
        insecure=settings.insecure,
        origin_base_url=settings.origin_base_url,
        host_header=settings.origin_host_header,
    )


def create_app(settings: AppSettings, runner=None) -> FastAPI:
    init_db(settings.db_path)
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
    app = FastAPI(title="Kor BizDirLib Area Crawler")
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
    app.state.settings = settings
    app.state.runner = runner or ThreadedJobRunner(settings.db_path, lambda: _make_fetcher(settings))

    def ensure_areas() -> tuple[list, str | None]:
        areas = list_areas(settings.db_path)
        if areas:
            return areas, None
        fetcher = _make_fetcher(settings)
        try:
            return sync_areas(settings.db_path, settings.area_index_url, fetcher.fetch), None
        except Exception as exc:
            return [], str(exc)
        finally:
            fetcher.close()

    @app.get("/")
    def home(request: Request, job_id: str | None = None):
        areas, error = ensure_areas()
        jobs = list_jobs(settings.db_path)
        active_job_id = job_id or (jobs[0].id if jobs else "")
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "areas": areas,
                "error": error,
                "jobs": jobs,
                "defaults": settings,
                "active_job_id": active_job_id,
            },
        )

    @app.post("/areas/refresh")
    def refresh_areas():
        fetcher = _make_fetcher(settings)
        try:
            sync_areas(settings.db_path, settings.area_index_url, fetcher.fetch)
        finally:
            fetcher.close()
        return RedirectResponse("/", status_code=303)

    @app.post("/jobs")
    def start_job(
        area_ids: list[int] = Form(...),
        company_limit: int | None = Form(None),
        workers: int = Form(...),
    ):
        areas, error = ensure_areas()
        if not areas:
            raise HTTPException(status_code=503, detail=error or "areas unavailable")
        page_limit = 0
        job_id = create_job(settings.db_path, area_ids=area_ids, page_limit=page_limit, company_limit=company_limit, workers=workers)
        job_settings = AppSettings(
            db_path=settings.db_path,
            origin_base_url=settings.origin_base_url,
            origin_host_header=settings.origin_host_header,
            page_limit=page_limit,
            company_limit=company_limit,
            workers=workers,
            area_index_url=settings.area_index_url,
            timeout=settings.timeout,
            insecure=settings.insecure,
            user_agent=settings.user_agent,
        )
        app.state.runner.start(job_id, area_ids, job_settings)
        return RedirectResponse(f"/?job_id={job_id}", status_code=303)

    @app.get("/jobs/{job_id}")
    def job_detail(job_id: str):
        return RedirectResponse(f"/?job_id={job_id}", status_code=303)

    @app.get("/api/jobs/{job_id}")
    def job_api(job_id: str):
        payload = {
            "job": asdict(get_job(settings.db_path, job_id)),
            "events": list_job_events(settings.db_path, job_id),
            "download_url": f"/jobs/{job_id}/download.csv",
        }
        return JSONResponse(payload)

    @app.get("/jobs/{job_id}/download.csv")
    def download_job(job_id: str):
        payload = export_job_csv(settings.db_path, job_id)
        headers = {"Content-Disposition": f'attachment; filename="{job_id}.csv"'}
        return Response(content=payload, media_type="text/csv; charset=utf-8", headers=headers)

    return app
