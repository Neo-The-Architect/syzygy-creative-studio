# Security policy

Syzygy Creative Studio is local-first and deliberately keeps external effects
disabled in the MVP.

Please do not include API keys, private listings, client data, unredacted
repositories, personal recordings, or private infrastructure details in public
issues or pull requests.

Report security issues privately to the repository maintainer rather than
opening a public issue with exploit details. Include a minimal reproduction,
affected component, impact, and suggested containment if known.

The project does not authorize testing third-party platforms, social accounts,
or infrastructure. Provider and publishing adapters must remain opt-in and
approval-gated.

The local service binds to loopback by default. Non-loopback binding requires
the explicit `SYZYGY_CREATIVE_STUDIO_ALLOW_NON_LOOPBACK=1` opt-in and should be
paired with the required `SYZYGY_CREATIVE_STUDIO_AUTH_TOKEN` and an
operator-controlled authenticated boundary before remote use. The application
rejects non-loopback startup without the token and requires
`Authorization: Bearer <token>` for API, run, artifact, approval, render, and
export routes.
Never commit the token or include it in logs or public artifacts.
Run IDs are path-constrained, artifact requests are containment-checked, and
HTTP request bodies are capped at 2 MiB in the local MVP. Run creation also
uses bounded active-work, per-client rate, input-media, and retained-storage
ceilings; exceeding a ceiling fails closed. Operators should set deliberate
values for their hardware and retention policy rather than treating the
defaults as a production capacity guarantee.
