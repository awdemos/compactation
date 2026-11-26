# COMPACTATION.md - Agent Compaction Strategy Standard

Version 0.0.2 · Canonical source: https://github.com/awdemos/compactation
· Site: https://compactation.dev
· License: MIT (https://github.com/awdemos/compactation/blob/main/LICENSE) -
  copy this file into your repo, modify it, and ship it under your own terms;
  the MIT license applies to the template text.

## What this file is

This is an open-source standard for assisting agents in managing their
compactation strategy with the model(s) they are using. It is a repo-declared
contract, in the spirit of `AGENTS.md` / `CLAUDE.md`, between a repository and
any coding agent (AI or human) that works on it.

It governs one thing: the lifecycle of evidence when context is limited. An
agent captures raw records, derives compact projections for active context,
retains the originals, and restores verbatim evidence when a decision or a
report needs it. Provider-level context summarization is an external event, not
a compaction operation under this standard.

The active context is a cache. The record is the store. An agent must not
manage its own memory by rewriting strings in context and calling the result
evidence. A compact view is a derived artifact with references, coverage, and
declared losses, never a replacement for the bytes it came from.

Drop this file in a repository root (alongside `AGENTS.md` / `CLAUDE.md`).
Agents that support the convention pick it up automatically. Modify only the
`## Repo-specific rules` section for your project. The protocol, operations,
and model-strategy rules below are the portable standard and must not be
weakened. You may add rules, never remove the core seven.

## Vocabulary

| Term | Meaning |
|------|---------|
| Record | One immutable unit of captured evidence, stored as bytes. |
| Store | An append-only, content-addressed collection of records. |
| Record ID | The SHA-256 hex digest of a record's exact bytes. Agents do not invent IDs. |
| Projection | A compact, derived view of selected records with source references. |
| Reference | A record ID plus its hash, the role it played, and the byte span used. |
| Coverage | An accounting of captured bytes versus referenced and declared-omitted bytes. |
| Loss declaration | A named policy, a reason, the affected record IDs, and the bytes omitted. |
| Rehydration | Restoring verbatim record bytes from the store by ID. |
| Claim | A statement in a decision or report that must cite rehydrated records. |

## The protocol

When asked to compact, summarize, or manage context mid-task, or when a repo
declares this file and the work is non-trivial, the agent MUST:

1. **Capture before compacting.** Capture every source that may inform a later
   decision or report as an immutable, content-addressed record before any
   projection is derived. The store is append-only: no deletion, no overwrite,
   no rewrite of captured bytes. A record ID is derived from its bytes, never
   chosen by the agent.
2. **Project, do not rewrite.** Treat active context as a cache. Derive a
   projection with source references, a coverage map, and a loss declaration.
   Never promote a self-written summary to the status of evidence. If a fact
   matters, it carries the ID of the record it came from.
3. **No silent loss.** Every exclusion is attributable to a declared policy:
   deduplication, bounds, redaction, or relevance, with a reason and the
   affected record IDs. Anything that cannot be classified is RETAINED, not
   quietly dropped. The projection states what was omitted and why.
4. **Rehydrate before deciding or reporting.** Before a bug fix, a gate
   decision, a model switch, or a final report, restore the referenced records
   verbatim by ID and cite those IDs in the work. A claim backed only by a
   summary is UNVERIFIED, not a finding, not a conclusion.
5. **Verify before use.** Recompute the hash of every referenced record and
   check that references resolve and coverage arithmetic balances. On mismatch,
   invalidate the projection, re-derive from the store, and record an integrity
   incident. Never silently repair a projection.
6. **Budget and exit explicitly.** Compact at logical boundaries or on measured
   pressure, using a named token estimator. Exit on green (integrity, coverage,
   and references all sound), on an enforced budget, or on stall (the same
   integrity or coverage failure twice). Escalate a stall to the human. No
   fixed retry count is a substitute for these exits.
7. **Report with provenance and honesty.** The final report includes an
   evidence ledger (record IDs, hashes, what was rehydrated), the token estimate
   with its estimator named, what was omitted and why, and the validation status
   of any performance claim. Savings are reported as estimates, never as
   measured guarantees unless a controlled measurement exists.

## Operations contract

An implementation, whether a tool or a runtime, MUST provide these operations
with these meanings. It may add operations, not weaken these.

| Operation | Required behavior |
|-----------|-------------------|
| `init` | Create the store structure. Refuse to destroy an existing store. |
| `capture` | Read bytes, compute the content hash, store verbatim bytes, append an immutable ledger event. Idempotent for identical bytes. |
| `project` | Apply a declared policy to produce a compact view with references, coverage, omissions, redactions, and a named estimator. It must fail closed on unresolved references. |
| `retrieve` | Restore exact bytes by ID after hash verification. A hash mismatch is an error, never a warning. |
| `verify` | Recheck object hashes, projection integrity, reference resolution, and coverage arithmetic. Re-derive the core from stored bytes and the recorded policy so a hand-edited projection cannot pass. Emit a structured verdict. |
| `report` | Validate that every claim cites records present in the projection, rehydrate them, and render a report with the evidence ledger. Uncited claims become UNVERIFIED. |
| `ledger` | Show the append-only event sequence. Earlier entries must remain a prefix of later ones. |

## Model strategy

This standard assists the agent with the model or models it is actually using.
It does not assume a single model or a stable context window.

- Declare the active model family, context budget, and estimator in every
  projection core as `model`, `context_budget`, and `estimator`. Set
  `budget_enforced` to true only when a runtime actually enforces the budget.
  A projection made for one model is not silently reused for another.
- A provider compaction event is recorded as context state, not treated as a
  successful evidence operation. The store survives it unchanged.
- On a model switch, re-derive projections for the new model and re-verify
  references. Do not assume a summary written for model A is faithful for B.
- Log which model produced each projection. A different model family producing
  the verification pass is preferred where available; if unavailable, record
  the limitation.
- If the runtime cannot enforce a budget, label it advisory and reduce the
  autonomy claimed for the run.

## Performance expectation

Early work suggests an expected improvement of roughly **37 percent** in
session-management success relative to an unmanaged baseline. This is an
expectation from an initial trial, not a measured result. It is **UNVALIDATED**
and requires more data. Do not present it as proven, do not use it to justify
skipping verification, and do not drop evidence to chase the number. The
experiment that would validate or refute it is specified in
`docs/VALIDATION.md`.

## Output format

A compaction record and a report use this shape. Keep the field names stable.

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

## Runtime boundary

`COMPACTATION.md` and its installed skill instruct the current agent. They are
not a store, a scheduler, a budget enforcer, or a kill switch. An external
runtime or tool must supply any claimed capability among:

- Durable, append-only storage across processes and restarts.
- Content hashing and atomic writes.
- Deterministic projection and redaction policy enforcement. External-file
  writers must canonicalize output paths and refuse targets inside the store
  root so a projection or report can never replace captured evidence.
- Enforced token, time, or cost budgets.
- Isolated verifier contexts and execution logs.
- A documented pause or kill switch.

If a mechanism is missing, disclose it and reduce the autonomy claimed. An
advisory budget is not an enforced budget. The reference implementation in
`tools/compactation.py` supplies the storage, hashing, projection, retrieval,
verification, and reporting operations; budgets and triggers remain runtime
concerns.

## Repo-specific rules

<!-- Edit everything below this line for your project. -->

This is the canonical repository: an open-source standard, an installable
skill, a reference CLI, and a static site. Every adopter MUST fill this section
with checkable rules derived from their own code, tests, and docs.

- Priority invariants that must never regress: the seven protocol rules, the
  operations contract, the model-strategy rules, content-addressed IDs, the
  append-only ledger, the quickstart curl command, and the UNVALIDATED status
  of the 37 percent expectation.
- Known weak spots that always get a second pass: the output-format example
  (every agent copies it), the coverage arithmetic, the redaction patterns
  (a missed secret is a real leak), and any claim on the site that could be
  read as a measured performance guarantee.
- Extra lenses: `provenance` lens - every user-facing factual claim must map to
  `COMPACTATION.md`, `docs/TRACEABILITY.md`, or `docs/VALIDATION.md`; `web`
  lens - HTML parses, meta/OG tags match the site claims, and no em-dashes
  appear in user-facing copy; `tool` lens - `python3 -m unittest discover -s tests`
  passes and the demo reproduces capture, project, retrieve, and report.
- Review roles: R = `reviewer` subagent, C = `challenger` subagent under
  `ADVERSARIAL_REVIEW.md`; available model families are recorded in the report.
  Escalation authority: the NCO of record named in `README.md`.
- Commands the reviewer must run before reporting: execute the quickstart curl
  command and confirm the fetched file parses; run the unit tests; run
  `python3 tools/compactation.py --help`; confirm `index.html` and
  `public/index.html` are byte-identical; for site changes, run
  `npx wrangler deploy --dry-run` (never a live deploy during review).
