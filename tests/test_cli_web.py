import unittest
from pathlib import Path

from bizdir_crawler.cli import build_parser


class CliWebTests(unittest.TestCase):
    def test_httpx_is_default_transport(self):
        args = build_parser().parse_args(["collect-urls", "--output", "tmp/out.txt"])
        self.assertEqual(args.transport, "httpx")

    def test_serve_command_parses_web_args(self):
        args = build_parser().parse_args(
            [
                "serve",
                "--db-path",
                "tmp/app.sqlite3",
                "--origin-base-url",
                "https://test.databasesets.com",
                "--origin-host-header",
                "kor.bizdirlib.com",
            ]
        )
        self.assertEqual(args.command, "serve")
        self.assertEqual(args.db_path, Path("tmp/app.sqlite3"))
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8000)


if __name__ == "__main__":
    unittest.main()
