# Compactation: Agent Compaction Strategy Standard

**Version:** 0.0.2
**Status:** open-source standard, v0.0.2 follow-up release
**Companion:** `COMPACTATION.md` in the repo root is the agent-facing contract
derived from this document.

---

## 1. Overview

This document defines an open-source standard for assisting agents in managing
their compactation strategy with the model or models they are using. It is not
a claim that models become smarter. It is a rule set for the evidence lifecycle
when context is scarce.

The failure that motivated it is concrete. On 2026-11-25 an agent compacted
noisy logs mid-task, reducing estimated tokens by roughly 37 percent, discarded
the originals, fixed the bug, and then tried to pull the compacted logs back to
write the full report. The saving was real; the evidence chain was not. The
report could not cite verbatim lines it no longer had.

In one sentence: **an agent may compact its active context, but it must never
destroy the record, and every consequential claim must be rehydrated from that
record before it is used.**

The standard distinguishes two things that are often conflated:

- Provider compaction: the model runtime summarizes or truncates its own
  context window. This is an external event the agent observes and records.
- Evidence compactation: the agent's own operation of deriving a compact,
  referenced projection from immutable records. This is what the standard
  governs.

## 2. Goals and non-goals

### Goals

- Let an agent reduce active-context cost without losing recoverable evidence.
- Make omissions explicit, named, attributable, and auditable.
- Keep a model switch or a provider compaction from breaking continuity.
- Make every consequential claim traceable to exact bytes.
- Report performance as an estimate until a controlled study says otherwise.

### Non-goals

- Replacing a model's tokenizer or the runtime's context management.
- Proving that the expected ~37 percent improvement is real. It is unvalidated.
- Enforcing budgets, triggers, or kill switches from Markdown alone.
- Storing secrets without an explicit reason and redaction policy.

## 3. Core concepts

### 3.1 Record and store

A record is one immutable unit of evidence, stored as bytes. Its ID is the
SHA-256 of those bytes, so the agent cannot choose an ID that hides a change.
The store is append-only: earlier ledger entries remain a prefix of later ones,
and objects are never overwritten. Identical bytes map to the same record.

### 3.2 Projection

A projection is a derived artifact, not a memory. It contains excerpts, source
references (ID, hash, role, byte span), a coverage map, omission declarations,
redaction counts, and a named token estimator. Its own ID is a hash of its core,
so a stale or hand-edited projection can be detected.

### 3.3 Coverage

Coverage is an accounting identity, not a vibe:

```text
captured bytes = projected excerpt bytes + all declared omitted bytes
```

Declared omissions come from named policies: `dedupe`, `bounds`,
`total_bounds`, `redaction`, `decode`, `drop_kinds`, and `integrity`. A
projection that cannot balance is not green, regardless of how small it is.

### 3.4 Rehydration and claims

Rehydration restores verbatim bytes by ID after hash verification. A claim in a
decision or report must cite at least one rehydrated record. Without one it is
labeled UNVERIFIED, never asserted. This is the rule that fixes yesterday's
failure directly.

## 4. The seven rules and why they exist

| Rule | Failure it prevents |
|------|---------------------|
| Capture before compacting | A summary that cannot be checked against what it summarized. |
| Project, do not rewrite | The agent treating its own context edit as authoritative evidence. |
| No silent loss | Omitted evidence being mistaken for evidence that never existed. |
| Rehydrate before deciding or reporting | A bug fix or report driven by a lossy paraphrase. |
| Verify before use | A corrupted or stale projection silently poisoning later steps. |
| Budget and exit explicitly | Unbounded rewrites and retry counts that cannot detect a stall. |
| Report with provenance and honesty | Unfalsifiable reports and performance claims presented as measured. |

The rules are a stable API. Repos may add rules and lenses but may not remove
these seven.

## 5. Operations

The reference CLI implements the operations contract in `COMPACTATION.md`:

```text
capture -> ledger (append-only) -> project -> verify -> retrieve -> report
                                       |                    ^
                                       +-- invalidate ------+
```

- `capture` refuses secret-like patterns unless given an explicit reason.
- `project` applies a JSON policy and fails closed on unresolved references.
- `verify` rechecks object hashes, projection identity, excerpts, and coverage.
- `retrieve` refuses to return bytes that fail hash verification.
- `report` turns claims into cited evidence or UNVERIFIED entries.

Atomic writes and file locks make concurrent capture safe. Sharded object paths
keep large stores usable. There are no third-party dependencies.

## 6. Model strategy

The standard is explicitly multi-model. A projection records the model family
that produced it, the estimator, and the policy. A provider compaction is
logged as context state, not mistaken for a successful evidence operation. On a
model switch, projections are re-derived and references re-verified; a summary
written for model A is not assumed faithful for model B. An independent
verifier from a different model family is preferred where available, and its
absence is recorded.

## 7. Performance expectation

Current expectation: agents using the standard will see roughly **37 percent
better-than-average session-management success** than an unmanaged baseline.
This comes from an initial trial, not a controlled study. It is **UNVALIDATED**.
The site, README, guide, and skill all say so. `docs/VALIDATION.md` defines the
study that would validate or refute it. Until then the number is a hypothesis,
and no implementation may drop evidence to improve it.

## 8. Runtime boundary

The standard and skill instruct an agent. Durable storage, hashing, atomic
writes, enforced budgets, triggers, isolated verifiers, and kill switches are
external capabilities. The reference CLI supplies storage, hashing, projection,
retrieval, verification, and reporting. Budgets and triggers remain runtime
concerns and must be disclosed as missing when absent.

## 9. Anti-patterns

- Compacting first and capturing later.
- Deleting originals after a successful projection.
- Rewriting context strings and calling the rewrite evidence.
- Silent truncation or redaction with no policy name or byte accounting.
- Reporting from a projection without rehydrating cited records.
- Treating model confidence or "no errors" as verification.
- Assuming a projection made for one model works for another.
- Quoting the 37 percent expectation as a measured result.

## 10. Accepted risks

These are known limitations of the reference implementation, not unresolved
CRITICAL findings. They are recorded so operators can decide whether to add
external controls.

- **Ledger cost grows with history.** `Store.events()` parses the whole ledger
  for each command (O(n) per call; O(N²) bytes re-read across N sequential
  captures). Object writes are dominated by `fsync`. Correctness is unaffected;
  a larger deployment should add an index or a bounded tail read.
- **No external ledger anchor.** The ledger is append-only with per-record
  content hashes but carries no signature or external notarization. A party with
  write access to the store can rewrite a coherent prefix. Existing projections
  retain verbatim bytes and `verify` re-derives from the store, so a rewrite
  that changes captured bytes invalidates them; a rewrite preserving every byte
  has no observable effect. Full tamper-evidence needs an external anchor or
  signature, left for a future version.
- **Object-path symlinks.** Object paths are content-addressed and every read is
  hash-verified, but the reference CLI does not reject symlinks inside the
  store's `objects/` tree. Output paths are guarded against symlink escapes.
- **`--out` TOCTOU.** Output paths are resolved and checked before an atomic
  replace. A process able to mutate the store between the check and the replace
  can already write the store directly.
- **Secret detection is heuristic.** Patterns cover common credential formats,
  assignments, and text encodings but cannot prove arbitrary bytes are
  secret-free. `--allow-secrets` with a reason is the explicit escape hatch, and
  metadata that trips a pattern is redacted.
- **Estimates stay estimates.** `utf8_bytes_over_4` is not a tokenizer; savings
  percentages are estimates and the 37 percent expectation is UNVALIDATED.

## 11. Open questions for v0.2

- Reference runtime for enforced budgets, triggers, and kill switches.
- Cross-model fidelity measurement for projections.
- Audit log format and retention policy for integrity incidents.
- Whether redaction policies should be machine-verifiable against a secret scanner.
- Controlled measurement of session success against an unmanaged baseline.

## 12. Companion documents

- `COMPACTATION.md`: the agent-facing contract.
- `SKILL.md` in `skill/compactation/`: the installable skill.
- `docs/TRACEABILITY.md`: source-to-implementation matrix.
- `docs/VALIDATION.md`: experiment plan for the 37 percent expectation.
- `CHANGELOG.md`: version history and release checksums.
