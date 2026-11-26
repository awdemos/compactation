#!/usr/bin/env python3
"""Generate the SPDX SBOM and the release checksum block for v0.0.1.

Dev-only script. It excludes itself, the changelog, and the SBOM from checksums
so no file contains its own hash. This is a reset release: no earlier sections
are carried forward.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.0.1"
CREATED = "2026-11-26T00:00:00Z"
EXCLUDED = {
    "CHANGELOG.md",
    "sbom.spdx.json",
    ".git",
    "node_modules",
    ".wrangler",
    ".compactation",
    "__pycache__",
}
RELEASE_NOTES = [
    "- Reset release after an adversarial review; withdrawn draft artifacts are excluded.",
    "- Refuse store-internal `--out` targets for `project`, `retrieve`, and `report`.",
    "- Broaden secret detection to common credential formats, encodings, and metadata.",
    "- Re-derive projections from store bytes during `verify` so hand-edited fields fail.",
    "- Fix coverage double-counting and classify unbalanced results as stalls.",
    "- Emit the canonical report shape, byte spans, and declared context budget.",
    "- Tighten secret detection so git SHAs and placeholders are not refused while "
    "key-name variants, quoted keys, and metadata are covered.",
    "- Bound redaction regexes against catastrophic backtracking and verify a "
    "projection before rendering a report from it.",
    "- Fail closed on malformed ledger events and byte-count mismatches; redact "
    "secret-like reason, model, and kind metadata.",
    "- Accept --store on either side of the subcommand; document accepted risks.",
    "- Correct public version and governance claims; add regression tests.",
]


def tracked_files() -> list[Path]:
    """List release files from git, excluding ignored and excluded paths."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=True,
        )
        candidates = [Path(line) for line in result.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.CalledProcessError):
        candidates = [
            path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file()
        ]
    release: list[Path] = []
    for relative in candidates:
        if any(part in EXCLUDED for part in relative.parts):
            continue
        if any(part.endswith(".pyc") for part in relative.parts):
            continue
        if (ROOT / relative).is_file():
            release.append(relative)
    return sorted(release, key=lambda path: path.as_posix())


def sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def spdx_id(name: str) -> str:
    safe = "".join(char if char.isalnum() else "-" for char in name)
    return f"SPDXRef-File-{safe.strip('-')}"


def make_sbom(files: list[Path]) -> None:
    package = {
        "SPDXID": "SPDXRef-Package-compactation",
        "name": "compactation",
        "versionInfo": VERSION,
        "supplier": "Person: Andrew White",
        "downloadLocation": "https://github.com/awdemos/compactation",
        "filesAnalyzed": False,
        "licenseConcluded": "MIT",
        "licenseDeclared": "MIT",
        "copyrightText": "Copyright (c) 2026 Andrew White",
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:github/awdemos/compactation@{VERSION}",
            }
        ],
    }
    entries = []
    for path in files:
        entries.append(
            {
                "fileName": f"./{path.as_posix()}",
                "SPDXID": spdx_id(path.as_posix()),
                "checksums": [{"algorithm": "SHA256", "checksumValue": sha256(path)}],
                "licenseConcluded": "MIT",
                "copyrightText": "Copyright (c) 2026 Andrew White",
            }
        )
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package-compactation",
        }
    ]
    relationships.extend(
        {
            "spdxElementId": "SPDXRef-Package-compactation",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": entry["SPDXID"],
        }
        for entry in entries
    )
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"compactation-v{VERSION}",
        "documentNamespace": f"https://compactation.dev/spdx/compactation-v{VERSION}",
        "creationInfo": {
            "created": CREATED,
            "creators": ["Person: Andrew White", f"Tool: compactation-release-metadata-{VERSION}"],
            "licenseListVersion": "3.25",
        },
        "documentDescribes": ["SPDXRef-Package-compactation"],
        "packages": [package],
        "files": entries,
        "relationships": relationships,
    }
    (ROOT / "sbom.spdx.json").write_text(
        json.dumps(document, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def make_changelog(files: list[Path]) -> None:
    lines = [
        "# Changelog",
        "",
        "Semantic versioning: the seven rules, the operations contract, and the",
        "model-strategy rules in `COMPACTATION.md` are the stable API. Examples,",
        "wording, the reference tool internals, and the site may tighten in patch",
        "releases.",
        "",
        "## [Unreleased]",
        "",
        "- No unreleased changes.",
        "",
        f"## [v{VERSION}] - 2026-11-26",
        "",
        *RELEASE_NOTES,
        "",
        "Verification (`sha256sum`):",
        "",
        "```",
    ]
    for path in files:
        lines.append(f"{sha256(path)}  {path.as_posix()}")
    lines.extend(
        [
            "```",
            "",
            f"Verify the release with `git tag -v v{VERSION}`; the signed tag covers",
            "every tracked release file, including this changelog.",
            "",
            f"[v{VERSION}]: https://github.com/awdemos/compactation/releases/tag/v{VERSION}",
            "",
        ]
    )
    (ROOT / "CHANGELOG.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    files = tracked_files()
    make_sbom(files)
    make_changelog(files)
    print(f"wrote SBOM and changelog for {len(files)} tracked files")


if __name__ == "__main__":
    main()
