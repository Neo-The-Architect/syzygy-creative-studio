# Syzygy Creative Studio

Syzygy Creative Studio is an open-source, local-first creative automation studio.
It turns an approved source package and a plain-language creative brief into
inspectable artifacts such as cinematic video, websites, presentations, and
future application prototypes.

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
```

The MVP does not publish to social platforms, send messages, mutate a CRM,
deploy services, or claim production readiness.

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

Open `http://127.0.0.1:8765`.

Run one complete deterministic fixture:

```powershell
python apps/creative-studio/app.py --once
```

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

## Evidence boundary

`IMPLEMENTED != TESTED != INTEGRATED != RUNTIME_VERIFIED != DEPLOYED != PRODUCTION_PROVEN`.

The MVP is proven only through the local source-to-preview boundary. External
publishing is disabled.

## License

MIT. See [LICENSE](LICENSE).
