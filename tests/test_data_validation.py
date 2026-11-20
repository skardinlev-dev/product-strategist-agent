import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scenario  # noqa: E402
import validate_data  # noqa: E402


class DataTests(unittest.TestCase):
    def test_demo_table_passes(self):
        report = validate_data.validate(ROOT / "demo" / "megafon-plus" / "data" / "synthetic_metrics.csv")
        self.assertEqual(report.errors, [])

    def test_broken_balance_fails(self):
        text = (ROOT / "demo" / "megafon-plus" / "data" / "synthetic_metrics.csv").read_text(encoding="utf-8")
        text = text.replace("12000,1500,1100,12400", "12000,1500,1100,1", 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic_metrics.csv"
            path.write_text(text, encoding="utf-8")
            (Path(folder) / "README.md").write_text("учебные\n", encoding="utf-8")
            report = validate_data.validate(path)
        self.assertTrue(report.errors)

    def test_teaching_contribution(self):
        rows = scenario.load(ROOT / "demo" / "megafon-plus")
        self.assertEqual(scenario.contribution(rows), 1312928)
        pessimistic = scenario.contribution(rows, 0.85)
        self.assertLess(pessimistic, 0)


if __name__ == "__main__":
    unittest.main()
