import tempfile
import unittest
from pathlib import Path

from bizdir_crawler.area_sources import parse_area_terms
from bizdir_crawler.db import (
    append_job_event,
    create_job,
    export_job_csv,
    get_job,
    init_db,
    insert_job_rows,
    list_areas,
    list_job_areas,
    list_job_events,
    save_areas,
    update_job,
    update_job_area,
)
from bizdir_crawler.models import DetailRow


AREA_HTML = """
<div class="item-list"><ul>
  <li><a href="/taxonomy/term/2">Busan</a></li>
  <li><a href="/taxonomy/term/5">Daegu</a></li>
</ul></div>
"""


class JobStoreTests(unittest.TestCase):
    def test_job_lifecycle_and_csv_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.sqlite3"
            init_db(db_path)

            save_areas(db_path, parse_area_terms(AREA_HTML, "https://kor.bizdirlib.com/area"))
            areas = list_areas(db_path)
            self.assertEqual([area.name for area in areas], ["Busan", "Daegu"])

            job_id = create_job(db_path, area_ids=[2], page_limit=2, company_limit=5, workers=4)
            append_job_event(db_path, job_id, "info", "Collected first page")
            update_job(db_path, job_id, status="running", discovered_count=2)
            update_job_area(db_path, job_id, area_id=2, status="done", discovered_count=2, saved_count=1)
            insert_job_rows(
                db_path,
                job_id,
                "Busan",
                [
                    DetailRow(
                        detail_url="https://kor.bizdirlib.com/node/14",
                        company_name="21C HI-TECH CO., LTD.",
                        contact="Kim",
                        website="example.com",
                        area="Busan",
                    )
                ],
            )
            update_job(db_path, job_id, status="completed", processed_count=1, saved_count=1)

            job = get_job(db_path, job_id)
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.saved_count, 1)
            self.assertEqual(list_job_areas(db_path, job_id)[0].status, "done")
            self.assertEqual(list_job_events(db_path, job_id)[0]["message"], "Collected first page")
            self.assertIn("21C HI-TECH CO., LTD.", export_job_csv(db_path, job_id))


if __name__ == "__main__":
    unittest.main()
