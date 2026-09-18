from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ingest import parse_listing_html  # noqa: E402
from pipeline import PipelineError, build_claims, deterministic_copy, openrouter_copy, openrouter_creative_plan, run_pipeline, validate_copy, validate_property  # noqa: E402


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run([sys.executable, str(SRC / "create_fixture.py")], check=True)

    def test_jsonld_ingestion_is_conservative(self) -> None:
        html = '''<html><head><meta property="og:image" content="https://example.test/hero.jpg"><script type="application/ld+json">{"@type":"SingleFamilyResidence","address":{"streetAddress":"1 Main St","addressLocality":"Testville","addressRegion":"TS"},"numberOfBedrooms":2,"numberOfBathroomsTotal":1,"floorSize":{"value":1000},"offers":{"price":"$300000"},"image":["https://example.test/a.jpg"]}</script></head></html>'''
        record = parse_listing_html(html, "https://example.test/listing")
        self.assertEqual(record["address"], "1 Main St, Testville, TS")
        self.assertEqual(record["beds"], 2)
        self.assertEqual(record["image_urls"], ["https://example.test/a.jpg"])

    def test_unsupported_copy_is_rejected(self) -> None:
        record = json.loads((ROOT / "fixtures" / "property.json").read_text(encoding="utf-8"))
        claims = build_claims(record)
        copy = deterministic_copy(record, claims)
        copy["description"] += " Located in the safest neighborhood with the best schools."
        with self.assertRaises(RuntimeError):
            validate_copy(copy, claims)

    def test_end_to_end_offline_outputs(self) -> None:
        record_path = ROOT / "fixtures" / "property.json"
        images = ROOT / "fixtures" / "images"
        with tempfile.TemporaryDirectory() as temp:
            result = run_pipeline(str(record_path), str(images), temp, "deterministic")
            self.assertEqual(result["audit"]["status"], "PASS")
            self.assertEqual(result["audit"]["external_publication"], "NOT_ATTEMPTED")
            self.assertTrue(Path(result["campaign"]["assets"]["reel"]).exists())
            self.assertTrue(Path(result["campaign"]["assets"]["brochure"]).exists())
            self.assertGreater(Path(result["campaign"]["assets"]["reel"]).stat().st_size, 1000)
            self.assertGreater(Path(result["campaign"]["assets"]["brochure"]).stat().st_size, 1000)

    def test_openrouter_requires_explicit_configuration(self) -> None:
        record = json.loads((ROOT / "fixtures" / "property.json").read_text(encoding="utf-8"))
        claims = build_claims(record)
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "OPENROUTER_MODEL": ""}):
            with self.assertRaisesRegex(PipelineError, "OPENROUTER_API_KEY and OPENROUTER_MODEL"):
                openrouter_copy(record, claims)

    def test_openrouter_accepts_strict_claim_bound_output(self) -> None:
        record = json.loads((ROOT / "fixtures" / "property.json").read_text(encoding="utf-8"))
        claims = build_claims(record)
        generated = deterministic_copy(record, claims)
        generated.pop("provider")
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "id": "req_test_123",
                "choices": [{"message": {"content": json.dumps(generated)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        ).encode("utf-8")
        response.headers = {"x-ratelimit-remaining": "9"}
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/model"}):
            with mock.patch("pipeline.urllib.request.urlopen", return_value=response):
                result = openrouter_copy(record, claims)
        self.assertEqual(result["provider"], "openrouter:test/model")
        self.assertEqual(result["provider_metadata"]["request_id"], "req_test_123")
        self.assertEqual(set(result["claim_ids"]), {claim["claim_id"] for claim in claims})

    def test_openrouter_rejects_schema_drift_without_fallback(self) -> None:
        record = json.loads((ROOT / "fixtures" / "property.json").read_text(encoding="utf-8"))
        claims = build_claims(record)
        generated = deterministic_copy(record, claims)
        generated.pop("provider")
        generated["unexpected"] = "must be rejected"
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": json.dumps(generated)}}]}
        ).encode("utf-8")
        response.headers = {}
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/model"}):
            with mock.patch("pipeline.urllib.request.urlopen", return_value=response):
                with self.assertRaisesRegex(PipelineError, "schema keys mismatch"):
                    openrouter_copy(record, claims)

    def test_openrouter_creative_plan_accepts_claim_bound_beats(self) -> None:
        record = json.loads((ROOT / "fixtures" / "property.json").read_text(encoding="utf-8"))
        claims = build_claims(record)
        claim_ids = [claim["claim_id"] for claim in claims]
        generated = {
            "creative_direction": "A calm, editorial arrival that lets the supported details lead.",
            "beats": [
                {
                    "id": "arrival",
                    "purpose": "establish the property and its verified proposition",
                    "duration_seconds": 8,
                    "claim_ids": claim_ids,
                }
            ],
            "claim_ids": claim_ids,
        }
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "id": "plan_test_123",
                "choices": [{"message": {"content": json.dumps(generated)}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 30},
            }
        ).encode("utf-8")
        response.headers = {"x-ratelimit-remaining": "8"}
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/model"}):
            with mock.patch("pipeline.urllib.request.urlopen", return_value=response):
                result = openrouter_creative_plan(
                    "Create a cinematic property showcase.",
                    record,
                    claims,
                    ["video", "website"],
                )
        self.assertEqual(result["creative_direction"].startswith("A calm"), True)
        self.assertEqual(result["provider_metadata"]["request_id"], "plan_test_123")
        self.assertEqual(set(result["claim_ids"]), set(claim_ids))

    def test_openrouter_creative_plan_rejects_unbound_claims(self) -> None:
        record = json.loads((ROOT / "fixtures" / "property.json").read_text(encoding="utf-8"))
        claims = build_claims(record)
        claim_ids = [claim["claim_id"] for claim in claims]
        generated = {
            "creative_direction": "Unsupported direction",
            "beats": [
                {
                    "id": "arrival",
                    "purpose": "make an unsupported claim",
                    "duration_seconds": 8,
                    "claim_ids": ["claim-unknown"],
                }
            ],
            "claim_ids": claim_ids,
        }
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": json.dumps(generated)}}]}
        ).encode("utf-8")
        response.headers = {}
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/model"}):
            with mock.patch("pipeline.urllib.request.urlopen", return_value=response):
                with self.assertRaisesRegex(PipelineError, "unknown or duplicate claims"):
                    openrouter_creative_plan("Reject unsupported plan", record, claims, ["video"])


if __name__ == "__main__":
    unittest.main()
