# compactation.dev

An open-source standard for assisting agents in managing their compactation
strategy with the model or models they are using. The agent may compact its
active context, but the record is immutable, omissions are declared, and every
consequential claim is rehydrated from exact bytes before it is used.

- [index.html](./index.html) - the landing page (Cloudflare Workers Assets)
- [COMPACTATION.md](./COMPACTATION.md) - the canonical agent-readable contract you copy into your repo
- [skill/compactation/SKILL.md](./skill/compactation/SKILL.md) - the installable skill
- [tools/compactation.py](./tools/compactation.py) - a dependency-free reference CLI for the operations contract
- [tests/](./tests/) - 52 unit tests for the reference CLI
- [examples/demo.py](./examples/demo.py) - a reproducible noisy-log walkthrough
- [docs/DESIGN.md](./docs/DESIGN.md) - the design spec behind the standard
- [docs/TRACEABILITY.md](./docs/TRACEABILITY.md) - rule-to-implementation matrix
- [docs/BOUNDEDNESS-PROOF.md](./docs/BOUNDEDNESS-PROOF.md) - proof that bounded authority, budgets, and paths are necessary for the skill's correctness
- [docs/VALIDATION.md](./docs/VALIDATION.md) - experiment plan for the performance expectation
- [ADVERSARIAL_REVIEW.md](./ADVERSARIAL_REVIEW.md) - the review standard this repo holds itself to
- [CONTRIBUTING.md](./CONTRIBUTING.md) - governance: issues before PRs, verified commits, NCO signoff
- [CHANGELOG.md](./CHANGELOG.md) - semver policy, release history, and SHA-256 checksums
- [SECURITY.md](./SECURITY.md) - vulnerability and secret-handling policy

License: MIT (see [LICENSE](./LICENSE)).

## Why this exists

On 2026-11-25 an agent compacted noisy logs mid-task, cut estimated tokens by
roughly 37 percent, discarded the originals, fixed the bug, and then tried to
write a full report from the compacted text. The saving was real; the evidence
chain was broken.

The expectation is that agents using this standard will gain roughly **37
percent better-than-average session-management success** than an unmanaged
baseline. That number comes from an initial trial with no control group. It is
**UNVALIDATED** and requires more data. See [docs/VALIDATION.md](./docs/VALIDATION.md).
Never present it as a measured result, and never drop evidence to chase it.

## Quickstart

```sh
curl -fsSL -O https://raw.githubusercontent.com/awdemos/compactation/v0.0.2/COMPACTATION.md
```

Place `COMPACTATION.md` at the repository root, next to `AGENTS.md` or
`README.md`. Keep every rule above the `## Repo-specific rules` heading intact
and fill that section with checkable rules derived from your own repo. The
quickstart pins to the signed `v0.0.2` tag; verify it with `git tag -v v0.0.2`.
Use the tag URL, not `main`, because branch content can be cached and moved.

## Install the skill

```sh
git clone https://github.com/awdemos/compactation.git
cp -r compactation/skill/compactation ~/.claude/skills/
# or ~/.kimi-code/skills/ for Kimi Code
```

Then say **"compact this session"**, **"manage context with compactation"**, or
**"plan this with an evidence ledger"**. The skill finds your repo's
`COMPACTATION.md` and follows it. Without one it uses the bundled
`default-protocol.md`.

## Use the reference tool

The tool implements capture, projection, verification, retrieval, and reporting
with no third-party dependencies. It is the practical answer to "letting agents
manage their own memory by manipulating strings is not great either": the agent
calls a deterministic ledger instead of rewriting its own context.

```sh
python3 tools/compactation.py --store .compactation init
python3 tools/compactation.py --store .compactation capture --file noisy.log --kind log --model <model-name>
python3 tools/compactation.py --store .compactation project --policy examples/noisy-log-policy.json --out projection.json --model <model-name>
python3 tools/compactation.py --store .compactation verify --projection projection.json
python3 tools/compactation.py --store .compactation retrieve --id <record-id> --out evidence.bin
python3 tools/compactation.py --store .compactation report --projection projection.json --claims claims.json --out report.md
```

Run the tests and the end-to-end demo:

```sh
python3 -m unittest discover -s tests
python3 examples/demo.py
```

Token estimates use a named `utf8_bytes_over_4` heuristic. They are estimates,
not tokenizer output, and any saving they show is separate from the unvalidated
session-success expectation.

## Deploy the site

The site is static and served by Cloudflare Workers Assets. After editing
`index.html`:

```sh
./deploy.sh
```

`deploy.sh` installs pinned dependencies with `npm ci` when `node_modules` is
missing, copies `index.html` and `og-image.png` into `public/`, and runs
`wrangler deploy`. Reviewers use `npx wrangler deploy --dry-run` instead of a
live deploy. The site is live at [https://compactation.dev](https://compactation.dev)
and `https://www.compactation.dev`; see [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md).

## For AI agents reading this

If a repo contains `COMPACTATION.md`, its rules are binding. Read it before
compacting, before a model switch, and before writing a report that depends on
prior context. If no file is present but the user asks for compactation, follow
`skill/compactation/SKILL.md`. Capture first, project with a named policy,
verify, rehydrate before claiming, and mark the 37 percent expectation
UNVALIDATED.

## Provenance

Every release is tagged and signed. Verify one with:

```sh
git tag -v v0.0.2
```

SHA-256 checksums for tracked release files are in `CHANGELOG.md`. A
machine-readable SBOM is in `sbom.spdx.json`. Releases follow semantic
versioning: the seven rules and the operations contract are the stable API;
examples, wording, and the site may tighten in patch releases.

## Governance

NCO of record: Andrew White. Contributions require an accepted issue first,
verified commits, and NCO signoff on every merge to `main`. No tokens, keys, or
credentials belong in this repository, its fixtures, or its issues. This
repository has been authored and reviewed by the same operator so far; no merge
has yet had an independent signoff, and that limitation is recorded in
`docs/TRACEABILITY.md` rather than presented as a completed control.

## Version

0.0.2: follow-up release adding `docs/BOUNDEDNESS-PROOF.md`, v0.0.2 version
alignment, legacy-policy compatibility, and expanded compatibility tests. The
seven protocol rules and the operations contract are unchanged.

0.0.1: first public release of the corrected standard, installable skill,
reference CLI, test suite, validation plan, and static site. It tightens
store-output guards, secret detection, derived verification, coverage
accounting, canonical reports, and public claim accuracy. Earlier draft
artifacts were withdrawn after an adversarial review and are not part of this
release.
