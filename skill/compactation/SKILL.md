---
name: compactation
description: Use when the user asks to compact, summarize, or manage context, logs, or evidence mid-task; when a session approaches a context budget; when evidence must survive a provider compaction or a model switch; or when a repository contains COMPACTATION.md. Applies the open-source compactation standard with a content-addressed evidence ledger and verified rehydration.
---

# Compactation

## HARD TRIGGER

Invoke this skill automatically when any of these holds:

- A session is approaching a context budget or the user asks to compact.
- Evidence or logs will be summarized and then used for a fix, a gate, or a report.
- A model switch or provider compaction could break context continuity.
- The repo contains `COMPACTATION.md`.

Single-answer questions and pure conversation are exempt.

## What this skill is

An open-source standard that assists you in managing your compactation
strategy with the model or models you are using. It instructs the current
agent. It is not a durable store, a scheduler, a budget enforcer, or a kill
switch unless an external tool supplies those capabilities.

The core move: active context is a cache, the record is the store. Never manage
memory by rewriting strings in your own context and treating the rewrite as
evidence. Capture bytes, project a compact view with references, retain the
originals, rehydrate before deciding, and report with provenance.

## Protocol

Each rule has a Why (the failure it prevents) and a Proof obligation (the
checkable invariant the output must satisfy).

### 1. Capture before compacting

Capture raw evidence as content-addressed, immutable records before deriving any
compact view. IDs are SHA-256 of exact bytes, not agent-invented labels.

Why: yesterday's failure was compacting noisy logs, discarding the originals,
then trying to write a full report from the compacted text. A projection cannot
restore bytes it never had.

Proof obligation: For every source `s`, emit `record(id, bytes, hash)` with
`id = sha256(bytes)` and `hash = sha256(bytes)`. The ledger's earlier entries
remain a prefix of later entries. No captured object is modified.

### 2. Project, do not rewrite

Derive a compact projection with source references, a coverage map, and a loss
declaration. Do not promote your own summary to evidence.

Why: a model-written summary is a hypothesis about the evidence, not the
evidence. Treating it as authoritative is how a wrong fix gets a confident report.

Proof obligation: For projection `p`, every record reference `r` satisfies
`r.id in captured_ids` and `r.hash = sha256(object(r.id))`. Coverage satisfies
`captured_bytes = referenced_bytes + sum(declared_omitted_bytes)`.

### 3. No silent loss

Attribute every exclusion to a declared policy with a reason and affected IDs.
Unclassifiable items are RETAINED.

Why: silent omission is indistinguishable from evidence that never existed.

Proof obligation: `omitted_ids + retained_ids + referenced_ids = captured_ids`
as a disjoint partition, and every element of `omitted_ids` has a non-empty
policy name and reason.

### 4. Rehydrate before deciding or reporting

Before a fix, a gate, a model switch, or a final report, restore referenced
records verbatim and cite their IDs.

Why: a bug fix driven by a summary can miss the exact line that mattered; a
report built from a summary cannot prove its claims.

Proof obligation: For every consequential claim `c`, there exists at least one
cited `id` with `retrieve(id)` returning bytes whose hash is verified. A claim
without one is labeled UNVERIFIED, not asserted.

### 5. Verify before use

Recompute hashes, resolve references, and balance coverage. On failure,
invalidate the projection, re-derive, and record an incident.

Why: a corrupted or stale projection silently poisons every later decision.

Proof obligation: `verify(p) = pass` implies all reference hashes match and
coverage balances. A mismatch implies `verify(p) = fail` and the projection is
not used for decisions until re-derived.

### 6. Budget and exit explicitly

Compact at logical boundaries or on measured pressure with a named estimator.
Exit on green, enforced budget, or stall (the same failure twice). Escalate a
stall to the human.

Why: a fixed retry count cannot distinguish slow progress from a stuck loop,
and an untracked budget turns compaction into an unbounded rewrite.

Proof obligation: Emit `(state, estimator, exit_reason)` for each compaction
step. `exit_reason` is in {green, budget, stall}. Two identical failures with no
change in state imply `exit_reason = stall`.

### 7. Report with provenance and honesty

Include the evidence ledger, estimator name, omissions, and validation status.

Why: a report without provenance is unfalsifiable and invites overclaimed
results.

Proof obligation: Every claim has either a cited rehydrated record or an
UNVERIFIED label. Any performance figure is marked UNVALIDATED unless a
controlled measurement is cited.

## Using the reference tool

The reference implementation is `tools/compactation.py` (stdlib Python). Use it
instead of hand-editing context strings:

```sh
python3 tools/compactation.py --store .compactation init
python3 tools/compactation.py --store .compactation capture --kind log --model claude-sonnet-4.6 --file noisy.log
python3 tools/compactation.py --store .compactation project --policy examples/noisy-log-policy.json --out projection.json --model claude-sonnet-4.6
python3 tools/compactation.py --store .compactation verify --projection projection.json
python3 tools/compactation.py --store .compactation retrieve --id <record-id> --out evidence.bin
python3 tools/compactation.py --store .compactation report --projection projection.json --claims claims.json --out report.md
```

If no tool is available, follow the protocol manually and disclose that
storage and hashing are session-only. Do not claim durable provenance.

## Performance honesty

The expected ~37 percent session-management improvement is an expectation from
an initial trial, not a measured result. Mark it UNVALIDATED. See
`docs/VALIDATION.md`. Never drop evidence to improve the estimate.

## Common mistakes

- Compacting first and capturing later, or discarding originals after projection.
- Rewriting context strings and calling the rewrite evidence.
- Silent truncation with no policy name, reason, or affected IDs.
- Reporting from a projection without rehydrating cited records.
- Using a corrupted or stale projection without re-verification.
- Claiming a fixed retry count is a budget or an advisory budget is enforced.
- Presenting the 37 percent expectation as a measured guarantee.
- Assuming a summary made for one model is faithful for another.

## Output

State the compactation plan before acting: the records to capture, the policy to
apply, the estimator and budget, the model in use, the verification step, and
what will be rehydrated for the final report. Then emit the compactation record
in `COMPACTATION.md`'s output format with an explicit validation status.
