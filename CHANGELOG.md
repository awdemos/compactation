# Changelog

Semantic versioning: the seven rules, the operations contract, and the
model-strategy rules in `COMPACTATION.md` are the stable API. Examples,
wording, the reference tool internals, and the site may tighten in patch
releases.

## [Unreleased]

- No unreleased changes.

## [v0.0.1] - 2026-11-26

- Reset release after an adversarial review; withdrawn draft artifacts are excluded.
- Refuse store-internal `--out` targets for `project`, `retrieve`, and `report`.
- Broaden secret detection to common credential formats, encodings, and metadata.
- Re-derive projections from store bytes during `verify` so hand-edited fields fail.
- Fix coverage double-counting and classify unbalanced results as stalls.
- Emit the canonical report shape, byte spans, and declared context budget.
- Tighten secret detection so git SHAs and placeholders are not refused while key-name variants, quoted keys, and metadata are covered.
- Bound redaction regexes against catastrophic backtracking and verify a projection before rendering a report from it.
- Fail closed on malformed ledger events and byte-count mismatches; redact secret-like reason, model, and kind metadata.
- Accept --store on either side of the subcommand; document accepted risks.
- Correct public version and governance claims; add regression tests.

Verification (`sha256sum`):

```
2beaa8924ba22e618c141d342532ab237e7660016266381e25a994dd5eedd88c  .gitignore
4aa6c46c6708696cbf331b2c29a0e8a6ebb6592d4ac692ca5dd5f6daca83ef48  ADVERSARIAL_REVIEW.md
9c1039314d931e0681f932e7d445c6c9dbc32a7492bad0c346d43c4cc77ab943  COMPACTATION.md
44f8473a1878a8f3a1181d7834de1c503d99b1950fdfe8335c9870f7df77797b  CONTRIBUTING.md
44015a2f28572408fc4f095e56fde4ddc1c361cfc708f9bbf27ddee55f294db1  LICENSE
a1e855484da879b285d00aada233e706ea535f63652b8ccc816d64fe25059239  README.md
8f4f667ad2b227f03fb572f837ca074b40cafef41542441da0426b991e8ed6dd  SECURITY.md
8782f4d465643d56e35cc1ae5448c24714a160329e8282993889ad96936070d2  deploy.sh
7b84db200a26c735dafb8e5ff5d2e9cef9f96b3d63fd89bf57f1636aed4efbd5  docs/DEPLOYMENT.md
6cc955c646af45124248de0a109fc1c61aa3351642da2fa06652adc5998fbb09  docs/DESIGN.md
f72e55c3ae65defd8c48539ab9a52e4f4b31eb26ae67770e913823c866636335  docs/TRACEABILITY.md
8966fe7b766b09732ba26c8e075abbed6d595311dadfa24478d62e357790b641  docs/VALIDATION.md
bf713180894ddc541d12d28cbc437ffd805513c4b424c25473f5284336f367f9  examples/demo.py
45c3a2532418f8d19b3fc065fe7ea27107246df7ace6302c352677fbe7c56336  examples/noisy-log-policy.json
967c3f58b244247e2ac49c20005637ae7a9cc0d46d877cc35e3614a876bf1a86  index.html
3fd985836b78bd045afa3529d9becb90124ddef08a74b040709b4e50c8579d39  og-image.png
bffc19b7871d0c5a7cb3319fcacfcd13b13e40733aff53eaba6dbadb449c6f22  package-lock.json
364212ee917e84b73f888039592b328baf1f34498287de7361131f97f0daebfb  package.json
967c3f58b244247e2ac49c20005637ae7a9cc0d46d877cc35e3614a876bf1a86  public/index.html
3fd985836b78bd045afa3529d9becb90124ddef08a74b040709b4e50c8579d39  public/og-image.png
05a99cbf6a9d0bc4b2bbcbc6cabb415654d0b50f7297a028392cc4cfcac2e3e0  skill/compactation/SKILL.md
8fcc75263919e969e05e6ed352a3e17a5fdceaa5354adef1d959012de863b82a  skill/compactation/default-protocol.md
cc9b5cfdef5ecf2476b0cf09284409f8abcddf1bd6dabb59f6506e0d58290a41  tests/test_compactation.py
b5c41a3f36693395b4727b2af2d59773dbdb9aef01cf6b03178608b1c663997f  tools/compactation.py
8e5555d88714ddfef5fa0cf2ce6500648cfe355cf44d8ec6af57c1729e49d788  tools/make_og_image.py
24bc3f632d60f68380eaa9f077282622c0c5eee89f0d5cfa7941a8e306d7773c  tools/make_release_metadata.py
e9fc30fdf81ed0837fb8c619462fa9eb6c11472c2019cb34d4bb54188bb7e073  wrangler.toml
```

Verify the release with `git tag -v v0.0.1`; the signed tag covers
every tracked release file, including this changelog.

[v0.0.1]: https://github.com/awdemos/compactation/releases/tag/v0.0.1
