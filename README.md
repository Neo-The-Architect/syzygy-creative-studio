# Syzygy Creative Studio

Syzygy Creative Studio is an open-source, local-first creative automation studio.
It turns an approved source package and a plain-language creative brief into
inspectable artifacts such as cinematic video, websites, presentations, and
interactive local application prototypes, plus reviewable platform content
drafts.

The project is designed to run on local hardware or operator-controlled remote
infrastructure. It uses OpenRouter as an optional reasoning/model-routing plane
and HyperFrames as an editable, deterministic HTML-to-video composition layer.

## Current MVP

The first vertical slice is deliberately small:

```text
prompt + approved property fixture
  -> source manifest and claims
  -> deterministic campaign
  -> editable HyperFrames project
  -> strict check and snapshots
  -> local review state
  -> explicit approval
  -> verified local MP4 render + receipt
  -> local evidence/artifact export bundle
```

The MVP does not publish to social platforms, send messages, mutate a CRM,
deploy services, or claim production readiness.

Rendering is intentionally a separate state transition. After a run reaches
`NEEDS_REVIEW`, the operator can approve the exact source and plan in the UI or
through `POST /api/runs/{run_id}/approve`. Only an `APPROVED` run with matching
source/plan hashes and passing HyperFrames check and snapshot evidence can call
`POST /api/runs/{run_id}/render`. The render receipt records the output hash,
size, quality, and `ffprobe` metadata; a changed source or plan fails closed as
`STALE_APPROVAL`.

Clients that may retry a request can include an `idempotency_key` in the run
payload. The service stores a request fingerprint, returns the original run for
an identical retry, and rejects reuse of that key for changed content.

After a run reaches `RENDERED`, the operator can call
`POST /api/runs/{run_id}/export` to create a local ZIP containing the source,
plan, checks, receipts, generated artifacts, and a file-hash manifest. Export
is a local handoff state (`EXPORTED`), not a publish or deployment action.

The optional `content` output target creates Instagram, TikTok, YouTube, and
LinkedIn drafts plus a local content-calendar entry. They are marked
`DRAFT_NEEDS_REVIEW`; publishing remains disabled and requires separate
platform authorization.

## Run the application

Requirements:

- Python 3.11+
- Node.js 20+
- FFmpeg on `PATH`
- HyperFrames CLI available through `npx`

From the repository root:

```powershell
python apps/creative-studio/app.py
```

Or use the loopback-only launcher from any PowerShell working directory:

```powershell
.\scripts\start_local.ps1
```

The launcher reuses an already healthy local service, keeps the worker in the
current terminal for inspectable logs, and never binds beyond `127.0.0.1`.
Add `-Open` to open the local UI automatically, or `-CheckOnly` to qualify
whether the service is already healthy without starting another process.

Open `http://127.0.0.1:8765`.

Run one complete deterministic fixture:

```powershell
python apps/creative-studio/app.py --once
```

Run the bounded local qualification checks:

```powershell
python scripts/verify_local.py
```

The verifier runs compilation, both focused test suites, recorded-evidence
presence checks, and an optional loopback health check. A stopped local service
is reported as `SKIP` by default; use `--require-health` when the persistent
service itself is part of the acceptance boundary. The verifier never calls
external providers or publishing APIs.

## Run tests

```powershell
python -m unittest discover -s apps/creative-studio/tests -v
python -m unittest discover -s packages/real-estate-pipeline/tests -v
```

## Project layout

```text
apps/creative-studio/          local application and desktop-friendly UI
packages/real-estate-pipeline/ property source and deterministic campaign adapter
packages/hyperframes-showcase/ editable HyperFrames composition and snapshots
docs-architecture.md           architecture and ownership model
docs-coding-agent-prompt.md    bounded implementation prompt for agents
delivery-rounds.yaml           evidence-driven delivery state
```

## Provider policy

Deterministic fixtures are the default. OpenRouter is an optional adapter for
structured planning and model selection. Configure it explicitly; do not place
keys in source, fixtures, logs, or public artifacts:

```powershell
$env:OPENROUTER_API_KEY = "..."
$env:OPENROUTER_MODEL = "..."
```

Provider-specific image/video/audio adapters are intentionally separate from
the core run state. A generated artifact is not automatically an approved or
published artifact.

The local UI exposes both provider routes. `deterministic fixture` is the
offline default. Selecting `OpenRouter` requires `OPENROUTER_API_KEY` and
`OPENROUTER_MODEL` to be configured in the process environment; missing
configuration or malformed model output fails the run with a typed error and
does not silently fall back to another model.

## Evidence boundary

`IMPLEMENTED != TESTED != INTEGRATED != RUNTIME_VERIFIED != DEPLOYED != PRODUCTION_PROVEN`.

The MVP is proven only through the local source-to-preview boundary. External
publishing is disabled.

## License

MIT. See [LICENSE](LICENSE).
