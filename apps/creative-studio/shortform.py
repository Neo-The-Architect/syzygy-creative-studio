"""Read-only, evidence-first preflight for short-form creative candidates.

The existing Syzygy run engine retains sole authority for approval, rendering,
export, and release. This module makes no external requests, files, or grants.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "quark.shortform-preflight@0.1.0"
CREATIVE_ID = re.compile(r"^EL-P\d{2}-(PARENT|FOUNDER|STUDIO)-([ABC])$")
LANES = {
    "PARENT": "Efficient Labs parent brand",
    "FOUNDER": "Founder personal brand (not Efficient Labs corporate social feed)",
    "STUDIO": "Separate Website Studio brand — DRAFT identity, not parent Efficient Labs feed",
}
UNSET_DESTINATIONS = {"", "NOT_SET", "TBD", "PENDING", "NONE"}
MAX_VARIANTS = 24


def _text(value: Any, field: str, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be nonempty text of at most {limit} characters")
    if "\x00" in value:
        raise ValueError(f"{field} contains a forbidden NUL")
    return value.strip()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _destination(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or value.strip().upper() in UNSET_DESTINATIONS:
        return {"state": "MISSING", "reason": "No founder-approved lead destination is recorded"}
    if len(value) > 2048:
        raise ValueError("approved_utm_destination too long")
    split = urlsplit(value.strip())
    if split.scheme != "https" or not split.hostname or split.username or split.password:
        raise ValueError("approved_utm_destination must be a credential-free HTTPS URL")
    return {"state": "CANDIDATE_ONLY", "reason": "URL is well formed but ownership, consent and live tracking are not independently verified"}


def _strings(value: Any, field: str, max_items: int = 32) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= max_items:
        raise ValueError(f"{field} must be a non-empty bounded list")
    return [_text(entry, field + "[]", 1024) for entry in value]


def preflight_shortform(candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate one source-bound creative and return a review candidate, never authorization."""
    if not isinstance(candidate, dict):
        raise ValueError("creative must be a JSON object")
    ident = _text(candidate.get("creative_id"), "creative_id", 80)
    match = CREATIVE_ID.fullmatch(ident)
    if match is None:
        raise ValueError("creative_id must match EL-PNN-{PARENT,FOUNDER,STUDIO}-{A,B,C}")
    lane_id, variant = match.groups()
    if candidate.get("variation") != variant:
        raise ValueError("variation does not match creative_id")
    if candidate.get("lane") != LANES[lane_id]:
        raise ValueError("lane identity mismatch; parent, founder and studio cannot be interchanged")
    if candidate.get("render_status") not in {"SCRIPT_DRAFT", "NOT_STARTED"}:
        raise ValueError("creative must be an unrendered script candidate; do not import claimed renders")
    if candidate.get("publish_status") != "BLOCKED_PENDING_REVIEW":
        raise ValueError("publish_status must remain BLOCKED_PENDING_REVIEW")
    if candidate.get("state") != "SCRIPT_DRAFT":
        raise ValueError("candidate state must be SCRIPT_DRAFT")
    if candidate.get("media_generation_jobs") != [] or candidate.get("published_urls") != []:
        raise ValueError("published/media jobs cannot be imported as unverified empty-source pilot assets")
    if candidate.get("production_expenses_usd") != 0:
        raise ValueError("pilot must remain zero paid provider spend")

    hook = _text(candidate.get("first_frame_hook"), "first_frame_hook", 180)
    script = _text(candidate.get("common_script"), "common_script", 6000)
    cta = _text(candidate.get("cta"), "cta", 500)
    _text(candidate.get("hook_style"), "hook_style", 80)
    _text(candidate.get("objective"), "objective", 240)
    _text(candidate.get("format"), "format", 200)
    rights = _strings(candidate.get("original_art_assets_needed"), "original_art_assets_needed")
    blockers = _strings(candidate.get("hard_blockers"), "hard_blockers")
    refs = _strings(candidate.get("source_references"), "source_references")
    destination = _destination(candidate.get("approved_utm_destination"))

    # A user-controlled 'approved' field is not evidence of a real review receipt.
    gates = {
        "source_truth": "REVIEW_REQUIRED",
        "media_and_likeness_rights": "REVIEW_REQUIRED",
        "brand_identity": "REVIEW_REQUIRED",
        "script_and_claims": "REVIEW_REQUIRED",
        "9x16_composition_and_caption_safe_area": "NOT_TESTED",
        "live_offer_and_attribution": "BLOCKED" if lane_id == "STUDIO" else "NOT_VERIFIED",
        "cost_preflight": "NOT_TESTED",
        "operator_approval": "NOT_GRANTED",
        "publication": "DISABLED",
    }
    if destination["state"] == "MISSING" and lane_id == "STUDIO":
        gates["live_offer_and_attribution"] = "BLOCKED"

    return {
        "schema_version": SCHEMA_VERSION,
        "creative_id": ident,
        "lane": lane_id,
        "variation": variant,
        "hook_style": candidate["hook_style"],
        "hook": hook,
        "common_script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "body": script,
        "cta": cta,
        "destination": destination,
        "source_references": refs,
        "required_assets": rights,
        "reported_blockers": blockers,
        "render_intent": {"aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 24, "duration_seconds": None, "audio": "UNSPECIFIED"},
        "review_gates": gates,
        "source_sha256": _hash(candidate),
        "status": "DRAFT_NEEDS_REVIEW",
        "rendering": "DISABLED_PENDING_INTEGRATION_AND_APPROVAL",
        "publishing": "DISABLED",
        "external_effects": "NOT_ATTEMPTED",
    }


def preflight_pilot(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single candidate or a bounded batch without writing run state."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "creatives" not in payload:
        return preflight_shortform(payload.get("creative", payload))
    items = payload["creatives"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_VARIANTS:
        raise ValueError(f"creatives must contain 1 to {MAX_VARIANTS} candidates")
    previews = [preflight_shortform(item) for item in items]
    ids = [item["creative_id"] for item in previews]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate creative_id in batch")
    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in previews:
        lanes[item["lane"]].append(item)
    for lane, group in lanes.items():
        if len({item["common_script_sha256"] for item in group}) != 1:
            raise ValueError(f"{lane} variants changed the common body; hook test would be invalid")
        if len({item["cta"] for item in group}) != 1:
            raise ValueError(f"{lane} variants changed CTA; hook test would be invalid")
        if len({item["variation"] for item in group}) != len(group):
            raise ValueError(f"{lane} variant repeats")
    full_pilot = len(previews) == 9 and set(lanes) == set(LANES) and all(
        {item["variation"] for item in group} == {"A", "B", "C"} for group in lanes.values()
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "DRAFT_NEEDS_REVIEW",
        "complete_three_lane_pilot": full_pilot,
        "creative_count": len(previews),
        "lanes": {key: {"count": len(group), "variants": sorted(item["variation"] for item in group)} for key, group in lanes.items()},
        "creatives": previews,
        "batch_sha256": _hash([item["source_sha256"] for item in previews]),
        "rendering": "DISABLED_PENDING_INTEGRATION_AND_APPROVAL",
        "publishing": "DISABLED",
        "external_effects": "NOT_ATTEMPTED",
    }
