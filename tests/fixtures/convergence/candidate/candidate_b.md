# Delivery Candidate: Interop Handoff Guide (Fixture, Corrected)

A frozen, identity-bound delivery document fixture. It carries delivery
content only; its identity is the SHA-256 of these exact bytes, recorded in
the fixture manifest and bound by the external records beside it.

## Install

Run the packaged installer with the pinned dependency set. For controlled
offline installs, pass the reviewed wheelhouse directory with
`--find-links`.

## Compatibility

Supports interchange format versions 1 and 2. Version 3 payloads are
rejected with a diagnostic.
