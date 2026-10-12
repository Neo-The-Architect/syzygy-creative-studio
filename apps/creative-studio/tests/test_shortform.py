"""No-network validations for the short-form pilot preflight."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shortform import preflight_pilot, preflight_shortform  # noqa: E402


def fixture(lane="PARENT", variation="A"):
    labels = {
        "PARENT": "Efficient Labs parent brand",
        "FOUNDER": "Founder personal brand (not Efficient Labs corporate social feed)",
        "STUDIO": "Separate Website Studio brand — DRAFT identity, not parent Efficient Labs feed",
    }
    return {
        "creative_id": f"EL-P01-{lane}-{variation}", "lane": labels[lane],
        "variation": variation, "hook_style": "contradiction", "first_frame_hook": f"VIEWER HOOK {variation}",
        "common_script": f"A verified source-bound body for lane {lane}.",
        "cta": "Follow for documented examples." if lane != "STUDIO" else "Request review — DRAFT",
        "objective": "Inform", "format": "Motion graphics", "state": "SCRIPT_DRAFT",
        "render_status": "SCRIPT_DRAFT", "publish_status": "BLOCKED_PENDING_REVIEW",
        "media_generation_jobs": [], "published_urls": [], "production_expenses_usd": 0,
        "approved_utm_destination": "NOT_SET", "source_references": ["source:A"],
        "original_art_assets_needed": ["Original graphics"], "hard_blockers": ["Owner review"],
    }


class ShortformPreflightTests(unittest.TestCase):
    def test_single_is_not_approved_or_published(self):
        output = preflight_shortform(fixture())
        self.assertEqual(output["creative_id"], "EL-P01-PARENT-A")
        self.assertEqual(output["status"], "DRAFT_NEEDS_REVIEW")
        self.assertEqual(output["render_intent"]["aspect_ratio"], "9:16")
        self.assertEqual(output["external_effects"], "NOT_ATTEMPTED")
        self.assertEqual(output["review_gates"]["operator_approval"], "NOT_GRANTED")
        self.assertEqual(output["publishing"], "DISABLED")

    def test_lanes_cannot_leak(self):
        value = fixture(lane="STUDIO")
        value["lane"] = "Efficient Labs parent brand"
        with self.assertRaisesRegex(ValueError, "lane identity mismatch"):
            preflight_shortform(value)

    def test_unverified_published_and_paid_state_rejected(self):
        for k, value in [("published_urls", ["https://example.test"]), ("media_generation_jobs", ["fake"]),
                         ("production_expenses_usd", 1), ("publish_status", "PUBLISHED")]:
            obj = fixture()
            obj[k] = value
            with self.subTest(k=k), self.assertRaises(ValueError):
                preflight_shortform(obj)

    def test_external_url_requires_https_without_credentials(self):
        for url in ["http://example.com", "https://user:password@example.com", "ftp://example.com"]:
            obj = fixture("STUDIO")
            obj["approved_utm_destination"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                preflight_shortform(obj)
        obj = fixture("STUDIO")
        obj["approved_utm_destination"] = "https://example.com/form"
        out = preflight_shortform(obj)
        self.assertEqual(out["destination"]["state"], "CANDIDATE_ONLY")
        self.assertEqual(out["review_gates"]["live_offer_and_attribution"], "BLOCKED")

    def test_batch_nine_variants_and_shared_script(self):
        items = [fixture(lane, variant) for lane in ("PARENT", "FOUNDER", "STUDIO") for variant in ("A", "B", "C")]
        out = preflight_pilot({"creatives": items})
        self.assertTrue(out["complete_three_lane_pilot"])
        self.assertEqual(out["creative_count"], 9)
        self.assertEqual(out["rendering"], "DISABLED_PENDING_INTEGRATION_AND_APPROVAL")
        self.assertEqual(out["publishing"], "DISABLED")

    def test_batch_body_drift_fails(self):
        items = [fixture("PARENT", v) for v in ("A", "B", "C")]
        items[1]["common_script"] = "Different body changes the experiment."
        with self.assertRaisesRegex(ValueError, "changed the common body"):
            preflight_pilot({"creatives": items})

    def test_duplicate_creatives_fail(self):
        items = [fixture(), fixture()]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            preflight_pilot({"creatives": items})



if __name__ == "__main__":
    unittest.main()
