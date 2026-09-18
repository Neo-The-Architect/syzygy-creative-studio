import json
import os
import sys
import tempfile
import unittest
from unittest import mock
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
                website = (app.RUNS_ROOT / "run-test-001" / "artifacts" / "website" / "index.html").read_text(encoding="utf-8")
                self.assertIn("100 Example Avenue", website)
                self.assertIn("open kitchen", website)
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

    def test_unsupported_output_target_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported output target"):
            app.create_run({"prompt": "Reject unknown adapter", "output_targets": ["teleporter"]}, run_id="run-test-003b", run_checks=False)

    def test_idempotency_key_returns_original_run(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                payload = {"prompt": "Retry-safe run", "idempotency_key": "request-001"}
                first = app.create_run(payload, run_id="run-test-idempotent-001")
                second = app.create_run(payload, run_id="run-test-idempotent-002")
                self.assertEqual(first["run_id"], second["run_id"])
                self.assertEqual(len(list((app.RUNS_ROOT).glob("*/run.json"))), 1)
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_idempotency_key_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                app.create_run({"prompt": "Original", "idempotency_key": "request-002"}, run_id="run-test-idempotent-003")
                with self.assertRaisesRegex(ValueError, "already bound"):
                    app.create_run({"prompt": "Changed", "idempotency_key": "request-002"}, run_id="run-test-idempotent-004")
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_custom_source_is_bound_into_plan_and_composition(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                result = app.create_run(
                    {
                        "prompt": "Create a modern listing film.",
                        "output_targets": ["video", "website", "presentation", "app"],
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
                presentation = (app.RUNS_ROOT / "run-test-004" / "artifacts" / "presentation" / "index.html").read_text(encoding="utf-8")
                self.assertIn("42 Signal Street", presentation)
                prototype = (app.RUNS_ROOT / "run-test-004" / "artifacts" / "app" / "index.html").read_text(encoding="utf-8")
                self.assertIn("42 Signal Street", prototype)
                self.assertEqual(
                    result["artifacts"],
                    {
                        "website": "artifacts/website/index.html",
                        "presentation": "artifacts/presentation/index.html",
                        "app": "artifacts/app/index.html",
                    },
                )
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

    def test_render_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                app.create_run({"prompt": "Render gate"}, run_id="run-test-006")
                with self.assertRaisesRegex(ValueError, "requires APPROVED"):
                    app.render_run("run-test-006")
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_render_binds_receipt_to_approved_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                app.create_run({"prompt": "Render receipt"}, run_id="run-test-007")
                app.approve_run("run-test-007")
                run_dir = app.RUNS_ROOT / "run-test-007"
                app.write_json(
                    run_dir / "hyperframes-check.json",
                    {"status": "PASS", "snapshot": {"status": "PASS"}},
                )

                def fake_render(project, output, quality):
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"synthetic-mp4")
                    return {
                        "command": ["fake-hyperframes", "render"],
                        "quality": quality,
                        "stdout": "fake render",
                        "stderr": "",
                        "ffprobe": {
                            "format": {"duration": "18.0"},
                            "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
                        },
                    }

                with mock.patch.object(app, "render_hyperframes", side_effect=fake_render):
                    result = app.render_run("run-test-007")
                self.assertEqual(result["status"], "RENDERED")
                receipt = app.read_json(run_dir / "render-receipt.json")
                self.assertEqual(receipt["status"], "PASS")
                self.assertEqual(receipt["size_bytes"], len(b"synthetic-mp4"))
                self.assertTrue(receipt["sha256"])
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_render_rejects_stale_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                app.create_run({"prompt": "Stale approval"}, run_id="run-test-008")
                app.approve_run("run-test-008")
                source_path = app.RUNS_ROOT / "run-test-008" / "inputs" / "source.json"
                source = app.read_json(source_path)
                source["description"] = "changed after approval"
                app.write_json(source_path, source)
                with self.assertRaisesRegex(ValueError, "STALE_APPROVAL"):
                    app.render_run("run-test-008")
                self.assertEqual(app.read_json(app.RUNS_ROOT / "run-test-008" / "run.json")["status"], "BLOCKED")
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)


if __name__ == "__main__":
    unittest.main()
