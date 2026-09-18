# Open-source-first AI real-estate marketing pipeline

This is a local-first reference implementation inspired by the supplied video, but it removes the hard dependency on Claude Code, Hexfield, Fal, Veo, and Hybrid Frames.

## What it does

Given a verified property JSON record and a folder of rights-cleared images, it:

1. validates and normalizes the property record;
2. creates an evidence-bound claim ledger;
3. selects a balanced set of property images;
4. generates structured campaign copy with a deterministic provider or OpenRouter;
5. renders a vertical social reel with Pillow and FFmpeg;
6. renders a 16:9 animated digital brochure with Pillow and FFmpeg;
7. writes a campaign manifest and audit report;
8. runs deterministic end-to-end tests.

The default test path is offline and uses synthetic fixture images. It does not publish, message, scrape a third-party site, or send private data to a model provider.

## Requirements

- Python 3.11+
- Pillow 12+
- FFmpeg available on PATH

Optional:

- `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` for live structured copy generation.

## Run the offline pipeline

From this directory:

```powershell
python src/create_fixture.py
python src/pipeline.py --property fixtures/property.json --images fixtures/images --out outputs/run-offline --provider deterministic
python -m unittest discover -s tests -v
```

Expected artifacts:

- `outputs/run-offline/reel_final.mp4`
- `outputs/run-offline/brochure_final.mp4`
- `outputs/run-offline/campaign.json`
- `outputs/run-offline/audit.json`

## Run with OpenRouter

Set the key and a model available to the account, then run:

```powershell
$env:OPENROUTER_API_KEY = '...'
$env:OPENROUTER_MODEL = 'your/structured-output-capable-model'
python src/pipeline.py --property fixtures/property.json --images fixtures/images --out outputs/run-openrouter --provider openrouter
```

Only sanitized property facts and the approved claim ledger are sent. Raw images, secrets, customer records, and unredacted documents are not sent by this reference adapter.

## Important boundary

This implementation proves local generation and rendering. It does not prove MLS permission, live publishing, lead-contact consent, ad-platform compliance, or production performance. Those require separate adapters and qualification evidence.
