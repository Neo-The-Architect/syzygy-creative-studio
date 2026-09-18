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
placed behind an operator-controlled authenticated boundary before remote use.
Run IDs are path-constrained, artifact requests are containment-checked, and
HTTP request bodies are capped at 2 MiB in the local MVP.
