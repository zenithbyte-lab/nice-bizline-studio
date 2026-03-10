import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bizdir_crawler.windows_launcher import build_runtime_settings, parse_listening_pids, run_windows_app


NETSTAT_SAMPLE = """
  TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       4120
  TCP    127.0.0.1:8000         127.0.0.1:51234        ESTABLISHED     4120
  TCP    [::]:8000              [::]:0                 LISTENING       9988
  TCP    0.0.0.0:9000           0.0.0.0:0              LISTENING       7777
"""


class WindowsLauncherTests(unittest.TestCase):
    def test_parse_listening_pids_returns_unique_listening_pids_for_port(self):
        self.assertEqual(parse_listening_pids(NETSTAT_SAMPLE, 8000), [4120, 9988])

    def test_build_runtime_settings_uses_packaged_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = build_runtime_settings(Path(tmp), port=8877)

        self.assertEqual(settings.db_path, Path(tmp) / "data" / "kor_bizdir.sqlite3")
        self.assertEqual(settings.origin_base_url, "https://test.databasesets.com")
        self.assertEqual(settings.origin_host_header, "kor.bizdirlib.com")
        self.assertEqual(settings.page_limit, 0)
        self.assertEqual(settings.company_limit, 50)
        self.assertEqual(settings.workers, 8)

    def test_run_windows_app_disables_uvicorn_default_log_config(self):
        class _FakeThread:
            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("bizdir_crawler.windows_launcher.app_base_dir", return_value=Path(tmp)),
                patch("bizdir_crawler.windows_launcher.cleanup_port"),
                patch("bizdir_crawler.windows_launcher.create_app", return_value=object()),
                patch("bizdir_crawler.windows_launcher.threading.Thread", return_value=_FakeThread()),
                patch("bizdir_crawler.windows_launcher.uvicorn.run") as uvicorn_run,
            ):
                result = run_windows_app(port=8123)

        self.assertEqual(result, 0)
        uvicorn_run.assert_called_once()
        _, kwargs = uvicorn_run.call_args
        self.assertIsNone(kwargs["log_config"])
        self.assertFalse(kwargs["access_log"])
        self.assertEqual(kwargs["log_level"], "warning")


if __name__ == "__main__":
    unittest.main()
