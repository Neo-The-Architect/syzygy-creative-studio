# Quark short-form creative preflight (EFF-61) — Draft integration

This bounded **read-only** addition to the existing Syzygy Creative Studio accepts
source-grounded 9:16 creative candidates and checks the lane boundaries and
comparability of A/B/C hooks before they reach a renderer. It does not create
runs, media, post drafts or approvals; it cannot spend credits, publish, send
messages, create accounts or change lead destinations. This is an integration
seam, **not** the complete video production or sales system.

## HTTP input

`POST http://127.0.0.1:8765/api/shortform/preflight`

- One candidate: `{ "creative": { ... } }` using fields in the Quark pilot
  `creatives/EL-P01-*.json` record.
- Up to 24 variants: `{ "creatives": [{ ... }, ...] }`.
- A full 3-format test has exactly PARENT, FOUNDER and STUDIO lanes, each A/B/C.

For video candidates, this preflight produces a safe `render_intent` with 9:16
(1080×1920, 24fps), but **no invented duration** or media readiness. A subsequent
adapter must source actual footage, score design, validate rights, resolve
caption safe areas and render through the current HyperFrames approval-bound
pipeline. A successful HTTP 200 signals only schema/hypothesis checking, not
publication or production authorization. Invalid inputs return HTTP 400.

The existing remote-bound HTTP service still requires its Bearer token; loopback
works per the current app security model. Run the unmodified `verify_local.py`
script for full suite. Add no credentials to creative JSON or requests.

## Source snapshot and release gates

Canonical Pilot 01 package: private Efficient Labs Google Drive →
`Efficient-Labs-Company-Library/_work/Quark-Cinematic-Content-Pilot-01`.
Skill package: `Efficient-Labs-Company-Library/skills/quark-visual-influence`.
Track the implementation in EFF-61. EFF-50 keeps the Studio separate from
Efficient Labs and founder channels. EFF-36's proposed commercial prices are
**not approved for publishing**.

Only 1 of the 9 original creatives has an offline internal motion prototype
with a previous receipt. None has a verified consented presenter, approved
Studio identity, operational CTA or publication permission by virtue of this PR.

**Runtime classification:** local unit/HTTP verification when executed; CI is
required for repository compatibility. Full paid-provider render and external
publication remain untested and intentionally disabled.
