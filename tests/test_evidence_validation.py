import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import decision_trace  # noqa: E402
import validate_sources  # noqa: E402


class EvidenceTests(unittest.TestCase):
    def test_demo_sources_pass(self):
        report = validate_sources.validate(ROOT / "demo" / "megafon-plus")
        self.assertEqual(report.errors, [], "\n".join(report.errors))

    def test_price_change_touches_decision(self):
        project = ROOT / "demo" / "megafon-plus"
        ledger = decision_trace.c.load_ledger(project)
        state = decision_trace.c.read_json(project / "state" / "project-state.json")
        text = decision_trace.render_impact(project, ledger, state, {"E002"})
        self.assertIn("DEC-001", text)
        self.assertIn("E030", text)


if __name__ == "__main__":
    unittest.main()
