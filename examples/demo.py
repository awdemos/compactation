#!/usr/bin/env python3
"""Reproduce the noisy-log scenario: capture, project, verify, retrieve, report.

Run: python3 examples/demo.py
The store is created in a temporary directory. Nothing is written to your repo.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "compactation.py"
POLICY = ROOT / "examples" / "noisy-log-policy.json"


def run(
    store: str, *args: str, data: bytes | None = None, allowed: tuple[int, ...] = (0,)
) -> bytes:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--store", store, *args],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in allowed:
        raise RuntimeError(
            f"command failed ({result.returncode}): {result.stderr.decode('utf-8', 'replace')}"
        )
    return result.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="compactation-demo-") as tmp:
        work = Path(tmp)
        store = str(work / "store")
        run(store, "init", "--quiet")

        lines = [
            "2026-11-25T09:00:01Z INFO boot sequence complete",
            "2026-11-25T09:00:02Z DEBUG env=prod region=eu-west-1",
            "2026-11-25T09:00:03Z WARN retry queue depth 1194",
            "2026-11-25T09:00:04Z ERROR null pointer in parse_header at src/parse.rs:88",
            "2026-11-25T09:00:05Z DEBUG token=DEMO_TOKEN_abc123xyz789",
            "2026-11-25T09:00:06Z INFO worker 3 restarted",
        ]
        noisy = ("\n".join(lines) + "\n").encode("utf-8")
        repeated = ("\n".join(lines) + "\n").encode("utf-8")
        metric = b"metric queue_depth=1194 timestamp=2026-11-25T09:00:07Z\n"

        ids = []
        for name, data, kind in (
            ("noisy.log", noisy, "log"),
            ("repeat.log", repeated, "log"),
            ("metrics.txt", metric, "metric"),
        ):
            out = run(
                store, "capture", "--file", "-", "--kind", kind,
                "--model", "demo-model", "--note", name,
                "--allow-secrets", "--reason", "synthetic token in public demo fixture",
                data=data,
            )
            ids.append(json.loads(out)["id"])

        projection_path = str(work / "projection.json")
        run(
            store, "project", "--policy", str(POLICY),
            "--out", projection_path, "--model", "demo-model",
        )
        projection = json.loads(Path(projection_path).read_text(encoding="utf-8"))
        core = projection["core"]

        verify_result = json.loads(run(store, "verify", "--projection", projection_path))
        evidence_path = str(work / "evidence.bin")
        run(store, "retrieve", "--id", ids[0], "--out", evidence_path)
        retrieved = Path(evidence_path).read_bytes()

        claims_path = work / "claims.json"
        claims_path.write_text(
            json.dumps(
                [
                    {
                        "claim": "the null pointer originates in parse_header",
                        "record_ids": [ids[0], ids[1]],
                    },
                    {"claim": "deployment was slow", "record_ids": []},
                ]
            ),
            encoding="utf-8",
        )
        report_path = str(work / "report.md")
        run(
            store, "report", "--projection", projection_path,
            "--claims", str(claims_path), "--out", report_path,
            allowed=(0, 2),
        )
        report = Path(report_path).read_text(encoding="utf-8")

        summary = {
            "records_captured": len(ids),
            "projection_id": projection["id"][:16],
            "records_projected": len(core["records"]),
            "omissions": [o["policy"] for o in core["omissions"]],
            "redactions": sum(r["count"] for r in core["redactions"]),
            "coverage_balanced": core["coverage"]["balanced"],
            "verification_passed": verify_result["pass"],
            "verbatim_bytes_rehydrated": len(retrieved),
            "token_estimate": core["token_estimate"],
            "uncited_claim_marked_unverified": "UNVERIFIED - deployment was slow" in report,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        print("\nThe 37 percent figure remains UNVALIDATED; see docs/VALIDATION.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
