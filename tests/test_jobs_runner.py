import tempfile
import unittest
from pathlib import Path

from bizdir_crawler.db import create_job, get_job, init_db, list_job_rows, save_areas
from bizdir_crawler.jobs import run_job
from bizdir_crawler.models import AreaTerm, FetchResult
from bizdir_crawler.web import AppSettings


TERM_HTML = """
<div class="item-list"><ol>
  <li><a href="/node/14">21C HI-TECH CO., LTD.</a></li>
  <li><a href="/node/33">316 STEEL CO., LTD.</a></li>
</ol></div>
"""

DETAIL_ONE = """
Company Name: 21C HI-TECH CO., LTD.
Contact: Kim
Website: example-one.com
Area: Busan
"""

DETAIL_TWO = """
Company Name: 316 STEEL CO., LTD.
Contact: Lee
Website: example-two.com
Area: Busan
"""


class JobRunnerTests(unittest.TestCase):
    def test_run_job_saves_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.sqlite3"
            init_db(db_path)
            save_areas(
                db_path,
                [AreaTerm(term_id=2, name="Busan", url="https://kor.bizdirlib.com/taxonomy/term/2")],
            )
            job_id = create_job(db_path, area_ids=[2], page_limit=1, company_limit=10, workers=2)

            payloads = {
                "https://kor.bizdirlib.com/taxonomy/term/2": TERM_HTML,
                "https://kor.bizdirlib.com/node/14": DETAIL_ONE,
                "https://kor.bizdirlib.com/node/33": DETAIL_TWO,
            }

            def fake_fetch(url: str) -> FetchResult:
                return FetchResult(status_code=200, text=payloads[url])

            run_job(
                db_path,
                job_id,
                area_ids=[2],
                settings=AppSettings(
                    db_path=db_path,
                    origin_base_url="https://test.databasesets.com",
                    origin_host_header="kor.bizdirlib.com",
                    page_limit=1,
                    company_limit=10,
                    workers=2,
                ),
                fetch_document=fake_fetch,
            )

            job = get_job(db_path, job_id)
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.discovered_count, 2)
            self.assertEqual(job.saved_count, 2)
            self.assertEqual(len(list_job_rows(db_path, job_id)), 2)


if __name__ == "__main__":
    unittest.main()
