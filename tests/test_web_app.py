import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from bizdir_crawler.db import init_db, save_areas
from bizdir_crawler.models import AreaTerm
from bizdir_crawler.web import AppSettings, create_app


class _InlineRunner:
    def __init__(self) -> None:
        self.started = []

    def start(self, job_id: str, area_ids: list[int], settings: AppSettings, source: str = "bizdir") -> None:
        self.started.append((job_id, area_ids, settings.page_limit, settings.company_limit, settings.workers, source))


class WebAppTests(unittest.TestCase):
    def test_index_and_job_creation_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.sqlite3"
            init_db(db_path)
            save_areas(
                db_path,
                [
                    AreaTerm(term_id=2, name="Busan", url="https://kor.bizdirlib.com/taxonomy/term/2"),
                    AreaTerm(term_id=57, name="Bundang-Gu", url="https://kor.bizdirlib.com/taxonomy/term/57"),
                ],
            )

            runner = _InlineRunner()
            app = create_app(
                AppSettings(
                    db_path=db_path,
                    origin_base_url="https://test.databasesets.com",
                    origin_host_header="kor.bizdirlib.com",
                    page_limit=2,
                    company_limit=10,
                    workers=4,
                ),
                runner=runner,
            )
            client = TestClient(app)

            home = client.get("/")
            self.assertEqual(home.status_code, 200)
            self.assertIn("Busan", home.text)
            self.assertIn("开始抓取", home.text)
            self.assertNotIn('name="page_limit"', home.text)
            self.assertIn("自动翻页", home.text)

            response = client.post(
                "/jobs",
                data={"area_ids": ["2", "57"], "company_limit": "20", "workers": "6", "source": "bizdir"},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 303)
            self.assertIn("/?job_id=", response.headers["location"])
            self.assertEqual(len(runner.started), 1)
            self.assertEqual(runner.started[0][2], 0)

            job_id = response.headers["location"].split("job_id=")[-1]
            dashboard = client.get(response.headers["location"])
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("日志", dashboard.text)

            api_payload = client.get(f"/api/jobs/{job_id}").json()
            self.assertEqual(api_payload["job"]["status"], "queued")
            self.assertTrue(api_payload["events"])


if __name__ == "__main__":
    unittest.main()
