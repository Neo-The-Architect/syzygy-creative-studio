# Coding-agent prompt: implement Syzygy Creative Studio

Syzygy Creative Studio is the application. Creative Fabric is its internal source-to-artifact execution capability.

Use this prompt with a coding agent only after selecting and explicitly authorizing one clean Syzygy target worktree.

## Role

You are the implementation agent for **Syzygy Creative Fabric**, a local-first creative-automation capability. You are not the system authority. Mission OS/WorkGraph remains the canonical work owner; Foundation Zero remains the admission, execution, receipt, and evidence authority; Pi remains the conversational/operator surface; Codex Box/Studio Presence remains a projection and intervention surface. HyperFrames is the inspectable composition, preview, and rendering layer.

## Mission

Implement the smallest evidence-bound vertical slice that accepts an approved source package—initially a real-estate listing—and produces an inspectable, reviewable creative run. The first slice must support:

1. source normalization and provenance;
2. claim extraction with unsupported-claim rejection;
3. a typed creative plan and storyboard;
4. OpenRouter model routing through strict structured output when configured;
5. generation of a HyperFrames project;
6. HyperFrames lint, strict check, and deterministic snapshots;
7. an approval-gated local preview state;
8. a content-addressed artifact/evidence bundle;
9. a desktop mini-application projection that lets the operator inspect and approve the run.

Do not build a second scheduler, Mission system, WorkGraph, memory fabric, evidence authority, release authority, or provider-control plane.

## Truth and safety rules

Preserve the invariant `CLAIM <= EVIDENCE`.

Never promote any of the following into production proof: model prose, a green unit test, a UI state, a dispatch receipt, a generated file, a successful compile, or a preview URL.

Keep these boundaries distinct:

```text
IMPLEMENTED != TESTED
TESTED != INTEGRATED
INTEGRATED != RUNTIME_VERIFIED
RUNTIME_VERIFIED != DEPLOYED
DEPLOYED != PRODUCTION_PROVEN
```

Fail closed when source provenance, rights, model configuration, approval, or postcondition evidence is missing. Never silently switch models or providers. Never publish, send, upload, contact a lead, mutate a CRM, or deploy as part of this slice.

## Preflight: stop before editing

1. Resolve the exact repository, worktree, branch, and HEAD.
2. Record dirty/untracked state and preserve unrelated changes.
3. Locate the existing Pi, Mission OS/WorkGraph, Foundation Zero, provider-routing, evidence, and Codex Box seams.
4. Read the local `AGENTS.md` and relevant architecture contracts.
5. Confirm the smallest allowed path set and test budget.
6. If the target worktree is dirty, ambiguous, or has an active writer, stop and report `BLOCKED`; do not edit a neighboring checkout.

Your first response must contain a short preflight report and a proposed bounded work-unit plan. Do not start implementation until the target is unambiguous.

## Canonical capability contract

Implement the following versioned capability at the existing owner-aligned seam:

```text
creative.fabric.run@1.0.0
```

Input:

```json
{
  "source_package_ref": "content-addressed source package",
  "creative_intent": {
    "brief": "what the artifact should communicate",
    "audience": "target audience",
    "tone": "visual and editorial direction",
    "cta": "optional call to action"
  },
  "output_targets": ["video", "website", "presentation"],
  "brand_profile_ref": "optional approved brand profile",
  "model_policy_ref": "approved provider/model policy",
  "media_rights_ref": "rights and license manifest",
  "review_policy_ref": "approval requirements"
}
```

Output:

```json
{
  "run_id": "stable run id",
  "status": "state-machine status",
  "source_manifest_ref": "manifest ref",
  "plan_ref": "creative plan ref",
  "composition_refs": ["HyperFrames project refs"],
  "artifact_refs": ["local artifact refs"],
  "evidence_bundle_ref": "evidence ref",
  "unresolved": ["explicit gaps, warnings, or blocked effects"],
  "external_effects": "NOT_ATTEMPTED"
}
```

Use the state machine:

```text
REQUESTED -> ADMITTED -> SOURCE_READY -> PLAN_READY -> COMPOSITION_READY
-> CHECKED -> PREVIEW_READY -> NEEDS_REVIEW -> APPROVED -> RENDERED -> EXPORTED
```

External publication is a separate future state machine and must remain disabled.

## Required sub-capabilities

Implement or map to existing owners rather than duplicating them:

```text
creative.source.normalize@1.0.0
creative.claims.extract@1.0.0
creative.plan.storyboard@1.0.0
creative.plan.asset-map@1.0.0
creative.compose.hyperframes@1.0.0
creative.check.hyperframes@1.0.0
creative.preview.hyperframes@1.0.0
creative.render.hyperframes@1.0.0
creative.export.bundle@1.0.0
```

The first vertical slice may leave render/export as approval-gated stubs, but the contract and evidence must make that limitation explicit.

## HyperFrames implementation rules

Treat the HyperFrames project folder as the source of truth. Keep the project editable and local:

- `BRIEF.md` — intent and audience;
- `STORYBOARD.md` — beats, timings, transitions, and visual purpose;
- `SCRIPT.md` — approved narration/copy when applicable;
- `frame.md` — composition contract;
- `index.html` — composition entry point;
- `hyperframes.json` — project configuration;
- `compositions/` — reusable scenes;
- `assets/` — local, rights-bound media;
- `renders/` — generated output only.

Use explicit IDs, explicit `data-track-index`, deterministic timing, local media, and intentional overflow annotations. Run lint and strict check before snapshots. Do not call a successful check a rendered deliverable. Do not render until the review policy says the run is approved.

## OpenRouter implementation rules

Use OpenRouter only as the model-routing plane, not as authority. Creating a
provider-selected candidate must remain local and deterministic; do not read
provider credentials or send source data until a separate explicit,
approval-bound provider action is confirmed. Prefer strict structured JSON
output with a schema for source claims, storyboard beats, asset requests, and
copy variants. Record provider, model, request id, schema version, latency,
token usage when available, and failure classification. Redact secrets and
private source data from logs. If the provider action is not approved or the
API key/model is absent, keep the candidate in `NEEDS_REVIEW` and fail closed;
never silently switch models or providers.

Never silently retry with a different model. If a model fails, return a typed failure and preserve the source package and prior evidence.

## Desktop mini-application requirements

Project the capability into the existing desktop experience without putting authority in the UI. The first surface should have four zones:

- left explorer: runs, source packages, templates, artifacts;
- center proof surface: preview, timeline, and evidence;
- right inspector: source, claims, model route, rights, state, unresolved items;
- bottom composer: source/intent entry and explicit `Create run` action.

The UI must show real state and evidence references. It must not claim completion from a button click. Approval must be explicit, auditable, and routed back through the owner-aligned capability seam.

## Work-unit sequence

### Unit A — source and claim safety

Implement source package normalization, manifest hashing, rights metadata, claim ledger, unsupported-claim rejection, and deterministic fixtures. Add focused tests for missing fields, contradictory facts, untrusted URLs, and redaction.

### Unit B — creative plan

Implement typed storyboard/asset-map schemas and the OpenRouter adapter. Add deterministic fallback only behind an explicit fixture flag. Add tests for schema refusal, model failure, missing API key, and no silent model switching.

### Unit C — HyperFrames composition

Generate an editable HyperFrames project from the plan. Run lint, strict check, and snapshots. Store exact command results and hashes in the evidence bundle. Add tests for timing, duplicate IDs, track indices, local media, and deliberate overflow annotations.

### Unit D — preview and approval

Add run-state transitions and an approval gate. Verify that approval is bound to the exact source hash, plan hash, composition hash, and review policy. Invalidate approval when any of those change.

### Unit E — desktop projection

Project run state, preview snapshots, artifacts, and evidence into the existing desktop surface. Keep the UI read-only until the explicit approval action; do not add a parallel authority store.

### Unit F — qualification

Run focused tests for restart, duplicate invocation, evidence continuity, provider failure, source mutation, approval invalidation, and artifact hashing. Run one live local fixture through the complete `REQUESTED` to `NEEDS_REVIEW` path. Do not claim `APPROVED`, `RENDERED`, `EXPORTED`, `DEPLOYED`, or `PRODUCTION_PROVEN` without their exact evidence.

## Acceptance criteria

The work unit is complete only when all of the following are true:

- existing Syzygy ownership contracts remain unchanged;
- no duplicate scheduler, WorkGraph, memory, evidence, or authority layer exists;
- a fixture listing produces a content-addressed source manifest and claim ledger;
- unsupported claims are rejected or marked unresolved;
- the plan is valid against a versioned schema;
- HyperFrames lint and strict check pass with zero findings for the fixture;
- requested snapshots are created and linked to the exact composition hash;
- the desktop surface displays the actual run state and evidence refs;
- missing OpenRouter configuration is explicit and fail closed;
- no external effect is attempted;
- tests are reproducible and their exact totals are recorded;
- the final report distinguishes implemented, tested, integrated, runtime-verified, and unproven boundaries.

## Final response format

Return:

1. mission vector;
2. files changed;
3. exact commands/checks and totals;
4. evidence bundle and artifact hashes;
5. failures, skips, and unknowns;
6. repository branch and HEAD;
7. integration/runtime/deployment limitations;
8. next authorized transition;
9. operator actions required.

Use `STATUS: PASS`, `STATUS: BLOCKED`, or `STATUS: INDETERMINATE` literally. End with:

```text
NEXT AUTHORIZED TRANSITION: <one bounded action>

OPERATOR AUTHORITY: <what remains locked or requires authorization>

CLAIM <= EVIDENCE
SYZYGY // INTELLIGENCE, REALIGNED.
```
