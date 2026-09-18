import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402


class CreativeStudioMvpTests(unittest.TestCase):
    def test_openrouter_preflight_fails_before_partial_run_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            old_key = os.environ.pop("OPENROUTER_API_KEY", None)
            old_model = os.environ.pop("OPENROUTER_MODEL", None)
            app.RUNS_ROOT = Path(temp) / "runs"
            try:
                with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY.*OPENROUTER_MODEL"):
                    app.create_run(
                        {"prompt": "Provider preflight", "provider": "openrouter"},
                        run_id="run-openrouter-preflight",
                        run_checks=False,
                    )
                self.assertFalse((app.RUNS_ROOT / "run-openrouter-preflight").exists())
            finally:
                app.RUNS_ROOT = old_runs
                if old_key is not None:
                    os.environ["OPENROUTER_API_KEY"] = old_key
                if old_model is not None:
                    os.environ["OPENROUTER_MODEL"] = old_model

    def test_head_routes_return_headers_without_body_and_preserve_containment(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            run_dir = app.RUNS_ROOT / "head-test"
            artifact = run_dir / "artifacts" / "sample.txt"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("head-safe\n", encoding="utf-8")
            app.write_json(run_dir / "run.json", {"run_id": "head-test", "status": "NEEDS_REVIEW"})
            server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.StudioHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                for path, expected_type, expected_length in [
                    ("/api/health", "application/json; charset=utf-8", None),
                    ("/api/runs/head-test", "application/json; charset=utf-8", None),
                    ("/api/runs/head-test/artifacts/artifacts/sample.txt", "text/plain", artifact.stat().st_size),
                ]:
                    request = urllib.request.Request(base + path, method="HEAD")
                    with urllib.request.urlopen(request, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.read(), b"")
                        self.assertEqual(response.headers["Content-Type"], expected_type)
                        if expected_length is not None:
                            self.assertEqual(int(response.headers["Content-Length"]), expected_length)

                with self.assertRaises(urllib.error.HTTPError) as missing:
                    urllib.request.urlopen(
                        urllib.request.Request(base + "/api/runs/head-test/artifacts/artifacts/missing.txt", method="HEAD"),
                        timeout=5,
                    )
                self.assertEqual(missing.exception.code, 404)

                with self.assertRaises(urllib.error.HTTPError) as traversal:
                    urllib.request.urlopen(
                        urllib.request.Request(base + "/api/runs/head-test/artifacts/%2e%2e/%2e%2e/%2e%2e/run.json", method="HEAD"),
                        timeout=5,
                    )
                self.assertEqual(traversal.exception.code, 404)

                with self.assertRaises(urllib.error.HTTPError) as internal_path_confusion:
                    urllib.request.urlopen(
                        urllib.request.Request(base + "/api/runs/head-test/artifacts/%2e%2e/run.json", method="HEAD"),
                        timeout=5,
                    )
                self.assertEqual(internal_path_confusion.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                app.RUNS_ROOT = old_runs

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

    def test_run_id_and_binding_boundaries_fail_closed(self):
        self.assertTrue(app.is_safe_run_id("run-20260918T000000Z-abcd1234"))
        self.assertFalse(app.is_safe_run_id("../outside"))
        self.assertFalse(app.is_safe_run_id("run/child"))
        self.assertTrue(app.is_loopback_host("127.0.0.1"))
        self.assertTrue(app.is_loopback_host("localhost"))
        self.assertFalse(app.is_loopback_host("0.0.0.0"))
        with self.assertRaisesRegex(ValueError, "invalid run id"):
            app.create_run({"prompt": "Reject path run id"}, run_id="../outside", run_checks=False)

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
                        "output_targets": ["video", "website", "presentation", "app", "content"],
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
                content = json.loads((app.RUNS_ROOT / "run-test-004" / "artifacts" / "content" / "content-pack.json").read_text(encoding="utf-8"))
                self.assertEqual(content["status"], "DRAFT_NEEDS_REVIEW")
                self.assertEqual(content["publishing"], "DISABLED")
                self.assertIn("42 Signal Street", content["platform_drafts"]["instagram"]["text"])
                self.assertEqual(
                    result["artifacts"],
                    {
                        "website": "artifacts/website/index.html",
                        "presentation": "artifacts/presentation/index.html",
                        "app": "artifacts/app/index.html",
                        "content_json": "artifacts/content/content-pack.json",
                        "content_markdown": "artifacts/content/content-pack.md",
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
                exported = app.export_run("run-test-007")
                self.assertEqual(exported["status"], "EXPORTED")
                bundle_path = run_dir / "artifacts" / "export" / "creative-run-run-test-007.zip"
                self.assertTrue(bundle_path.exists())
                with zipfile.ZipFile(bundle_path) as bundle:
                    self.assertIn("export-manifest.json", bundle.namelist())
                    self.assertIn("inputs/source.json", bundle.namelist())
                    self.assertIn("render-receipt.json", bundle.namelist())
            finally:
                app.RUNS_ROOT = old_runs
                os.environ.pop("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES", None)

    def test_export_requires_rendered_state(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / "runs"
            os.environ["SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES"] = "1"
            try:
                app.create_run({"prompt": "Export gate"}, run_id="run-test-export-gate")
                with self.assertRaisesRegex(ValueError, "requires RENDERED"):
                    app.export_run("run-test-export-gate")
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
