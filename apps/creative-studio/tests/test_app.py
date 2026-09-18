import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402


class CreativeStudioMvpTests(unittest.TestCase):
    def test_create_run_reaches_review_without_external_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                result = app.create_run(
                    {
                        "prompt": "Create a cinematic property showcase.",
                        "output_targets": ["video", "website"],
                    },
                    run_id="run-test-001",
                    run_checks=True,
                )
                self.assertEqual(result["status"], "NEEDS_REVIEW")
                self.assertEqual(result["external_effects"], "NOT_ATTEMPTED")
                self.assertTrue((app.RUNS_ROOT / "run-test-001" / "artifacts" / "campaign.json").exists())
                self.assertTrue((app.RUNS_ROOT / "run-test-001" / "evidence.json").exists())
                composition = (app.RUNS_ROOT / "run-test-001" / "hyperframes" / "index.html").read_text(encoding="utf-8")
                self.assertIn("100 Example", composition)
                self.assertIn("$625,000", composition)
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_approval_is_explicit_and_state_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                app.create_run({"prompt": "Test approval"}, run_id="run-test-002")
                approved = app.approve_run("run-test-002")
                self.assertEqual(approved["status"], "APPROVED")
                with self.assertRaises(ValueError):
                    app.approve_run("run-test-002")
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_invalid_prompt_fails_closed(self):
        with self.assertRaises(ValueError):
            app.create_run({"prompt": ""}, run_id="run-test-003", run_checks=False)

    def test_custom_source_is_bound_into_plan_and_composition(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                result = app.create_run(
                    {
                        "prompt": "Create a modern listing film.",
                        "source": {
                            "source_url": "local://approved-custom",
                            "address": "42 Signal Street, Testville",
                            "price": "$710,000",
                            "beds": 4,
                            "baths": 3,
                            "area_sqft": 2400,
                            "features": ["studio", "garden"],
                            "description": "Synthetic custom fixture.",
                        },
                    },
                    run_id="run-test-004",
                    run_checks=True,
                )
                self.assertEqual(result["status"], "NEEDS_REVIEW")
                plan = json.loads((app.RUNS_ROOT / "run-test-004" / "plan.json").read_text(encoding="utf-8"))
                self.assertEqual(plan["source_facts"]["address"], "42 Signal Street, Testville")
                composition = (app.RUNS_ROOT / "run-test-004" / "hyperframes" / "index.html").read_text(encoding="utf-8")
                self.assertIn("42 Signal Street", composition)
                self.assertIn("$710,000", composition)
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_invalid_source_fails_closed(self):
        with self.assertRaises(ValueError):
            app.create_run(
                {"prompt": "Reject incomplete source", "source": {"address": "missing facts"}},
                run_id="run-test-005",
                run_checks=False,
            )


if __name__ == "__main__":
    unittest.main()
