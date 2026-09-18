# Security-boundary evidence

This is a bounded manual HTTP security check for the local MVP. A formal
coordinator-backed repository security scan was unavailable in the current
desktop host, so this packet does not claim complete security coverage.

- UI `X-Content-Type-Options`: `nosniff`
- UI CSP: present
- encoded artifact traversal request: HTTP `404`
- request body over 2 MiB: HTTP `413`
- non-loopback binding: requires explicit `SYZYGY_CREATIVE_STUDIO_ALLOW_NON_LOOPBACK=1`
- external effects: `NOT_ATTEMPTED`
