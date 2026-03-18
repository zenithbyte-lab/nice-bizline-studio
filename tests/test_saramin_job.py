"""Tests for Saramin job creation, row insertion, and CSV export in db.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

from bizdir_crawler.db import (
    create_saramin_job,
    export_saramin_csv,
    get_job,
    init_db,
    insert_saramin_rows,
    save_areas,
)
from bizdir_crawler.models import AreaTerm, SaraminRow


def _tmp_db() -> Path:
    return Path(tempfile.mktemp(suffix=".db"))


def test_create_saramin_job():
    db = _tmp_db()
    init_db(db)
    # Need at least one area for list_areas() — saramin uses fake areas
    save_areas(db, [AreaTerm(term_id=1, name="test", url="http://example.com")])

    job_id = create_saramin_job(db, region_codes=["101000", "102000"], company_limit=10, workers=2)
    assert job_id
    job = get_job(db, job_id)
    assert job.source == "saramin"
    assert job.selected_count == 2
    assert job.status == "queued"


def test_create_saramin_job_invalid_region():
    db = _tmp_db()
    init_db(db)
    save_areas(db, [AreaTerm(term_id=1, name="test", url="http://example.com")])
    try:
        create_saramin_job(db, region_codes=["999999"], company_limit=10, workers=2)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_insert_and_export_saramin_rows():
    db = _tmp_db()
    init_db(db)
    save_areas(db, [AreaTerm(term_id=1, name="test", url="http://example.com")])
    job_id = create_saramin_job(db, region_codes=["101000"], company_limit=10, workers=2)

    rows = [
        SaraminRow(company_name="CompA", ceo_name="CEO1", website="https://a.com", source_url="https://saramin/1"),
        SaraminRow(company_name="CompB", ceo_name="CEO2", website="https://b.com", source_url="https://saramin/2"),
    ]
    saved = insert_saramin_rows(db, job_id, rows)
    assert saved == 2

    # Duplicate insert
    saved_dup = insert_saramin_rows(db, job_id, rows)
    assert saved_dup == 0

    # Export CSV
    csv_text = export_saramin_csv(db, job_id)
    assert "CompA" in csv_text
    assert "CompB" in csv_text
    assert "source_url" in csv_text  # Header


def test_bizdir_job_source_default():
    """Verify that standard bizdir jobs get source='bizdir'."""
    db = _tmp_db()
    init_db(db)
    save_areas(db, [AreaTerm(term_id=1, name="test", url="http://example.com")])
    from bizdir_crawler.db import create_job

    job_id = create_job(db, area_ids=[1], page_limit=0, company_limit=10, workers=2)
    job = get_job(db, job_id)
    assert job.source == "bizdir"


def test_export_job_csv_dispatches_by_source():
    """export_job_csv should use the saramin exporter for saramin jobs."""
    from bizdir_crawler.db import export_job_csv

    db = _tmp_db()
    init_db(db)
    save_areas(db, [AreaTerm(term_id=1, name="test", url="http://example.com")])
    job_id = create_saramin_job(db, region_codes=["101000"], company_limit=10, workers=2)

    rows = [SaraminRow(company_name="X", ceo_name="Y", website="https://x.com", source_url="https://s/1")]
    insert_saramin_rows(db, job_id, rows)

    csv_text = export_job_csv(db, job_id)
    assert "ceo_name" in csv_text  # saramin CSV header
    assert "contact" not in csv_text  # not bizdir CSV header
