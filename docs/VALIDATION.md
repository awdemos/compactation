# Validation plan for the 37 percent expectation

**Status:** not started
**Claim under test:** agents using COMPACTATION.md achieve roughly 37 percent
better-than-average session-management success than an unmanaged baseline.

This is an expectation from one initial trial. It is not a measured result and
must not be reported as one. This document defines what would count as evidence.

## 1. Hypothesis

- **H1:** Using the standard increases session-management success rate.
- **H0:** There is no difference in session-management success rate.

The 37 percent figure is the effect size the initial trial suggests. The study
must estimate the actual effect, including the possibility that it is zero or
negative.

## 2. Definitions

A **session** is one bounded coding task with a declared goal and a deterministic
acceptance check, for example a test suite exit code plus a planned-scope diff.

**Session-management success** is a composite, declared before the run:

1. The acceptance check passes at session end.
2. The final report cites rehydrated records for every consequential claim.
3. No declared evidence source is unrecoverable from the store.
4. No UNVALIDATED performance figure is presented as measured.

A session fails if any component fails. Components are reported separately so
a token saving cannot mask a provenance failure.

## 3. Design

- Randomize sessions into control and treatment groups.
- Control: the same model, task, budget, and tool access without
  `COMPACTATION.md` or the reference CLI.
- Treatment: the same setup with the standard active and the CLI available.
- Pre-register the task set, acceptance checks, and scoring rubric before runs.
- Use at least two model families; record family and version per session.
- Use isolated checkouts or worktrees so one session cannot contaminate another.
- Score by a verifier that did not produce the work and does not see the group
  label where feasible.
- Record token use, wall time, number of compactions, omissions, integrity
  incidents, retrieval failures, and uncited claims.

## 4. Minimum sample and stopping rule

Target at least 100 completed sessions per arm before reading the primary
outcome, with a preregistered exclusion list for infrastructure failures. Stop
early only for a preregistered safety reason, such as evidence loss in the
treatment arm. Report confidence intervals, not just point estimates. Report
all exclusions.

## 5. What would change the claim

- A confidence interval excluding zero in favor of treatment would support H1.
- An interval including zero means the expectation is not established.
- An interval favoring control means the design must be revised.
- Any treatment session with unrecoverable declared evidence is counted as a
  failure regardless of token savings.

## 6. Privacy and secrets

Fixtures must use synthetic data. Real tokens, keys, and credentials must never
be captured into public fixtures, logs, changelogs, or issue reports. The CLI
refuses secret-like patterns by default; the default redaction policy is part
of the treatment, not an optional extra.

## 7. Current status

No controlled runs have been completed. The public materials therefore say
"expected" and "UNVALIDATED" wherever the 37 percent figure appears. Update this
document, the changelog, the README, the skill, and the site together when
evidence exists. A partial result in one arm is not a release-worthy claim.
