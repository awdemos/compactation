#!/usr/bin/env python3
"""Generate the SPDX SBOM and the current release checksum block.

Dev-only script. It excludes itself, the changelog, and the SBOM from checksums
so no file contains its own hash. Earlier changelog sections are preserved.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.0.2"
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
    "- Add `docs/BOUNDEDNESS-PROOF.md`: a short proof that correctness requires "
    "bounded operations, budget and model scope, and guarded paths.",
    "- Bump the contract, CLI, example policy, package metadata, and site to v0.0.2; "
    "the seven rules and operations contract are unchanged.",
    "- Keep `compactation/policy/0.0.1` policies valid while emitting and "
    "documenting `compactation/policy/0.0.2`.",
    "- Add regression tests for legacy policy acceptance and the current projection "
    "schema; preserve earlier changelog checksum history.",
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


def prior_history() -> str:
    """Return earlier version sections so a patch release keeps checksum history."""
    path = ROOT / "CHANGELOG.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"(?m)^## \[v(\d+\.\d+\.\d+)\]", text):
        if match.group(1) != VERSION:
            return text[match.start():].rstrip() + "\n"
    return ""


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
    history = prior_history()
    if history:
        lines.extend([history.rstrip(), ""])
    (ROOT / "CHANGELOG.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    files = tracked_files()
    make_sbom(files)
    make_changelog(files)
    print(f"wrote SBOM and changelog for {len(files)} tracked files")


if __name__ == "__main__":
    main()
