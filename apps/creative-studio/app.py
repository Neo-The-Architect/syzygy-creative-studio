"""Syzygy Creative Studio: local-first MVP service.

This is a bounded source-to-preview slice. It deliberately stops at NEEDS_REVIEW
unless an operator explicitly approves a run. No external publication occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
from html import escape
import ipaddress
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
_base_candidates = [ROOT, ROOT.parent, *ROOT.parents]
PROJECT_ROOT = next(
    (
        candidate
        for candidate in _base_candidates
        if (candidate / "packages" / "real-estate-pipeline").exists()
        or (candidate / "ai-real-estate-marketing-pipeline").exists()
    ),
    ROOT.parent,
)
PIPELINE_ROOT = (
    PROJECT_ROOT / "packages" / "real-estate-pipeline"
    if (PROJECT_ROOT / "packages" / "real-estate-pipeline").exists()
    else PROJECT_ROOT / "ai-real-estate-marketing-pipeline"
)
PIPELINE_SRC = PIPELINE_ROOT / "src"
FIXTURE_PROPERTY = PIPELINE_ROOT / "fixtures" / "property.json"
FIXTURE_IMAGES = PIPELINE_ROOT / "fixtures" / "images"
HYPERFRAMES_SHOWCASE = (
    PROJECT_ROOT / "packages" / "hyperframes-showcase"
    if (PROJECT_ROOT / "packages" / "hyperframes-showcase").exists()
    else PROJECT_ROOT / "syzygy-creative-fabric-showcase"
)
DATA_ROOT = ROOT / "data"
RUNS_ROOT = DATA_ROOT / "runs"
WEB_ROOT = ROOT / "web"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
AUTH_TOKEN_ENV = "SYZYGY_CREATIVE_STUDIO_AUTH_TOKEN"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_safe_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.fullmatch(run_id)) and run_id not in {".", ".."}


def require_safe_run_id(run_id: str) -> str:
    if not is_safe_run_id(run_id):
        raise ValueError("invalid run id")
    return run_id


def resolve_artifact_path(run_id: str, relative: str) -> Path | None:
    """Resolve an artifact only inside the run's artifacts subtree."""
    if not is_safe_run_id(run_id):
        return None
    root = (RUNS_ROOT / run_id).resolve()
    artifacts_root = (root / "artifacts").resolve()
    candidate = (root / unquote(relative)).resolve()
    if (
        not root.exists()
        or not artifacts_root.exists()
        or artifacts_root not in candidate.parents
        or not candidate.is_file()
    ):
        return None
    return candidate


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def fixture_property() -> dict[str, Any]:
    return read_json(FIXTURE_PROPERTY)


def validate_source(source: dict[str, Any], pipeline: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError("source must be a JSON object")
    try:
        return pipeline.validate_property(source)
    except Exception as exc:
        raise ValueError(f"invalid source package: {exc}") from exc


def build_creative_plan(
    prompt: str,
    source: dict[str, Any],
    output_targets: list[str],
    provider: str,
    pipeline: Any | None = None,
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    plan = {
        "schema_version": "creative.plan@1.1.0",
        "brief": prompt,
        "output_targets": output_targets,
        "provider": provider,
        "mode": "DETERMINISTIC_FIXTURE" if provider == "deterministic" else "OPENROUTER",
        "source_facts": {
            "address": source.get("address"),
            "price": source.get("price"),
            "beds": source.get("beds"),
            "baths": source.get("baths"),
            "area_sqft": source.get("area_sqft"),
            "features": source.get("features", []),
        },
        "beats": [
            {"id": "signal", "purpose": "establish the creative promise", "duration_seconds": 3},
            {"id": "arrival", "purpose": "introduce the source subject", "duration_seconds": 4},
            {"id": "details", "purpose": "show supported features", "duration_seconds": 6},
            {"id": "handoff", "purpose": "present the review or CTA handoff", "duration_seconds": 4},
        ],
    }
    if provider == "openrouter":
        if pipeline is None:
            raise ValueError("pipeline is required for provider=openrouter creative planning")
        bound_claims = claims if claims is not None else pipeline.build_claims(source)
        generated = pipeline.openrouter_creative_plan(prompt, source, bound_claims, output_targets)
        plan.update(
            {
                "creative_direction": generated["creative_direction"],
                "beats": generated["beats"],
                "claim_ids": generated["claim_ids"],
                "provider_metadata": generated["provider_metadata"],
            }
        )
    return plan


def validate_provider_configuration(provider: str) -> None:
    if provider != "openrouter":
        return
    missing = [
        name
        for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL")
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise ValueError(f"{', '.join(missing)} are required for provider=openrouter")


def render_website(source: dict[str, Any], prompt: str, destination: Path) -> dict[str, str]:
    destination.mkdir(parents=True, exist_ok=True)
    features = "".join(f"<li>{escape(str(feature))}</li>" for feature in source.get("features", []))
    address = escape(str(source.get("address", "Approved source")))
    safe_prompt = escape(prompt)
    html = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{address} | Creative Studio</title>
<style>body{{margin:0;background:#08131f;color:#eef7fb;font:16px/1.5 system-ui,sans-serif}}main{{max-width:980px;margin:auto;padding:72px 28px}}.eyebrow{{color:#e8b968;text-transform:uppercase;letter-spacing:.16em;font-size:11px}}h1{{font-size:clamp(42px,8vw,86px);line-height:.98;max-width:760px}}.facts{{display:flex;gap:18px;flex-wrap:wrap;color:#9ec3d0}}.facts strong{{color:#fff}}.card{{margin-top:48px;padding:24px;border:1px solid #24455b;border-radius:18px;background:#102638}}li{{margin:8px 0}}small{{color:#89a9bb}}</style></head>
<body><main><div class=\"eyebrow\">Syzygy Creative Studio · local artifact</div><h1>{address}</h1><p>{safe_prompt}</p><div class=\"facts\"><span><strong>{escape(str(source.get('price','Price on request')))}</strong></span><span><strong>{escape(str(source.get('beds','?')))}</strong> beds</span><span><strong>{escape(str(source.get('baths','?')))}</strong> baths</span><span><strong>{escape(str(source.get('area_sqft','?')))}</strong> sq ft</span></div><section class=\"card\"><div class=\"eyebrow\">Supported features</div><ul>{features}</ul><small>Generated from an approved local source package. Verify before publishing.</small></section></main></body></html>"""
    path = destination / "index.html"
    path.write_text(html, encoding="utf-8")
    return {"website": "artifacts/website/index.html"}


def render_presentation(source: dict[str, Any], prompt: str, destination: Path) -> dict[str, str]:
    """Create a source-bound, portable slide-deck artifact without a hosted dependency."""
    destination.mkdir(parents=True, exist_ok=True)
    address = escape(str(source.get("address", "Approved source")))
    price = escape(str(source.get("price", "Price on request")))
    beds = escape(str(source.get("beds", "?")))
    baths = escape(str(source.get("baths", "?")))
    area = escape(str(source.get("area_sqft", "?")))
    safe_prompt = escape(prompt)
    feature_items = "".join(f"<li>{escape(str(feature))}</li>" for feature in source.get("features", []))
    html = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{address} | Presentation</title>
<style>body{{margin:0;background:#07131f;color:#f4f8fb;font:18px/1.45 system-ui,sans-serif}}.deck{{display:grid;gap:22px;padding:30px;max-width:1100px;margin:auto}}.slide{{min-height:520px;padding:54px;border:1px solid #2b5268;border-radius:24px;background:linear-gradient(135deg,#173b54,#0b1b29);display:flex;flex-direction:column;justify-content:center}}.kicker{{color:#e8b968;text-transform:uppercase;letter-spacing:.18em;font-size:12px}}h1{{font-size:clamp(46px,8vw,96px);line-height:.95;margin:18px 0}}h2{{font-size:42px;margin:8px 0 24px}}.facts{{display:flex;gap:22px;flex-wrap:wrap;color:#b7d3df}}.facts b{{color:white}}li{{margin:12px 0}}</style></head>
<body><main class=\"deck\"><section class=\"slide\"><div class=\"kicker\">Syzygy Creative Studio · slide 01</div><h1>{address}</h1><p>{safe_prompt}</p></section><section class=\"slide\"><div class=\"kicker\">The proposition</div><h2>Room to live well.</h2><div class=\"facts\"><span><b>{price}</b></span><span><b>{beds}</b> beds</span><span><b>{baths}</b> baths</span><span><b>{area}</b> sq ft</span></div></section><section class=\"slide\"><div class=\"kicker\">Supported details</div><h2>What the source confirms</h2><ul>{feature_items}</ul></section><section class=\"slide\"><div class=\"kicker\">Review handoff</div><h2>Verify, then publish.</h2><p>This deck was generated from an approved local source package. Confirm facts, rights, and final copy before external use.</p></section></main></body></html>"""
    (destination / "index.html").write_text(html, encoding="utf-8")
    return {"presentation": "artifacts/presentation/index.html"}


def render_app_prototype(source: dict[str, Any], prompt: str, destination: Path) -> dict[str, str]:
    """Create a self-contained interactive listing-app prototype for local review."""
    destination.mkdir(parents=True, exist_ok=True)
    address = escape(str(source.get("address", "Approved source")))
    price = escape(str(source.get("price", "Price on request")))
    facts_json = json.dumps(
        {
            "address": str(source.get("address", "Approved source")),
            "price": str(source.get("price", "Price on request")),
            "beds": source.get("beds", "?"),
            "baths": source.get("baths", "?"),
            "area_sqft": source.get("area_sqft", "?"),
            "features": source.get("features", []),
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{address} | App Prototype</title>
<style>body{{margin:0;background:#f3f7f8;color:#112533;font:16px/1.5 system-ui,sans-serif}}header{{padding:22px 28px;background:#102638;color:white;display:flex;justify-content:space-between;gap:16px;align-items:center}}main{{max-width:960px;margin:auto;padding:36px 22px}}.hero{{padding:34px;border-radius:22px;background:linear-gradient(135deg,#1b5262,#102638);color:white}}h1{{font-size:clamp(36px,7vw,72px);line-height:1;margin:0 0 16px}}.facts{{display:flex;gap:16px;flex-wrap:wrap}}.facts span{{padding:10px 14px;border-radius:999px;background:#ffffff1c}}.card{{margin-top:22px;background:white;border:1px solid #d3e1e5;border-radius:18px;padding:24px}}button{{border:0;border-radius:10px;padding:12px 16px;background:#e8b968;color:#20160d;font-weight:700;cursor:pointer}}#details{{display:none}}small{{color:#5d7580}}</style></head>
<body><header><strong>Creative Studio app prototype</strong><span>local artifact</span></header><main><section class=\"hero\"><h1>{address}</h1><p>Explore the source-bound listing experience.</p><div class=\"facts\"><span>{price}</span><span id=\"beds\"></span><span id=\"baths\"></span><span id=\"area\"></span></div></section><section class=\"card\"><button id=\"toggle\">Show supported details</button><div id=\"details\"><ul id=\"features\"></ul><small>Generated from an approved local source package. Verify before publishing.</small></div></section></main><script>const source={facts_json};document.getElementById('beds').textContent=source.beds+' beds';document.getElementById('baths').textContent=source.baths+' baths';document.getElementById('area').textContent=source.area_sqft+' sq ft';document.getElementById('features').innerHTML=source.features.map(item=>'<li>'+String(item).replace(/[&<>\"']/g,char=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[char]))+'</li>').join('');document.getElementById('toggle').onclick=()=>{{const details=document.getElementById('details');details.style.display=details.style.display==='block'?'none':'block';}};</script></body></html>"""
    (destination / "index.html").write_text(html, encoding="utf-8")
    return {"app": "artifacts/app/index.html"}


def render_content_pack(source: dict[str, Any], prompt: str, pipeline_result: dict[str, Any], destination: Path) -> dict[str, str]:
    """Write local, reviewable platform drafts without attempting publication."""
    destination.mkdir(parents=True, exist_ok=True)
    copy = pipeline_result.get("campaign", {}).get("copy", {})
    address = str(source.get("address", "Approved source"))
    facts = f"{source.get('beds', '?')} beds · {source.get('baths', '?')} baths · {source.get('area_sqft', '?')} sq ft"
    caption = str(copy.get("social_caption", f"Now presenting {address}. {facts}."))
    video_script = str(copy.get("video_script", f"Welcome to {address}. {facts}."))
    drafts = {
        "content_pack_version": "creative.content-pack@1.0.0",
        "status": "DRAFT_NEEDS_REVIEW",
        "source": {"address": address, "source_url": source.get("source_url")},
        "brief": prompt,
        "platform_drafts": {
            "instagram": {"format": "caption", "text": caption, "approval": "REQUIRED"},
            "tiktok": {"format": "short_video_caption", "text": caption, "approval": "REQUIRED"},
            "youtube": {"format": "long_form_description", "text": video_script, "approval": "REQUIRED"},
            "linkedin": {"format": "post", "text": caption, "approval": "REQUIRED"},
        },
        "content_calendar": [{"slot": "next_available", "status": "DRAFT", "platforms": ["instagram", "tiktok", "youtube", "linkedin"]}],
        "external_effects": "NOT_ATTEMPTED",
        "publishing": "DISABLED",
    }
    json_path = destination / "content-pack.json"
    json_path.write_text(json.dumps(drafts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown = [
        "# Content pack — draft only",
        "",
        f"Source: {address}",
        f"Brief: {prompt}",
        "",
        "External publishing is disabled. Each platform draft requires explicit review and platform authorization.",
        "",
    ]
    for platform, draft in drafts["platform_drafts"].items():
        markdown.extend([f"## {platform}", "", draft["text"], "", "Approval: REQUIRED", ""])
    (destination / "content-pack.md").write_text("\n".join(markdown), encoding="utf-8")
    return {
        "content_json": "artifacts/content/content-pack.json",
        "content_markdown": "artifacts/content/content-pack.md",
    }


def import_pipeline() -> Any:
    if str(PIPELINE_SRC) not in sys.path:
        sys.path.insert(0, str(PIPELINE_SRC))
    import pipeline  # type: ignore[import-not-found]

    return pipeline


def copy_hyperframes_project(destination: Path, run: dict[str, Any], source: dict[str, Any]) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        HYPERFRAMES_SHOWCASE,
        destination,
        ignore=shutil.ignore_patterns("node_modules", "renders", "meta.json", "snapshots"),
    )
    brief = destination / "BRIEF.md"
    brief.write_text(
        "# Creative Fabric run\n\n"
        f"Run: `{run['run_id']}`\n\n"
        f"Intent: {run['request']['prompt']}\n\n"
        "This composition is generated locally and remains pending operator review.\n",
        encoding="utf-8",
    )
    index = destination / "index.html"
    composition = index.read_text(encoding="utf-8")
    address = escape(str(source.get("address", "Approved source")))
    address_parts = address.split(",", 1)
    address_html = address_parts[0] + ("<br />" + address_parts[1].strip() if len(address_parts) == 2 else "")
    specs = f"{escape(str(source.get('beds', '?')))} beds · {escape(str(source.get('baths', '?')))} baths<br />{escape(str(source.get('area_sqft', '?')))} sq ft"
    composition = composition.replace("100 Example<br />Avenue", address_html)
    composition = composition.replace("Testville<br />3 beds · 2.5 baths<br />2,100 sq ft", specs)
    composition = composition.replace("$625,000", escape(str(source.get("price", "Price on request"))))
    index.write_text(composition, encoding="utf-8")


def run_hyperframes_checks(project: Path, run_dir: Path) -> dict[str, Any]:
    if os.environ.get("SYZYGY_CREATIVE_STUDIO_SKIP_HYPERFRAMES") == "1":
        return {"status": "SKIPPED", "reason": "explicit_test_override"}

    npx = "npx.cmd" if os.name == "nt" else "npx"
    check = subprocess.run(
        [npx, "hyperframes@0.8.46", "check", "--json", "--strict"],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    result: dict[str, Any] = {
        "status": "PASS" if check.returncode == 0 else "FAIL",
        "returncode": check.returncode,
        "stdout": check.stdout[-12000:],
        "stderr": check.stderr[-12000:],
    }

    if check.returncode == 0:
        snapshot = subprocess.run(
            [npx, "hyperframes@0.8.46", "snapshot", "--at", "1,5,9,13,17", "--json"],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        result["snapshot"] = {
            "status": "PASS" if snapshot.returncode == 0 else "FAIL",
            "returncode": snapshot.returncode,
            "stdout": snapshot.stdout[-12000:],
            "stderr": snapshot.stderr[-12000:],
        }

    write_json(run_dir / "hyperframes-check.json", result)
    return result


def render_hyperframes(project: Path, output: Path, quality: str) -> dict[str, Any]:
    """Render a checked HyperFrames project and return inspectable encoder evidence."""
    if quality not in {"looks", "delivery"}:
        raise ValueError("quality must be looks or delivery")
    output.parent.mkdir(parents=True, exist_ok=True)
    npx = "npx.cmd" if os.name == "nt" else "npx"
    command = [
        npx,
        "hyperframes@0.8.46",
        "render",
        str(project),
        "--quality",
        quality,
        "--strict",
        "--output",
        str(output),
    ]
    render = subprocess.run(
        command,
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    if render.returncode != 0:
        raise subprocess.CalledProcessError(
            render.returncode,
            command,
            output=render.stdout[-16000:],
            stderr=render.stderr[-16000:],
        )
    if not output.is_file() or output.stat().st_size <= 0:
        raise ValueError("render completed without a non-empty output file")

    ffprobe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if ffprobe.returncode != 0:
        raise subprocess.CalledProcessError(
            ffprobe.returncode,
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(output)],
            output=ffprobe.stdout[-12000:],
            stderr=ffprobe.stderr[-12000:],
        )
    try:
        metadata = json.loads(ffprobe.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("ffprobe returned invalid JSON") from exc
    streams = metadata.get("streams") or []
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    if not video_streams:
        raise ValueError("render output has no video stream")
    duration = float((metadata.get("format") or {}).get("duration") or 0)
    if duration <= 0:
        raise ValueError("render output has no positive duration")
    return {
        "command": command,
        "quality": quality,
        "stdout": render.stdout[-16000:],
        "stderr": render.stderr[-16000:],
        "ffprobe": metadata,
    }


def create_run(payload: dict[str, Any], run_id: str | None = None, run_checks: bool = True) -> dict[str, Any]:
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")

    provider = str(payload.get("provider", "deterministic"))
    if provider not in {"deterministic", "openrouter"}:
        raise ValueError("provider must be deterministic or openrouter")
    validate_provider_configuration(provider)

    output_targets = payload.get("output_targets") or ["video"]
    if not isinstance(output_targets, list) or not output_targets:
        raise ValueError("output_targets must be a non-empty list")
    allowed_targets = {"video", "website", "presentation", "app", "content"}
    unsupported_targets = sorted(set(output_targets) - allowed_targets)
    if unsupported_targets:
        raise ValueError(f"unsupported output target(s): {', '.join(unsupported_targets)}")

    idempotency_key = str(payload.get("idempotency_key", "")).strip()
    pipeline = import_pipeline()
    source = validate_source(payload.get("source") or fixture_property(), pipeline)
    request_fingerprint = digest_json(
        {
            "prompt": prompt,
            "provider": provider,
            "output_targets": output_targets,
            "source": source,
        }
    )
    if idempotency_key:
        for existing in list_runs():
            existing_request = existing.get("request") or {}
            if existing_request.get("idempotency_key") != idempotency_key:
                continue
            if existing_request.get("fingerprint") != request_fingerprint:
                raise ValueError("idempotency key is already bound to a different request")
            return existing

    run_id = run_id or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    require_safe_run_id(run_id)
    run_dir = RUNS_ROOT / run_id
    if run_dir.exists():
        raise ValueError(f"run already exists: {run_id}")
    run_dir.mkdir(parents=True, exist_ok=False)

    request = {
        "prompt": prompt,
        "provider": provider,
        "output_targets": output_targets,
        "created_at": utc_now(),
        "external_effects": "NOT_ATTEMPTED",
        "idempotency_key": idempotency_key or None,
        "fingerprint": request_fingerprint,
    }
    write_json(run_dir / "request.json", request)
    write_json(run_dir / "inputs" / "source.json", source)
    images_dir = run_dir / "inputs" / "images"
    shutil.copytree(FIXTURE_IMAGES, images_dir)

    claims = pipeline.build_claims(source)
    creative_plan = build_creative_plan(prompt, source, output_targets, provider, pipeline, claims)
    artifacts_dir = run_dir / "artifacts"
    pipeline_result = pipeline.run_pipeline(
        str(run_dir / "inputs" / "source.json"),
        str(images_dir),
        str(artifacts_dir),
        provider=provider,
    )

    run_record: dict[str, Any] = {
        "run_id": run_id,
        "status": "COMPOSITION_READY",
        "request": request,
        "source_manifest": {
            "path": "inputs/source.json",
            "sha256": digest_file(run_dir / "inputs" / "source.json"),
        },
        "plan": creative_plan,
        "pipeline": pipeline_result["audit"],
        "external_effects": "NOT_ATTEMPTED",
        "created_at": request["created_at"],
    }
    write_json(run_dir / "plan.json", run_record["plan"])

    generated_artifacts: dict[str, str] = {}
    if "website" in output_targets:
        generated_artifacts.update(render_website(source, prompt, artifacts_dir / "website"))
    if "presentation" in output_targets:
        generated_artifacts.update(render_presentation(source, prompt, artifacts_dir / "presentation"))
    if "app" in output_targets:
        generated_artifacts.update(render_app_prototype(source, prompt, artifacts_dir / "app"))
    if "content" in output_targets:
        generated_artifacts.update(render_content_pack(source, prompt, pipeline_result, artifacts_dir / "content"))
    run_record["artifacts"] = generated_artifacts

    hyperframes_dir = run_dir / "hyperframes"
    copy_hyperframes_project(hyperframes_dir, {"run_id": run_id, "request": request}, source)
    run_record["composition"] = {"path": "hyperframes", "source": "editable_project_folder"}

    checks = run_hyperframes_checks(hyperframes_dir, run_dir) if run_checks else {"status": "NOT_RUN"}
    run_record["checks"] = checks
    if checks.get("status") == "PASS" and checks.get("snapshot", {}).get("status") == "PASS":
        run_record["status"] = "NEEDS_REVIEW"
    elif checks.get("status") in {"NOT_RUN", "SKIPPED"}:
        run_record["status"] = "NEEDS_REVIEW"
    else:
        run_record["status"] = "BLOCKED"

    evidence = {
        "evidence_version": "creative.evidence@1.0.0",
        "run_id": run_id,
        "source_sha256": run_record["source_manifest"]["sha256"],
        "plan_sha256": digest_file(run_dir / "plan.json"),
        "pipeline_audit": "artifacts/audit.json",
        "generated_artifacts": generated_artifacts,
        "hyperframes_check": "hyperframes-check.json",
        "external_effects": "NOT_ATTEMPTED",
        "qualification_boundary": "LOCAL_SOURCE_TO_PREVIEW",
    }
    write_json(run_dir / "evidence.json", evidence)
    run_record["evidence"] = evidence
    write_json(run_dir / "run.json", run_record)
    return run_record


def list_runs() -> list[dict[str, Any]]:
    if not RUNS_ROOT.exists():
        return []
    runs = []
    for path in RUNS_ROOT.glob("*/run.json"):
        try:
            runs.append(read_json(path))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(runs, key=lambda item: item.get("created_at", ""), reverse=True)


def approve_run(run_id: str) -> dict[str, Any]:
    path = RUNS_ROOT / run_id / "run.json"
    if not path.exists():
        raise FileNotFoundError(run_id)
    run = read_json(path)
    if run.get("status") != "NEEDS_REVIEW":
        raise ValueError(f"run is not awaiting review: {run.get('status')}")
    run["status"] = "APPROVED"
    run["approved_at"] = utc_now()
    run["approval_binding"] = {
        "source_sha256": digest_file(RUNS_ROOT / run_id / "inputs" / "source.json"),
        "plan_sha256": digest_file(RUNS_ROOT / run_id / "plan.json"),
    }
    run["external_effects"] = "NOT_ATTEMPTED"
    write_json(path, run)
    return run


def render_run(run_id: str, quality: str = "looks") -> dict[str, Any]:
    """Render only the exact approved composition, after revalidating its evidence."""
    run_dir = RUNS_ROOT / run_id
    path = run_dir / "run.json"
    if not path.exists():
        raise FileNotFoundError(run_id)
    run = read_json(path)
    if run.get("status") != "APPROVED":
        raise ValueError(f"render requires APPROVED run: {run.get('status')}")

    source_path = run_dir / "inputs" / "source.json"
    plan_path = run_dir / "plan.json"
    current_source_hash = digest_file(source_path)
    current_plan_hash = digest_file(plan_path)
    evidence = run.get("evidence") or {}
    binding = run.get("approval_binding") or {}
    expected_source_hash = evidence.get("source_sha256")
    expected_plan_hash = evidence.get("plan_sha256")
    if (
        current_source_hash != expected_source_hash
        or current_plan_hash != expected_plan_hash
        or current_source_hash != binding.get("source_sha256")
        or current_plan_hash != binding.get("plan_sha256")
    ):
        run["status"] = "BLOCKED"
        run["render_blocked_reason"] = "STALE_APPROVAL"
        write_json(path, run)
        raise ValueError("STALE_APPROVAL: source or plan changed after approval")

    checks = read_json(run_dir / "hyperframes-check.json") if (run_dir / "hyperframes-check.json").exists() else run.get("checks", {})
    if checks.get("status") != "PASS" or (checks.get("snapshot") or {}).get("status") != "PASS":
        raise ValueError("render requires PASS HyperFrames check and snapshot evidence")

    output = run_dir / "artifacts" / "hyperframes" / "reel.mp4"
    receipt: dict[str, Any] = {
        "receipt_version": "creative.render@1.0.0",
        "run_id": run_id,
        "status": "STARTED",
        "quality": quality,
        "source_sha256": current_source_hash,
        "plan_sha256": current_plan_hash,
        "external_effects": "NOT_ATTEMPTED",
        "started_at": utc_now(),
    }
    try:
        result = render_hyperframes(run_dir / "hyperframes", output, quality)
        if not isinstance(result, dict):
            raise ValueError("renderer returned no evidence object")
        output_size = output.stat().st_size
        output_sha256 = digest_file(output)
        receipt.update(result)
        receipt.update(
            {
                "status": "PASS",
                "output": "artifacts/hyperframes/reel.mp4",
                "size_bytes": output_size,
                "sha256": output_sha256,
                "completed_at": utc_now(),
            }
        )
    except Exception as exc:
        receipt.update({"status": "FAIL", "error": str(exc), "completed_at": utc_now()})
        write_json(run_dir / "render-receipt.json", receipt)
        raise

    write_json(run_dir / "render-receipt.json", receipt)
    run["status"] = "RENDERED"
    run["render"] = {
        "path": "artifacts/hyperframes/reel.mp4",
        "receipt": "render-receipt.json",
        "quality": quality,
        "sha256": output_sha256,
        "size_bytes": output_size,
    }
    run["external_effects"] = "NOT_ATTEMPTED"
    write_json(path, run)
    return run


def export_run(run_id: str) -> dict[str, Any]:
    """Package a rendered run and its evidence without performing an external effect."""
    run_dir = RUNS_ROOT / run_id
    path = run_dir / "run.json"
    if not path.exists():
        raise FileNotFoundError(run_id)
    run = read_json(path)
    if run.get("status") != "RENDERED":
        raise ValueError(f"export requires RENDERED run: {run.get('status')}")

    render_receipt_path = run_dir / "render-receipt.json"
    render_receipt = read_json(render_receipt_path) if render_receipt_path.exists() else {}
    render_path = run_dir / "artifacts" / "hyperframes" / "reel.mp4"
    if render_receipt.get("status") != "PASS" or not render_path.is_file():
        raise ValueError("export requires a PASS render receipt and rendered MP4")
    if digest_file(render_path) != render_receipt.get("sha256"):
        raise ValueError("export refused: rendered MP4 hash does not match receipt")

    export_dir = run_dir / "artifacts" / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    output = export_dir / f"creative-run-{run_id}.zip"
    files: list[dict[str, Any]] = []
    for candidate in sorted(run_dir.rglob("*")):
        if not candidate.is_file() or export_dir in candidate.parents:
            continue
        relative = candidate.relative_to(run_dir).as_posix()
        files.append({"path": relative, "size_bytes": candidate.stat().st_size, "sha256": digest_file(candidate)})
    manifest = {
        "bundle_version": "creative.export@1.0.0",
        "run_id": run_id,
        "status": "RENDERED_AT_EXPORT",
        "source_sha256": run.get("evidence", {}).get("source_sha256"),
        "plan_sha256": run.get("evidence", {}).get("plan_sha256"),
        "files": files,
        "external_effects": "NOT_ATTEMPTED",
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("export-manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        for item in files:
            bundle.write(run_dir / Path(item["path"]), item["path"])

    receipt = {
        "receipt_version": "creative.export@1.0.0",
        "run_id": run_id,
        "status": "PASS",
        "output": f"artifacts/export/{output.name}",
        "size_bytes": output.stat().st_size,
        "sha256": digest_file(output),
        "file_count": len(files),
        "source_sha256": manifest["source_sha256"],
        "plan_sha256": manifest["plan_sha256"],
        "external_effects": "NOT_ATTEMPTED",
        "completed_at": utc_now(),
    }
    write_json(run_dir / "export-receipt.json", receipt)
    run["status"] = "EXPORTED"
    run["export"] = {
        "path": receipt["output"],
        "receipt": "export-receipt.json",
        "sha256": receipt["sha256"],
        "size_bytes": receipt["size_bytes"],
        "file_count": receipt["file_count"],
    }
    run["external_effects"] = "NOT_ATTEMPTED"
    write_json(path, run)
    return run


class StudioHandler(BaseHTTPRequestHandler):
    server_version = "SyzygyCreativeStudio/0.1"

    def requires_authentication(self) -> bool:
        """Require an operator token whenever the listener is not loopback-only."""
        return not is_loopback_host(str(self.server.server_address[0]))

    def authorized(self) -> bool:
        if not self.requires_authentication():
            return True
        expected = str(getattr(self.server, "auth_token", ""))
        supplied = self.headers.get("Authorization", "")
        return bool(expected) and hmac.compare_digest(supplied, f"Bearer {expected}")

    def require_authorization(self) -> bool:
        if self.authorized():
            return True
        self.send_json({"error": "authentication required"}, HTTPStatus.UNAUTHORIZED)
        return False

    def send_json(self, value: Any, status: int = HTTPStatus.OK, head_only: bool = False) -> None:
        body = json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_HEAD(self) -> None:  # noqa: N802
        """Return GET-equivalent headers without reading or sending a body."""
        request_path = urlsplit(self.path).path
        if request_path == "/" or request_path == "/index.html":
            body = (WEB_ROOT / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if request_path == "/api/health":
            self.send_json({"status": "PASS", "service": "syzygy-creative-studio", "external_effects": "DISABLED"}, head_only=True)
            return
        if not self.require_authorization():
            return
        if request_path.startswith("/api/runs/") and "/artifacts/" in request_path:
            prefix, relative = request_path.split("/artifacts/", 1)
            run_id = unquote(prefix.removeprefix("/api/runs/"))
            candidate = resolve_artifact_path(run_id, relative)
            if candidate is None:
                self.send_json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND, head_only=True)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(candidate.stat().st_size))
            self.end_headers()
            return
        if request_path.startswith("/api/runs/"):
            run_id = unquote(request_path.removeprefix("/api/runs/").split("/", 1)[0])
            if not is_safe_run_id(run_id):
                self.send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND, head_only=True)
                return
            path = RUNS_ROOT / run_id / "run.json"
            if path.exists():
                self.send_json(read_json(path), head_only=True)
            else:
                self.send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND, head_only=True)
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND, head_only=True)

    def do_GET(self) -> None:  # noqa: N802
        request_path = urlsplit(self.path).path
        if request_path == "/" or request_path == "/index.html":
            body = (WEB_ROOT / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if request_path == "/api/health":
            self.send_json({"status": "PASS", "service": "syzygy-creative-studio", "external_effects": "DISABLED"})
            return
        if not self.require_authorization():
            return
        if request_path == "/api/runs":
            self.send_json({"runs": list_runs()})
            return
        if request_path.startswith("/api/runs/") and "/artifacts/" in request_path:
            prefix, relative = request_path.split("/artifacts/", 1)
            run_id = unquote(prefix.removeprefix("/api/runs/"))
            candidate = resolve_artifact_path(run_id, relative)
            if candidate is None:
                self.send_json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND)
                return
            body = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if request_path.startswith("/api/runs/"):
            run_id = unquote(request_path.removeprefix("/api/runs/").split("/", 1)[0])
            if not is_safe_run_id(run_id):
                self.send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
                return
            path = RUNS_ROOT / run_id / "run.json"
            if path.exists():
                self.send_json(read_json(path))
            else:
                self.send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not self.require_authorization():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "invalid Content-Length"}, HTTPStatus.BAD_REQUEST)
            return
        if length < 0 or length > MAX_REQUEST_BYTES:
            self.send_json({"error": f"request body exceeds {MAX_REQUEST_BYTES} bytes"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            request_path = urlsplit(self.path).path
            if request_path == "/api/runs":
                self.send_json(create_run(payload), HTTPStatus.CREATED)
                return
            if request_path.startswith("/api/runs/") and request_path.endswith("/approve"):
                run_id = unquote(request_path.removeprefix("/api/runs/").removesuffix("/approve").strip("/"))
                require_safe_run_id(run_id)
                self.send_json(approve_run(run_id))
                return
            if request_path.startswith("/api/runs/") and request_path.endswith("/render"):
                run_id = unquote(request_path.removeprefix("/api/runs/").removesuffix("/render").strip("/"))
                require_safe_run_id(run_id)
                quality = str(payload.get("quality", "looks"))
                self.send_json(render_run(run_id, quality=quality))
                return
            if request_path.startswith("/api/runs/") and request_path.endswith("/export"):
                run_id = unquote(request_path.removeprefix("/api/runs/").removesuffix("/export").strip("/"))
                require_safe_run_id(run_id)
                self.send_json(export_run(run_id))
                return
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except FileNotFoundError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError, subprocess.SubprocessError, RuntimeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # defensive boundary for the local service
            self.send_json({"error": f"internal error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Syzygy Creative Studio local MVP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--once", action="store_true", help="run the deterministic fixture once and exit")
    args = parser.parse_args()

    if args.once:
        result = create_run({"prompt": "Create a cinematic property showcase for this listing.", "output_targets": ["video"]})
        print(json.dumps({"run_id": result["run_id"], "status": result["status"], "evidence": result["evidence"]}, indent=2))
        return 0 if result["status"] == "NEEDS_REVIEW" else 1

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    if not is_loopback_host(args.host) and os.environ.get("SYZYGY_CREATIVE_STUDIO_ALLOW_NON_LOOPBACK") != "1":
        parser.error("non-loopback binding requires SYZYGY_CREATIVE_STUDIO_ALLOW_NON_LOOPBACK=1")
    auth_token = os.environ.get(AUTH_TOKEN_ENV, "").strip()
    if not is_loopback_host(args.host) and not auth_token:
        parser.error(f"non-loopback binding requires {AUTH_TOKEN_ENV}")
    server = ThreadingHTTPServer((args.host, args.port), StudioHandler)
    server.auth_token = auth_token
    print(f"Syzygy Creative Studio listening at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
