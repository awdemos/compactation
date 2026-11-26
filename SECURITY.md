# Security policy

## Reporting a vulnerability

Open a private security advisory on the GitHub repository, or contact the NCO
of record named in `README.md`. Do not open a public issue for an unfixed
vulnerability. Include a reproduction, the affected version or tag, and the
expected versus actual behavior.

## Secrets

This repository is public. Never commit tokens, API keys, private keys,
credentials, or real customer logs. The reference CLI refuses capture when it
detects common secret-like patterns unless `--allow-secrets` is used with an
explicit `--reason`. That escape hatch exists for synthetic fixtures only. If a
secret is committed, rotate it first, then report it. Do not rewrite public
history without operator approval.

## Supported versions

Security fixes are applied to the latest published tag. Older tags are
immutable historical artifacts; upgrade instead of patching a tag.

## Scope

The static site, the installable skill, the canonical Markdown contract, and
the reference CLI are in scope. Third-party runtime behavior (model providers,
Cloudflare, GitHub) is out of scope except where this project misdocuments it.
