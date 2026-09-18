from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ingest import parse_listing_html  # noqa: E402
from pipeline import build_claims, deterministic_copy, run_pipeline, validate_copy, validate_property  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
