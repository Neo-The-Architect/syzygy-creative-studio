# Syzygy Creative Studio

Creative Fabric is the internal source-to-artifact engine inside Syzygy Creative Studio.

## Native creative-automation capability and desktop mini-application seam

### Status

This is an architecture candidate derived from the current Creative Fabric blueprint, the tested local property pipeline, the HyperFrames documentation, and the existing Syzygy/Pi/Codex Box ownership model. It is not yet integrated into a Syzygy checkout.

### Product thesis

Creative Fabric is a repeatable cognitive automation workflow that turns an approved source package into inspectable creative artifacts:

```text
real estate listing | engineering session | product brief | research | future source
  -> source package
  -> evidence and intent extraction
  -> creative plan
  -> model/provider selection
  -> HyperFrames composition or another output adapter
  -> preview and review
  -> approved video / website / app / presentation / export bundle
```

The platform is not “a video generator.” It is a source-to-artifact compiler with a common creative plan and multiple output targets.

### What HyperFrames contributes

HyperFrames is an open-source HTML-to-video framework. Its important architectural properties are:

- the editable project folder is the source of truth;
- HTML, CSS, JavaScript, media, and timing remain inspectable;
- compositions are finite and seekable;
- timed clips use explicit data attributes;
- the same project can be operated by an agent, Studio, CLI, SDK, or Player;
- exact-frame rendering is more reliable than depending on live playback;
- variables allow approved content to change without rebuilding the layout;
- the smallest integration surface can be CLI, SDK, Player, or rendering infrastructure.

That makes HyperFrames a strong **creative execution and preview surface**, not a replacement for Syzygy authority, mission state, or evidence ownership. See the [HyperFrames introduction](https://hyperframes.heygen.com/introduction), [project model](https://hyperframes.heygen.com/concepts), and [developer integration guidance](https://hyperframes.heygen.com/developers).

## Syzygy ownership mapping

| Concern | Existing owner | Creative Fabric relationship |
|---|---|---|
| Human intent and conversation | Pi cognitive plane / Stella | Receives a typed creative request |
| Mission and durable work state | Mission OS / WorkGraph | Owns the Creative Fabric WorkUnit |
| Capability admission and evidence | Foundation Zero | Admits bounded source, model, filesystem, and render capabilities |
| Provider/model routing | Existing provider/capability layer | Creative Fabric requests a bounded OpenRouter/image/video capability |
| Creative source package | Creative Fabric | Owns property facts, source media, claim ledger, brand variables, and rights metadata |
| Composition and preview | HyperFrames project/Studio/CLI | Owns editable HTML compositions and local render checks |
| Artifact receipt | Foundation Zero evidence / EventLedger | Receives hashes, checks, render metadata, and output locations |
| Desktop projection | Codex Box / Studio Presence | Shows run state, live proof, files, preview, and approvals |
| External publishing | Official channel adapter | Future capability, disabled by default |

### Non-negotiable boundary

Creative Fabric must not create a second Mission OS, WorkGraph, scheduler, memory store, evidence ledger, or release authority. It is a capability package plus a projection surface.

## Native function contract

The first Syzygy-native function should be a bounded capability, not a free-form agent:

```text
creative.fabric.run@1.0.0

Input:
  source_package_ref
  creative_intent
  output_targets[]
  brand_profile_ref
  model_policy_ref
  media_rights_ref
  review_policy_ref

Output:
  run_id
  status
  source_manifest_ref
  plan_ref
  composition_refs[]
  artifact_refs[]
  evidence_bundle_ref
  unresolved[]
  external_effects
```

Suggested sub-capabilities:

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

Each sub-capability should have typed input/output schemas, effect class, source identity, model route, timeout, redaction policy, evidence requirements, and failure taxonomy.

## Run state machine

```text
REQUESTED
  -> ADMITTED
  -> SOURCE_READY
  -> PLAN_READY
  -> COMPOSITION_READY
  -> CHECKED
  -> PREVIEW_READY
  -> NEEDS_REVIEW
  -> APPROVED
  -> RENDERED
  -> EXPORTED
```

Future external states remain separate:

```text
EXPORTED -> PUBLISH_PROPOSED -> PUBLISH_ADMITTED -> PUBLISHED_VERIFIED
```

An HTTP success, provider receipt, or generated file must never jump directly to `PUBLISHED_VERIFIED`.

## Request and evidence sequence

```text
Pi intent
  -> ContextPacket / MissionWorkUnit
  -> Foundation Zero capability admission
  -> Creative Fabric source package
  -> local redaction and claim/evidence ledger
  -> OpenRouter structured plan/copy request
  -> HyperFrames composition write
  -> hyperframes check / snapshots / preview
  -> human approval
  -> render and artifact hash
  -> EvidenceReceipt / EventLedger projection
  -> Codex Box / Studio Presence projection
```

The renderer receives only the admitted source package and plan. It does not decide authority, publish messages, modify repositories, or contact third parties.

## Desktop mini-application UX

The desktop surface should be a focused Studio Presence extension with four zones:

1. **Left explorer** — Creative runs, source packages, templates, and recent artifacts.
2. **Center proof surface** — current HyperFrames preview, storyboard, timeline, or generated artifact; the agent visibly shows what it is doing.
3. **Right inspector** — source facts, claim/evidence links, model/provider route, media rights, checks, and unresolved items.
4. **Bottom composer** — natural-language creative intent with explicit output chips such as `video`, `website`, `presentation`, `app`, and `bundle`.

The primary action is “Create a creative run.” Supporting actions are “Inspect evidence” and “Open preview.” Do not lead with provider shopping or a dashboard full of metrics.

### Desktop states

- `No active run` — select a source or describe a new one.
- `Preparing source` — show extraction and redaction evidence.
- `Planning` — show storyboard beats and model route.
- `Composing` — show file changes and HyperFrames scene progress.
- `Checked` — show zero/known findings and snapshot strip.
- `Needs review` — surface the exact edits or approvals required.
- `Approved` — show the approved source hash and output targets.
- `Rendered` — show artifact links and receipt evidence.
- `Blocked` — show the smallest missing prerequisite and preserve the run.

## Provider policy

OpenRouter is the reasoning plane, not the authority plane. Candidate creation
must remain local; a separate explicit provider-approval action is required
before any OpenRouter transfer. The provider adapter should:

- accept an explicit model route;
- use strict structured output when supported;
- redact locally before transmission;
- send minimum-sufficient context;
- record model, provider, input hash, output hash, latency, and cost metadata;
- fail closed on malformed output or unavailable providers;
- never silently switch to an unapproved model.

Image and video generation are separate capabilities. A deterministic local HyperFrames composition must remain available even when an image/video provider is unavailable.

## Implementation phases

### Phase 0 — isolate the integration target

Select a clean Syzygy worktree and record branch/base, dirty state, current owner contracts, and test budget. The aggregate `C:\Users\Jax 16\Documents\Syzygy` directory is not itself one repository.

### Phase 1 — capability candidate outside authority

Add the Creative Fabric schemas, adapter interfaces, run-state projection, and local worker package in a dedicated worktree. Do not wire live effects.

### Phase 2 — local source and HyperFrames adapter

Bind the existing local property pipeline to a Creative Fabric source package and create HyperFrames projects with stable variables, compositions, assets, and render receipts.

### Phase 3 — Pi request seam

Accept a typed Pi intent and return a Mission/WorkUnit correlation plus a bounded Creative Fabric invocation. Pi remains the requester; Creative Fabric remains the executor candidate.

### Phase 4 — Codex Box/Studio Presence projection

Project run state, evidence, previews, and artifacts into the existing desktop experience. Do not put authority into the UI.

### Phase 5 — qualification

Run focused tests for source identity, redaction, claim binding, provider failure, HyperFrames check, preview, render, artifact hashing, restart, duplicate invocation, and approval invalidation. Keep external publishing disabled until separately qualified.

## Current proof and limitations

Already proven in the companion deliverables:

- local property source normalization;
- claim ledger generation;
- unsupported-claim rejection;
- deterministic reel and brochure rendering through Pillow and FFmpeg;
- campaign/audit manifests;
- a HyperFrames 18-second Creative Fabric composition;
- HyperFrames lint: zero findings;
- HyperFrames strict check: zero lint, runtime, layout, motion, and contrast findings;
- five requested snapshots plus an end-of-timeline snapshot visually inspected.

Not yet proven:

- integration into a selected Syzygy worktree;
- Pi invocation through a live capability bridge;
- Mission OS/WorkGraph admission for a Creative Fabric WorkUnit;
- OpenRouter live call in this environment;
- live HyperFrames render approval and final MP4 render;
- external publishing or production delivery.

## Next authorized transition

Choose one clean Syzygy target worktree for the first bounded integration unit. The safest first unit is read-only source-to-preview integration: receive a typed request, create a local Creative Fabric run, run HyperFrames checks/snapshots, and return an evidence bundle without live publishing or repository mutation beyond the chosen worktree.
