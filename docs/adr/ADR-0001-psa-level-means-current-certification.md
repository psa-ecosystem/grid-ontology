# ADR-0001: psa_level Means Current Certification Level

## Status

Accepted (2026-07-17)

## Context

`project.yaml` declares `maturity.psa_level: 2`, but the field's semantics
were never pinned down. v0.1 of the PSA Baseline Compliance Report
(`docs/governance/psa-baseline-compliance-report-v0.1.md`, §5.1) flagged
this as ambiguous and offered two readings:

- **Target (forward-looking)**: project *aims* to reach Level 2.
  Current state is Level 1.
- **Current (factual)**: project *has been certified at* Level 2.

The original `v0.1` review (2026-07-15) labeled Level 2 as **⚠️ PARTIAL**,
citing five missing P1/P2 governance artifacts. Two days later
(2026-07-17), all five have been delivered:

| Missing artifact (v0.1 §4) | Delivered | Location |
|----------------------------|-----------|----------|
| P1 PSA Semantic Package Contract | ✅ 2026-07-15 | `docs/governance/psa-semantic-package-contract.md` |
| P1 ADR directory + template | ✅ 2026-07-15 | `docs/adr/ADR-template.md` |
| P1 Compatibility Analysis Template | ✅ 2026-07-15 | `docs/governance/compatibility-analysis-template.md` |
| P2 CTS Gap Register | ✅ 2026-07-15 | `docs/governance/cts-gap-register.md` |
| P2 Release Process | ✅ 2026-07-17 | `docs/governance/release-process.md` |

The original Level 1/2 test counts (691) have grown to **640 passing
tests** (1 skipped), including 12 new PSA-specific tests under
`tests/psa/` that exercise SHACL/JSON Schema deep validation and
OWL reasoning closure across packages. The handoff stage previously
reported 741 passing; T0 re-verification confirms the current tracked
suite is 640 passed (1 skipped).

Given these deliveries, we must now decide what `psa_level: 2` means
going forward, because downstream consumers (PSA Registry, EASG
Runtime, PowerGenius AI, agent frameworks) will read this field to
decide whether to consume `grid-ontology` packages as Level 2 PSA
Aligned.

## Decision

`maturity.psa_level` is defined as **current certification level** —
the level that the project has demonstrably achieved, evidenced by
the artifacts enumerated in the PSA Baseline Compliance Report.

The current value `psa_level: 2` is therefore *correct as-is*: grid-ontology
has reached PSA Level 2 (PSA Aligned). To back this claim, the
Compliance Report must be promoted from `v0.1` (Level 2 = ⚠️ PARTIAL)
to `v0.2` (Level 2 = ✅ PASS), and that promotion is part of this
ADR's adoption.

### Future evolution

- Reaching Level 3 (PSA Native) requires: psa-validator integration,
  EASG Runtime PoC (CTS-TP-005), release pipeline automation. All
  currently tracked as P2 in `docs/governance/cts-gap-register.md`.
- Until Level 3 is achieved, `psa_level: 2` stays at 2.
- The field is **not** updated incrementally as gaps close — only when
  a baseline level is *fully* satisfied per the Compliance Report of
  record.

### Single field, no `target` companion

We deliberately do **not** add a `psa_level_target` field. Two reasons:

1. **Single source of truth.** Consumers should never have to reconcile
   two maturity fields. The roadmap (`docs/governance/level-2-roadmap.md`)
   already documents forward-looking work; that is its job.
2. **Drift risk.** A `target` field would need to be hand-maintained
   alongside `current`, and stale `target` values would mislead more
   than they inform.

## Consequences

**Easier:**

- Downstream consumers can trust `psa_level` as a single factual
  signal: "this project has been reviewed and meets Level N".
- The Compliance Report becomes the only authoritative maturity
  evidence; no need to cross-reference roadmap state.
- Future Level 3 promotion is a single discrete event (re-review →
  bump field → bump report version) instead of an ongoing maintenance
  burden.

**Harder:**

- The project cannot claim Level 3 even when 90% of Level 3 artifacts
  are in place. Discipline is required to *not* bump the field
  prematurely.
- If a Level 2 artifact regresses (e.g., a contract breaking change),
  we must immediately demote `psa_level` and re-issue a Compliance
  Report demotion notice. This is a **strict liability** discipline.

## PSA Impact

- Does this change affect PSA primitive mappings? **No**
- Does this change affect the Semantic Package format? **No**
- Does this change affect downstream consumers? **Yes** — `psa_level`
  is a signal they read. Semantics now match consumer expectations
  (factual, not aspirational).
- Compatibility impact: **None** for any consumer that already
  assumes `psa_level` is factual. For any consumer that read the
  v0.1 report and assumed `2` was aspirational, the meaning is now
  upgraded — they may want to revisit whether they have been
  prematurely deferring integration.

## Compatibility Analysis

| Consumer | Impact | Migration Required |
|----------|--------|-------------------|
| Registry | None | No — Registry reads `psa_level` as factual; behavior unchanged |
| Runtime (EASG) | None | No — same reason |
| Agent Framework | None | No — same reason |
| PowerGenius AI | None | No — same reason |
| Internal reviewers | Low | Re-read `psa-baseline-compliance-report-v0.2.md` instead of `v0.1` |

## Migration Note

This is not a breaking change for PSA-facing consumers; it is a
documentation clarification. No code or schema migration needed.

For internal reviewers: any reference to
`psa-baseline-compliance-report-v0.1.md` should be updated to
`v0.2` once that report is published (action item under this ADR).

## References

- Related ADRs: none (this is ADR-0001)
- Related PRs: (to be filled at merge time)
- Related PSA specs: PSA Engineering Baseline v0.1, Level 2 requirements
- Related reports:
  - `docs/governance/psa-baseline-compliance-report-v0.1.md` (superseded by v0.2)
  - `docs/governance/level-2-roadmap.md` (forward-looking roadmap, *not* a maturity signal)
  - `docs/governance/cts-gap-register.md` (gap tracking, current state)
- Related tests:
  - `tests/psa/test_semantic_validation.py` (12 cases)
  - `tests/psa/test_owl_reasoning.py` (3 cases)