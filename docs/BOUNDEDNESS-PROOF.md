# Boundedness proof for the compactation skill

Version 0.0.2 · Canonical source: https://github.com/awdemos/compactation
· Site: https://compactation.dev · License: MIT

This document proves a necessity claim about
`skill/compactation/SKILL.md`: to satisfy its own proof obligations, the skill
must be bounded in three ways. It is a design proof, not an experiment. It does
not validate the roughly 37 percent session-management expectation; that figure
remains UNVALIDATED in `docs/VALIDATION.md`.

## Definitions

Let the store `S` be an append-only map from record IDs to bytes, with
`id = sha256(bytes)`. Let a projection `p` be a derived view of records in `S`
under a declared policy. Let a report contain consequential claims `C`.

Correctness `K` is the conjunction of the skill's checkable obligations
(`SKILL.md` sections 1 through 7):

- **I1 Provenance:** every consequential claim cites an `id` whose
  `retrieve(id)` returns bytes with `sha256(bytes) = id`.
- **I2a Byte conservation:** `captured_bytes = referenced_bytes + omitted_bytes`.
- **I2b ID partition:** `captured_ids = referenced_ids ∪ omitted_ids ∪
  retained_ids` as a disjoint partition at whole-record granularity, and every
  omitted ID has a policy name and reason. A partial-byte loss may list a record
  ID in both `referenced_ids` and an omission's affected IDs because the byte
  span is still cited.
- **I3 Integrity:** `verify(p) = pass` implies hashes match, references
  resolve, and coverage balances. A mismatch makes `p` unusable until it is
  re-derived.
- **I4 Honest termination:** each step emits
  `(state, estimator, exit_reason in {green, budget, stall})`. An advisory
  budget is not reported as enforced, and a projection is not silently reused
  for another model.

The three bounds are:

- **B1 Operations:** only `init`, `capture`, `project`, `retrieve`, `verify`,
  `report`, and `ledger` may change evidence state. No captured byte is edited,
  deleted, or re-authored, and no self-written summary becomes evidence.
- **B2 Budget and model:** a named estimator, a declared `model` and
  `context_budget`, an explicit exit reason for every compaction step, stall
  escalation, and re-derivation on a model switch.
- **B3 Paths and verification:** hash-verified object reads for I1 and I3, plus
  store-root confinement and guarded `--out` targets that enforce B1 at the tool
  boundary.

## Lemmas

**Lemma 1: `K` implies B1.** I1 and I2 need a fixed referent for each ID. If an
agent may edit a captured object, `retrieve(id)` returns bytes whose hash is not
`id`, so I1 fails. If it may delete or add records after `p` was derived, the
derivation identity in I3 fails: `verify` re-derives the core from the store and
no longer matches `p`. If it may promote its own summary into the store, a claim
cites an ID whose bytes were never evidence. Only B1 forbids those transitions.

**Lemma 2: `K` implies B2.** I4 requires a finite, declared decision for every
step. Without a bound and permitted exits, a sequence either runs forever or
stops without a checkable reason; both violate I4. Without a declared model and
estimator, an external runtime has no input with which to detect that a
projection made for model A is being reused under model B; the projection can
still print green because `verify` and `report` take no active-model argument.
Unbounded context also allows evidence to be dropped without a declared policy
to chase a target, which breaks I2a and I2b. Only B2 supplies the estimator, exit
set, and declared model input that an external runtime needs.

**Lemma 3: `K` implies B3.** I1 requires that `retrieve(id)` return bytes whose
hash is the ID. If object reads are not hash-verified, tampered bytes satisfy
I1's syntax but not its meaning, and `verify` cannot distinguish them. Hash
verified reads are therefore directly necessary for I1 and I3. Guarded output
paths add defense in depth: they enforce B1 at the tool boundary by preventing a
derived artifact from being written into the evidence store. A projection copied
into the store does not by itself change verification, because B1 forbids
promoting it to evidence.

## Theorem

`K` implies `B1 and B2 and B3`.

Contrapositive: remove any one bound and there is an execution that respects
the other rules but violates a proof obligation. Losing B1 destroys immutable
referents. Losing B2 destroys declared termination and the model signal an
external runtime needs. Losing hash-verified reads breaks I1 and I3. Therefore
an unbounded skill is incorrect by its own stated obligations.

## Converse and boundary

Given B1 through B3 **and** an external runtime that supplies durable storage,
hashing, enforcement, isolation, and a kill switch, the invariants are
preserved: `capture` fixes referents, `project` declares coverage, `verify`
refuses mismatches, `retrieve` hash-verifies, `report` verifies before rendering,
and explicit exits stop loops. The skill alone cannot claim those runtime
capabilities. This matches `COMPACTATION.md` section "Runtime boundary" and
`SKILL.md` section "What this skill is".

So boundedness is necessary for correctness. Sufficiency is conditional on the
runtime the skill explicitly refuses to impersonate.

## Mapping to the standard

| Invariant | Contract rule | Enforcement |
|-----------|---------------|-------------|
| I1 | Rules 1, 4, 5 | Content-addressed capture, rehydration, verification |
| I2a/I2b | Rules 2, 3 | Byte coverage and disjoint ID partition |
| I3 | Rule 5 | `verify` re-derives from store bytes and recorded policy |
| I4 | Rule 6 and model strategy | Named estimator, explicit exits, declared model for external runtime |
| B1 | Operations contract | `init`, `capture`, `project`, `retrieve`, `verify`, `report`, `ledger` |
| B2 | Rule 6 and model strategy | `context_budget`, `budget_enforced`, stall escalation |
| B3 | Runtime boundary | Hash-verified object reads; `guard_output_path()` enforces B1 at the tool boundary |

## What this does not prove

This proof says nothing about whether the standard improves session outcomes.
It does not replace the controlled comparison in `docs/VALIDATION.md`, and it
does not turn the 37 percent expectation into a measured result.

Projection schema strings are informational labels in v0.0.2: `verify` does not
gate on them, and the regression test asserts emission only. A legacy
`compactation/0.0.1` label remains verifiable when the stored bytes and recorded
policy re-derive correctly.
