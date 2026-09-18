"""Run the repository's bounded local qualification checks.

The verifier intentionally separates deterministic source/test checks from the
optional live HTTP check. A missing local service is not treated as a failure
unless ``--require-health`` is supplied, and no external side effects are
performed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_check(label: str, command: list[str], timeout: int = 420) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "label": label,
            "command": command,
            "returncode": None,
            "status": "FAIL",
            "error": f"timed out after {timeout}s",
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
        }
    result: dict[str, object] = {
        "label": label,
        "command": command,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }
    if completed.stdout.strip():
        result["stdout"] = completed.stdout.strip()
    if completed.stderr.strip():
        result["stderr"] = completed.stderr.strip()
    return result


def health_check(url: str, required: bool) -> dict[str, object]:
    result: dict[str, object] = {
        "label": "live health",
        "url": url,
        "required": required,
    }
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result["response"] = payload
        result["status"] = "PASS" if payload.get("status") == "PASS" else "FAIL"
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        result["status"] = "FAIL" if required else "SKIP"
        result["error"] = str(exc)
    return result


def evidence_check() -> dict[str, object]:
    required = [
        "delivery-rounds.yaml",
        "examples/four-output-run/run-summary.json",
        "examples/exported-run/run-summary.json",
        "examples/content-pack-run/run-summary.json",
        "examples/idempotency-run/run-summary.json",
        "examples/security-boundary-run/run-summary.json",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    return {
        "label": "recorded evidence packets",
        "status": "PASS" if not missing else "FAIL",
        "required": required,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--health-url",
        default="http://127.0.0.1:8765/api/health",
        help="Local health endpoint to qualify (default: %(default)s)",
    )
    parser.add_argument(
        "--require-health",
        action="store_true",
        help="Fail when the local service is unavailable or reports non-PASS.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the concise report.",
    )
    args = parser.parse_args()

    checks = [
        run_check(
            "compile",
            [
                PYTHON,
                "-m",
                "py_compile",
                "apps/creative-studio/app.py",
                "packages/real-estate-pipeline/src/pipeline.py",
            ],
        ),
        run_check(
            "creative studio tests",
            [
                PYTHON,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/creative-studio/tests",
                "-v",
            ],
        ),
        run_check(
            "property pipeline tests",
            [
                PYTHON,
                "-m",
                "unittest",
                "discover",
                "-s",
                "packages/real-estate-pipeline/tests",
                "-v",
            ],
        ),
        evidence_check(),
        health_check(args.health_url, args.require_health),
    ]
    failures = [check for check in checks if check["status"] == "FAIL"]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "root": str(ROOT),
        "external_effects": "DISABLED",
        "checks": checks,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"STATUS: {report['status']}")
        for check in checks:
            detail = check.get("error", "")
            suffix = f" — {detail}" if detail else ""
            print(f"{check['status']}: {check['label']}{suffix}")
        print("EXTERNAL_EFFECTS: DISABLED")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
