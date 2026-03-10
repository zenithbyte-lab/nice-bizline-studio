import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class PackagingTests(unittest.TestCase):
    def test_pyproject_declares_python_multipart_dependency(self):
        with (ROOT / "pyproject.toml").open("rb") as fh:
            payload = tomllib.load(fh)

        dependencies = payload["project"]["dependencies"]
        self.assertTrue(any(dep.startswith("python-multipart") for dep in dependencies))

    def test_windows_workflow_collects_multipart_modules(self):
        workflow = (ROOT / ".github" / "workflows" / "build-windows-exe.yml").read_text(encoding="utf-8")

        self.assertIn("--collect-submodules multipart", workflow)
        self.assertIn("--collect-submodules python_multipart", workflow)


if __name__ == "__main__":
    unittest.main()
