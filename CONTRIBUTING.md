# Contributing to COMPACTATION.md

A standard about evidence discipline owes its contributors the same discipline.
Three hard requirements, none negotiable:

## 1. Issues before PRs

Every PR must reference an issue that was opened and accepted first. An
unsolicited PR with no linked issue will be closed without review. Use the issue
to argue scope before anyone writes code; use the PR to review what was actually
written. Drive-by fixes for obvious typos may open an issue and PR
simultaneously, but the issue link is still mandatory.

## 2. Verified commits

All commits on `main` must be cryptographically verified:

- Sign commits with **GPG** (`git commit -S`) or **SSH**
  (`git commit -S --gpg-format=ssh`), with the signing key registered on the
  contributor's GitHub account.
- Verified signatures are required on `main` by this policy. Platform
  enforcement (branch protection or rulesets) is configured separately by the
  operator; its absence does not relax this requirement.
- Agents and humans are held to the same bar: an agent-authored commit is made
  under the human operator's identity and key, and the operator takes
  responsibility for it. No anonymous or keyless automation commits to `main`,
  ever.

## 3. NCO signoff

Every merge to `main` requires an **NCO signoff**: a named non-commissioned
officer of record who did not author the change, independently re-reviewed it
against this repository's `ADVERSARIAL_REVIEW.md`, and accepts responsibility
for it.

- The signoff is a PR comment of the form
  `NCO signoff: <name> - reviewed <commit range> against ADVERSARIAL_REVIEW.md`.
- Review by the author, or by tooling controlled by the author, does not count.
  Independence is the point.
- Merges without a signoff comment are reverted.
- The current NCO of record is listed in `README.md`. There must always be
  exactly one acting NCO; handoff happens by PR with the outgoing NCO signing
  off the incoming one (the one exception to the independence rule).
- Observed status: this repository has been authored and reviewed by the same
  operator, so no merge to date has an independent signoff. The policy above is
  not presented as an already-satisfied control in public copy.

## Changing the standard itself

Changes to `COMPACTATION.md` (the seven rules, operations contract, or model
strategy) get the strictest treatment: the PR description must include a
completed adversarial review of the diff, run against the standard's own rules,
with at least one lens performed by a party other than the author. Version
bumps follow `CHANGELOG.md`. A change to a performance claim also requires an
update to `docs/VALIDATION.md` and to every public copy of the number.

## Secrets and evidence

Do not commit tokens, keys, credentials, real customer logs, or captures that
contain them. Synthetic fixtures are fine. The reference CLI refuses
secret-like patterns by default; keep that default. If a fixture needs a fake
token, use a clearly synthetic value and a documented reason.

## Review expectations

Reviewers apply this repo's `ADVERSARIAL_REVIEW.md`: reproducible evidence for
claims, honest severities, per-lens verdicts. Findings that cannot be reproduced
are downgraded to UNVERIFIED, not argued over. The `provenance` lens is always
in scope: every user-facing factual claim must map to the standard, the
traceability matrix, or the validation plan.
