"""Exercise the live local HTTP lifecycle without external effects.

This is intentionally separate from ``verify_local.py``: it requires a running
loopback service and performs one deterministic, approval-gated render/export
cycle so the full API boundary can be qualified repeatedly.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def request(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 180, raw_body: bool = False) -> tuple[int, dict[str, Any] | bytes, dict[str, str]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request_object = urllib.request.Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request_object, timeout=timeout) as response:
            response_body = response.read()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            content_type = response_headers.get("content-type", "")
            if raw_body:
                return response.status, response_body, response_headers
            if "json" in content_type:
                return response.status, json.loads(response_body.decode("utf-8")), response_headers
            return response.status, response_body, response_headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: dict[str, Any] | bytes = json.loads(detail)
        except json.JSONDecodeError:
            parsed = detail.encode("utf-8")
        return exc.code, parsed, {key.lower(): value for key, value in exc.headers.items()}


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, help="Optional path for the JSON evidence packet.")
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc).isoformat()
    key = f"runtime-verifier-{time.time_ns()}"
    source = {
        "source_url": "local://runtime-verifier",
        "address": "88 Acceptance Way, Testville",
        "price": "$905,000",
        "beds": 4,
        "baths": 3,
        "area_sqft": 2700,
        "features": ["sunlit studio", "garden terrace", "library wall"],
        "description": "Synthetic runtime verifier fixture only.",
    }
    payload = {
        "prompt": "Runtime verification of the complete local creative lifecycle.",
        "provider": "deterministic",
        "output_targets": ["video", "website", "presentation", "app", "content"],
        "idempotency_key": key,
        "source": source,
    }
    evidence: dict[str, Any] = {
        "evidence_version": "creative.runtime-verifier@1.0.0",
        "started_at": started_at,
        "base_url": args.base_url,
        "external_effects": "DISABLED",
        "provider": "deterministic",
    }

    try:
        status, health, _ = request(args.base_url, "GET", "/api/health", timeout=args.timeout)
        expect(status == 200 and isinstance(health, dict) and health.get("status") == "PASS", "health did not return PASS")
        expect(health.get("external_effects") == "DISABLED", "external effects are not disabled")

        status, created, _ = request(args.base_url, "POST", "/api/runs", payload, timeout=args.timeout)
        expect(status == 201 and isinstance(created, dict), f"create failed: HTTP {status}")
        run_id = str(created["run_id"])
        expect(created.get("status") == "NEEDS_REVIEW", f"create returned {created.get('status')}")
        expect((created.get("checks") or {}).get("status") == "PASS", "HyperFrames check did not pass")
        evidence["run_id"] = run_id
        evidence["transitions"] = [created["status"]]

        retry_status, retry, _ = request(args.base_url, "POST", "/api/runs", payload, timeout=args.timeout)
        expect(retry_status == 201 and isinstance(retry, dict), f"idempotency retry failed: HTTP {retry_status}")
        expect(retry.get("run_id") == run_id, "idempotency retry returned a different run")
        evidence["idempotency_retry"] = {"status": "PASS", "same_run_id": True}

        status, approved, _ = request(args.base_url, "POST", f"/api/runs/{run_id}/approve", {}, timeout=args.timeout)
        expect(status == 200 and isinstance(approved, dict) and approved.get("status") == "APPROVED", "approval failed")
        evidence["transitions"].append(approved["status"])

        status, rendered, _ = request(args.base_url, "POST", f"/api/runs/{run_id}/render", {"quality": "looks"}, timeout=args.timeout)
        expect(status == 200 and isinstance(rendered, dict) and rendered.get("status") == "RENDERED", "render failed")
        render = rendered.get("render") or {}
        expect(render.get("sha256") and int(render.get("size_bytes", 0)) > 0, "render receipt is incomplete")
        evidence["transitions"].append(rendered["status"])
        evidence["render"] = {"sha256": render["sha256"], "size_bytes": render["size_bytes"]}

        status, exported, _ = request(args.base_url, "POST", f"/api/runs/{run_id}/export", {}, timeout=args.timeout)
        expect(status == 200 and isinstance(exported, dict) and exported.get("status") == "EXPORTED", "export failed")
        export = exported.get("export") or {}
        expect(export.get("sha256") and int(export.get("file_count", 0)) > 0, "export receipt is incomplete")
        evidence["transitions"].append(exported["status"])
        evidence["export"] = {"sha256": export["sha256"], "size_bytes": export["size_bytes"], "file_count": export["file_count"]}

        artifact_paths = [
            "artifacts/website/index.html",
            "artifacts/presentation/index.html",
            "artifacts/app/index.html",
            "artifacts/content/content-pack.json",
            "artifacts/hyperframes/reel.mp4",
            export["path"],
        ]
        artifact_checks = []
        for relative in artifact_paths:
            path = f"/api/runs/{run_id}/artifacts/{relative}"
            get_status, body, _ = request(args.base_url, "GET", path, timeout=args.timeout, raw_body=True)
            expect(get_status == 200 and isinstance(body, (bytes, bytearray)) and len(body) > 0, f"artifact GET failed: {relative}")
            head_status, head_body, _ = request(args.base_url, "HEAD", path, timeout=args.timeout, raw_body=True)
            expect(head_status == 200 and isinstance(head_body, (bytes, bytearray)) and len(head_body) == 0, f"artifact HEAD failed: {relative}")
            artifact_checks.append({"path": relative, "get": get_status, "head": head_status, "bytes": len(body)})
        evidence["artifact_checks"] = artifact_checks
        evidence["status"] = "PASS"
        evidence["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        evidence["status"] = "FAIL"
        evidence["error"] = str(exc)
        evidence["completed_at"] = datetime.now(timezone.utc).isoformat()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
