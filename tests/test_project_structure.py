import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_project  # noqa: E402
import psa_common as c  # noqa: E402


class StructureTests(unittest.TestCase):
    def test_repository_shape(self):
        report = c.Report("repo")
        validate_project.validate_repo(report)
        self.assertEqual(report.errors, [], "\n".join(report.errors))

    def test_demo_state(self):
        report = validate_project.validate_project(ROOT / "demo" / "megafon-plus")
        self.assertEqual(report.errors, [], "\n".join(report.errors))


if __name__ == "__main__":
    unittest.main()
