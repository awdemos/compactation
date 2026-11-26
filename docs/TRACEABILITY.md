# Source-to-implementation traceability

This matrix prevents three different things from being presented as one:

- **Project rule:** a design choice made by this standard, not a measured result.
- **Implementation:** where the rule is enforced or instructed.
- **Runtime requirement:** a capability Markdown instructions cannot provide.

## Primary source

The motivating event is an operator report dated 2026-11-25: an agent compacted
noisy logs mid-task, reduced estimated tokens by roughly 37 percent, discarded
the originals, fixed the bug, then tried to reconstruct a full report from the
compacted text. No controlled measurement was run. The report supplies the
failure mode and the expectation, not evidence of benefit.

The standard is an original design. It is informed by general practice around
content-addressed storage, append-only logs, and verifiable provenance. It does
not claim endorsement by any research paper or industry body.

## Rule-to-implementation matrix

| ID | Rule | Implementation | Kind |
|----|------|----------------|------|
| R1 | Capture before compacting | `COMPACTATION.md` rule 1; `tools/compactation.py capture`; `tests/test_compactation.py` idempotence tests | Project rule plus implementation |
| R2 | Content-addressed IDs | `digest()` and `Store.put_object()`; ID validation in `retrieve` | Implementation |
| R3 | Append-only ledger | `Store.append()` with flock and fsync; prefix test | Implementation |
| R4 | Project, do not rewrite | `COMPACTATION.md` rule 2; `project` command; skill proof obligation | Project rule plus implementation |
| R5 | No silent loss | `project` omissions with named policies; coverage identity tests | Implementation |
| R6 | Rehydrate before deciding | `report` command and claim validation; skill rule 4 | Project rule plus implementation |
| R7 | Verify before use | `verify` re-derives the core from store bytes and the recorded policy; forgery, tamper, and identity tests | Implementation |
| R8 | Budget and exit | `max_chars_total` produces `exit_reason=budget`; stall classification | Mixed: enforcement requires runtime |
| R9 | Report with provenance | `report` command renders ledger, estimator, UNVERIFIED, validation status | Implementation |
| R10 | Model strategy | Model recorded in projections and reports; re-derive rule in skill | Project rule |
| R11 | Secret hygiene | `detect_secrets()` refuses capture without reason; redaction policy never mutates stored bytes | Implementation |
| R12 | Atomic durable writes | `atomic_write()` with fsync and os.replace | Implementation |
| R13 | Triggers, enforced budgets, kill switch, isolated verifier contexts | Not provided by Markdown or the CLI; `context_budget` and `budget_enforced` are advisory fields | Runtime requirement |
| R14 | Store immutability from external writers | `guard_output_path()` refuses `--out` targets inside the store for `project`, `retrieve`, and `report` | Implementation |
| R15 | Byte-accurate spans and bounded redaction | Byte-based span arithmetic; conservative regex subset in `safe_redact_pattern()` and pattern-length checks in `validate_policy()` | Implementation |
| R16 | Secret hygiene in metadata | `cmd_capture()` scans note, reason, kind, model, and source, then redacts secret-bearing metadata | Implementation |
| R17 | Verify before reporting | `cmd_report()` re-runs projection verification and refuses identity or derivation failures | Implementation |
| R18 | Bounded authority, budget, and paths | `docs/BOUNDEDNESS-PROOF.md`; skill proof obligations; runtime boundary in `COMPACTATION.md` | Design proof, not performance evidence |

## Project choices not dictated by the failure

| ID | Project rule | Reason |
|----|--------------|--------|
| P1 | Seven protocol rules are a stable API | Gives adopters a versionable contract. |
| P2 | SHA-256 of exact bytes is the only record ID | Removes agent-chosen labels that could hide rewrites. |
| P3 | Coverage is an accounting identity | Turns "we did not lose anything" into a checkable claim. |
| P4 | Token estimate is UTF-8 bytes over 4, always named | Avoids presenting a heuristic as a model tokenizer. |
| P5 | Uncited claim becomes UNVERIFIED, not an error hidden from the report | Keeps failures visible without letting them masquerade as evidence. |
| P6 | Secret-like bytes are refused by default | A public standard must not teach agents to store credentials in evidence. |
| P7 | Bounded operations, budget, and paths are necessary | The proof in `docs/BOUNDEDNESS-PROOF.md` makes each proof obligation depend on an explicit limit. |

## External and unvalidated claims

| Claim | Source | Location | Status |
|-------|--------|----------|--------|
| Roughly 37 percent better-than-average session-management success | Operator's initial trial on 2026-11-25, no control group | `README.md`, `index.html`, `COMPACTATION.md`, `docs/VALIDATION.md` | Expectation, UNVALIDATED |
| Roughly 37 percent token reduction in the initial trial | Operator report of that single session | `docs/DESIGN.md`, site copy | Anecdotal observation of one session, not a general result |
| Every merge has independent NCO signoff | Repository policy | `CONTRIBUTING.md`, site copy | Required policy, not yet observed; no PR has a signoff comment |

Every public mention of either figure pairs it with the unvalidated status. No
site copy presents the figure as a measured guarantee.

## Guide-to-tool coverage

| Contract operation | CLI command | Status |
|--------------------|-------------|--------|
| `init` | `python3 tools/compactation.py init` | Covered |
| `capture` | `capture` | Covered |
| `project` | `project` | Covered |
| `retrieve` | `retrieve` | Covered |
| `verify` | `verify` | Covered |
| `report` | `report` | Covered |
| `ledger` | `ledger` | Covered |
| Enforced budgets | none | Explicitly external |
| Triggers and kill switch | none | Explicitly external |
| Isolated verifier context | independent process or different model family outside the CLI | Explicitly external |

## Verification boundary

The tests prove that the reference implementation follows its own contract:
hashes verify, ledgers append, coverage balances, and uncited claims are
labeled. They do not prove improved session outcomes. Measuring benefit requires
the controlled comparison in `docs/VALIDATION.md`. Until that exists, describe
the standard as a testable control design, not a proven productivity method. The
separate proof in `docs/BOUNDEDNESS-PROOF.md` establishes that bounded authority,
budget, and paths are necessary for the skill's own invariants; it is a design
proof, not an outcome measurement.

## Adversarial review reconciliation (second loop)

The second loop ran R=Flint and C=Seaglass against the frozen tree, then an
independent re-review of the fix diff. No CRITICAL or unresolved HIGH
`DISAGREE_CONCERN` remained, so no NCO escalation was required. Every verdict
was reconciled before the `v0.0.1` squash.

| Finding | Verdict | Disposition |
|---------|---------|-------------|
| AR2-R-001 (secret pattern over-match) | MODIFY to MEDIUM | Fixed: context-scoped AWS pattern plus shape check; placeholder lookahead; broader key names and quoted keys. Regression tests added. |
| AR2-R-002 (signed tag absent) | MODIFY to MEDIUM | Publication step, not a code defect; completed in the release sequence below. |
| AR2-R-003 (`--store` after subcommand) | MODIFY, scope widened | Fixed: subparsers accept `--store` via `argparse.SUPPRESS`; docs use the global form. Test added. |
| AR2-R-004 (coherent ledger rewrite) | ACCEPT MEDIUM | Accepted risk: no external anchor; retained bytes and re-derivation limit the impact. Documented in `docs/DESIGN.md` §10. |
| AR2-R-005 (stale schema string) | MODIFY to LOW | Fixed string and status wording. |
| AR2-R-006 (site count drift) | ACCEPT LOW | Fixed to the then-current 50 tests after regressions; v0.0.2 adds two compatibility tests, so the site now reports 52. |
| C-MISSED-01/02 (key variants, quoted keys) | Confirmed MEDIUM | Fixed with AR2-R-001. |
| C-MISSED-03/04 (kind, model, reason unscanned) | Confirmed | Fixed: all metadata fields scanned; secret-bearing reason, kind, and model redacted. |
| C-MISSED-05 (`event.bytes` unchecked) | Confirmed | Fixed: byte-count mismatch becomes `unresolved` and stalls the projection. |
| C-MISSED-06 (non-object ledger event) | Confirmed | Fixed: structured `CompactationError`; `AttributeError` handled in `main`; `verify` emits a structured verdict. |
| C-MISSED-07 (hash marked before total cap) | Confirmed | Fixed: a skipped record is not a dedupe ancestor. |
| C-MISSED-08 (`bytes(N)` allocation in `estimate`) | Confirmed | Fixed with `token_count_estimate()`. |
| C-MISSED-09 (ReDoS guard incomplete) | Confirmed HIGH | Fixed: `safe_redact_pattern()` counts `*`, `+`, `?`, and bounded repeats, rejecting nested and repeated quantifiers; a follow-up re-review found and fixed an optional-quantifier bypass. |
| C-MISSED-10 (PGP private-key header) | Confirmed | Covered by the widened private-key pattern. |
| C-MISSED-11 (bool accepted as int) | Confirmed | Fixed in `validate_policy()`. |
| C-MISSED-12 (report not verify-first) | Confirmed | Fixed: report re-verifies and refuses identity or derivation failures. |
| C-MISSED-14 (object-path symlinks) | Accepted LOW | Content-addressed, hash-verified reads; output paths are guarded. Documented in `docs/DESIGN.md` §10. |
| Re-review NEW-9 (metadata file scan) | Confirmed LOW | Fixed: `make_release_metadata.py` uses `git ls-files` and excludes ignored paths. |
| R-011 (ledger parse cost) | Accept LOW | O(n) per command, O(N²) across N captures; documented in `docs/DESIGN.md` §10. |

The independent re-review confirmed the original CRITICAL/HIGH fixes
(store-internal `--out` guard, re-derived `verify`, coverage accounting,
canonical report, version reset, governance wording, context budget, protocol
shape). Its two HIGH objections, over-refusing secret detection and ReDoS, are
the C-MISSED-01/02 and C-MISSED-09 rows above.

## Adversarial review reconciliation (third loop, v0.0.2)

The third loop reviewed the staged v0.0.2 candidate: R = Basalt, C = Quartz.
Both instances ran on the same model family (`opencode/big-pickle`); the
preferred distinct-family independence was not available, so that limitation is
recorded rather than implied away. R and C exchanged verdicts until stabilized.
No CRITICAL or HIGH runtime defect was found and all mandated commands passed,
but R sustained NO-GO until the proof and hygiene items below were fixed. No
unresolved HIGH or CRITICAL `DISAGREE_CONCERN` remained, so no NCO escalation
was required.

| Finding | C verdict / R response | Disposition |
|---------|------------------------|-------------|
| f-proof-i2 (byte vs ID conservation) | ACCEPT MEDIUM | Fixed: I2 is split into I2a byte conservation and I2b disjoint ID partition. |
| f-proof-model-binding | MODIFY to LOW; R accepted | Fixed: Lemma 2 and the mapping table now say the declared model is an input for an external runtime, not a tool-enforced binding. |
| f-proof-b3-mechanism | ACCEPT MEDIUM | Fixed: Lemma 3 ties I1/I3 necessity to hash-verified reads and describes `guard_output_path()` as B1 defense in depth. |
| f-schema-not-enforced | MODIFY to LOW; R accepted | Fixed: the proof states that projection schema labels are informational and that the test asserts emission only. |
| f-design-version | ACCEPT LOW | Fixed: `docs/DESIGN.md` version line is 0.0.2. |
| f-quickstart-404 | ACCEPT LOW | Fixed: `docs/DEPLOYMENT.md` and the publish sequence push and verify the signed tag before deploying. |
| f-legacy-test-coverage | ACCEPT LOW | Fixed: the legacy-schema test now asserts `verify` and `report` as well as `project`. |
| C-MISSED-01 (append attributed to I2) | ACCEPT LOW; `DISAGREE_EVIDENCE` sustained | Fixed: post-projection appends are attributed to I3 derivation identity, not I2 byte balance. |
| C-MISSED-02 (deploy tag gate) | ACCEPT LOW | Fixed alongside f-quickstart-404. |

An independent re-review of this fix batch is required before publication.
