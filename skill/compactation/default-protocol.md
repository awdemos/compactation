# Bundled default compactation protocol (v0.0.x)

Use this when a repo has no `COMPACTATION.md` or has a stale copy. A current repo
file wins. This is the portable core of the open-source standard.

1. Capture raw evidence into an append-only, content-addressed store before any
   compaction. Record IDs are SHA-256 of exact bytes. Never delete or rewrite.
2. Derive a compact projection with source references, coverage, and declared
   losses. Active context is a cache, not the record.
3. Attribute every omission to a policy, a reason, and affected IDs. Retain
   what cannot be classified.
4. Rehydrate referenced records verbatim before any fix, gate, or report. An
   uncited claim is UNVERIFIED.
5. Verify hashes, references, and coverage before use. Invalidate and re-derive
   on mismatch; record the incident.
6. Exit on green, an enforced budget, or a stall (same failure twice). Escalate
   a stall to the human.
7. Report the ledger, estimator, omissions, and validation status. Mark the
   ~37 percent expectation UNVALIDATED.

## Output shape

Use the `## Output format` block in the canonical `COMPACTATION.md` verbatim.
Field names are stable; do not shorten or rename them:

```markdown
## Compactation - <scope> (<date>)

Model: <family/name> · Estimator: <name> · Policy: <name> · Status: <green|budget|stall>

Projection: <projection hash>
Coverage: <captured bytes> = <referenced bytes> + <declared omitted bytes>
Records: <id-prefix>:<role> (<bytes> bytes) ...
Omitted: <policy> - <reason> - <ids> - <bytes> bytes
Redactions: <pattern> - <count>
Token estimate: <before> -> <after> (<percent> saved, estimate only)

Rehydrated for decisions: <id-prefix> ...
Integrity: <verified|invalidated and re-derived>
UNVERIFIED: <claims without a rehydrated source, with what was attempted>

Validation status: unvalidated (see docs/VALIDATION.md)
```

The projection core also carries `model`, `context_budget`, `estimator`, and
`budget_enforced`; mark budgets advisory when no runtime enforces them.

## Runtime boundary

Storage, hashing, enforced budgets, triggers, isolation, and kill switches are
external capabilities. If missing, disclose the limitation and reduce claimed
autonomy.
