"""Tests for the COMPACTATION.md reference implementation."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "compactation.py"
SPEC = importlib.util.spec_from_file_location("compactation", TOOL)
if SPEC is None or SPEC.loader is None:  # pragma: no cover
    raise RuntimeError("cannot load compactation.py")
compactation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compactation)


class CompactationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = compactation.Store(self.root / "store")
        self.store.init()

    def run_cli(self, *args: str, data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(TOOL), "--store", str(self.store.root), *args],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def policy(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schema": "compactation/policy/0.0.1",
            "name": "test-policy",
            "keep_ids": [],
            "drop_kinds": [],
            "redact": [],
            "dedupe": True,
            "max_chars_per_record": 4000,
            "max_chars_total": 20000,
        }
        value.update(overrides)
        path = self.root / "policy.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return value

    def capture_bytes(self, data: bytes, kind: str = "log") -> str:
        return self.store.put_object(data)

    def project(self, **overrides: object) -> tuple[dict[str, object], int]:
        self.policy(**overrides)
        result = self.run_cli(
            "project", "--policy", str(self.root / "policy.json"), "--model", "test-model"
        )
        return json.loads(result.stdout), result.returncode

    def test_init_is_idempotent_and_non_destructive(self) -> None:
        self.store.append({"id": compactation.digest(b"a"), "bytes": 1})
        before = self.store.ledger.read_bytes()
        self.store.init()
        self.assertEqual(self.store.ledger.read_bytes(), before)

    def test_capture_id_is_sha256_of_bytes(self) -> None:
        data = b"hello evidence\n"
        record_id = self.capture_bytes(data)
        self.assertEqual(record_id, compactation.digest(data))
        self.assertEqual(self.store.get_object(record_id), data)

    def test_capture_via_cli_is_idempotent(self) -> None:
        first = self.run_cli("capture", "--file", "-", data=b"same bytes")
        second = self.run_cli("capture", "--file", "-", data=b"same bytes")
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(json.loads(first.stdout)["id"], json.loads(second.stdout)["id"])
        self.assertEqual(len(self.store.events()), 1)

    def test_ledger_is_append_only_prefix(self) -> None:
        first_id = self.capture_bytes(b"first")
        self.store.append({"id": first_id, "bytes": 5})
        second_id = self.capture_bytes(b"second")
        self.store.append({"id": second_id, "bytes": 6})
        events = self.store.events()
        self.assertEqual([e["id"] for e in events], [first_id, second_id])

    def test_retrieve_returns_exact_bytes(self) -> None:
        data = b"line one\nline two\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        result = self.run_cli("retrieve", "--id", record_id)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, data)

    def test_retrieve_rejects_bad_id(self) -> None:
        result = self.run_cli("retrieve", "--id", "../etc/passwd")
        self.assertEqual(result.returncode, compactation.EXIT_INPUT)

    def test_retrieve_detects_tampered_object(self) -> None:
        record_id = self.capture_bytes(b"original")
        path = self.store.object_path(record_id)
        path.write_bytes(b"tampered")
        result = self.run_cli("retrieve", "--id", record_id)
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)

    def test_secret_detection_refuses_capture(self) -> None:
        result = self.run_cli(
            "capture", "--file", "-", data=b"token ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        )
        self.assertEqual(result.returncode, compactation.EXIT_REFUSED)
        self.assertIn("github_token", result.stderr.decode())

    def test_secret_detection_allows_explicit_reason(self) -> None:
        result = self.run_cli(
            "capture",
            "--file", "-",
            "--allow-secrets",
            "--reason",
            "synthetic fixture for redaction test",
            data=b"ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(self.store.events()), 1)

    def test_projection_is_deterministic(self) -> None:
        data = b"stable evidence\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        first, code_one = self.project()
        second, code_two = self.project()
        self.assertEqual((code_one, code_two), (0, 0))
        self.assertEqual(first["id"], second["id"])

    def test_projection_covers_all_captured_bytes(self) -> None:
        for index in range(3):
            data = f"record {index}\n".encode()
            record_id = self.capture_bytes(data)
            self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, code = self.project()
        self.assertEqual(code, 0)
        coverage = projection["core"]["coverage"]
        self.assertTrue(coverage["balanced"])
        self.assertEqual(
            coverage["captured_bytes"],
            coverage["referenced_bytes"] + coverage["declared_omitted_bytes"],
        )

    def test_dedupe_declares_omission(self) -> None:
        data = b"repeated line\nrepeated line\nunique line\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, code = self.project()
        self.assertEqual(code, 0)
        self.assertEqual(len(projection["core"]["records"]), 1)
        self.assertTrue(any(o["policy"] == "dedupe" for o in projection["core"]["omissions"]))
        self.assertIn("unique line", projection["core"]["records"][0]["excerpt"])
        self.assertEqual(self.store.get_object(record_id), data)

    def test_redaction_does_not_mutate_stored_object(self) -> None:
        data = b"visible token=secret-string end\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, code = self.project(
            redact=[{"pattern": "secret-[a-z]+", "replacement": "[REDACTED]"}]
        )
        self.assertEqual(code, 0)
        self.assertIn("[REDACTED]", projection["core"]["records"][0]["excerpt"])
        self.assertEqual(self.store.get_object(record_id), data)
        self.assertTrue(projection["core"]["redactions"])

    def test_bounds_declares_truncation(self) -> None:
        data = b"x" * 200
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, code = self.project(max_chars_per_record=50)
        self.assertEqual(code, 0)
        self.assertTrue(any(o["policy"] == "bounds" for o in projection["core"]["omissions"]))
        self.assertEqual(len(projection["core"]["records"][0]["excerpt"]), 50)

    def test_total_budget_exits_budget_not_green(self) -> None:
        for index in range(3):
            data = f"record {index} " * 20
            record_id = self.capture_bytes(data.encode())
            self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, code = self.project(max_chars_total=40)
        self.assertEqual(code, 0)
        self.assertEqual(projection["core"]["exit_reason"], "budget")

    def test_verify_passes_on_green_projection(self) -> None:
        data = b"verify me\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, code = self.project()
        self.assertEqual(code, 0)
        path = self.root / "projection.json"
        path.write_text(json.dumps(projection), encoding="utf-8")
        result = self.run_cli("verify", "--projection", str(path))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["pass"])

    def test_verify_fails_on_tampered_object(self) -> None:
        data = b"verify me\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, _code = self.project()
        path = self.root / "projection.json"
        path.write_text(json.dumps(projection), encoding="utf-8")
        self.store.object_path(record_id).write_bytes(b"changed")
        result = self.run_cli("verify", "--projection", str(path))
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)
        self.assertFalse(json.loads(result.stdout)["pass"])

    def test_verify_fails_on_changed_projection_core(self) -> None:
        data = b"verify me\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, _code = self.project()
        projection["core"]["model"] = "different-model"
        path = self.root / "projection.json"
        path.write_text(json.dumps(projection), encoding="utf-8")
        result = self.run_cli("verify", "--projection", str(path))
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)

    def test_report_cites_rehydrated_evidence(self) -> None:
        data = b"error at line 42: null pointer\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, _code = self.project()
        projection_path = self.root / "projection.json"
        projection_path.write_text(json.dumps(projection), encoding="utf-8")
        claims_path = self.root / "claims.json"
        claims_path.write_text(
            json.dumps([{"claim": "the failure is a null pointer", "record_ids": [record_id]}]),
            encoding="utf-8",
        )
        result = self.run_cli(
            "report", "--projection", str(projection_path), "--claims", str(claims_path)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(record_id[:16].encode(), result.stdout)
        self.assertIn(b"null pointer", result.stdout)
        self.assertIn(b"Validation status: unvalidated", result.stdout)

    def test_report_marks_uncited_claim_unverified(self) -> None:
        data = b"evidence\n"
        record_id = self.capture_bytes(data)
        self.store.append({"id": record_id, "hash": record_id, "bytes": len(data), "kind": "log"})
        projection, _code = self.project()
        projection_path = self.root / "projection.json"
        projection_path.write_text(json.dumps(projection), encoding="utf-8")
        claims_path = self.root / "claims.json"
        claims_path.write_text(
            json.dumps([{"claim": "uncited assertion", "record_ids": []}]), encoding="utf-8"
        )
        result = self.run_cli(
            "report", "--projection", str(projection_path), "--claims", str(claims_path)
        )
        self.assertEqual(result.returncode, compactation.EXIT_POLICY)
        self.assertIn(b"UNVERIFIED - uncited assertion", result.stdout)

    def test_estimate_uses_named_heuristic(self) -> None:
        source = self.root / "source.txt"
        source.write_bytes(b"12345678")
        result = self.run_cli("estimate", str(source))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["estimated_tokens"], 2)

    def test_help_and_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--version"], capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"0.0.1", result.stdout)


    def _record(self, data: bytes, kind: str = "log") -> str:
        record_id = self.capture_bytes(data)
        self.store.append(
            {"id": record_id, "hash": record_id, "bytes": len(data), "kind": kind}
        )
        return record_id

    def _projection_file(self) -> Path:
        projection, _code = self.project()
        path = self.root / "projection.json"
        path.write_text(json.dumps(projection), encoding="utf-8")
        return path

    def test_output_paths_cannot_mutate_store(self) -> None:
        first = self._record(b"alpha evidence\n")
        second = self._record(b"beta evidence\n")
        self.policy()
        policy_path = self.root / "policy.json"
        ledger_before = self.store.ledger.read_bytes()
        object_before = self.store.object_path(second).read_bytes()

        project = self.run_cli(
            "project", "--policy", str(policy_path), "--out", str(self.store.ledger)
        )
        retrieve = self.run_cli(
            "retrieve", "--id", first, "--out", str(self.store.object_path(second))
        )
        projection_path = self._projection_file()
        claims_path = self.root / "claims.json"
        claims_path.write_text("[]", encoding="utf-8")
        report = self.run_cli(
            "report", "--projection", str(projection_path),
            "--claims", str(claims_path), "--out", str(self.store.ledger),
        )

        for result in (project, retrieve, report):
            self.assertEqual(result.returncode, compactation.EXIT_INPUT)
        self.assertEqual(self.store.ledger.read_bytes(), ledger_before)
        self.assertEqual(self.store.object_path(second).read_bytes(), object_before)

    def test_secret_detection_covers_common_formats(self) -> None:
        payloads = [
            b"ASIA1234567890ABCDEF",
            b"sk-abcdefghijklmnopqrstuvwxyz1234",
            b"sk-ant-abcdefghijklmnopqrstuvwxyz12",
            b"github_pat_abcdefghijklmnopqrstuvwxyz12",
            b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
            "ghp_abcdefghijklmnopqrstuvwxyz0123456789".encode("utf-16-le"),
            b"api_key=abcdefghijklmnop",
        ]
        for payload in payloads:
            with self.subTest(payload=payload[:20]):
                result = self.run_cli("capture", "--file", "-", data=payload)
                self.assertEqual(result.returncode, compactation.EXIT_REFUSED)

    def test_secret_detection_scans_metadata_and_redacts_it(self) -> None:
        token = b"ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        refused = self.run_cli(
            "capture", "--file", "-", "--note", token.decode(), data=b"clean bytes\n"
        )
        self.assertEqual(refused.returncode, compactation.EXIT_REFUSED)

        allowed = self.run_cli(
            "capture", "--file", "-", "--note", token.decode(),
            "--allow-secrets", "--reason", "synthetic metadata fixture",
            data=b"clean bytes\n",
        )
        self.assertEqual(allowed.returncode, 0)
        events = self.store.events()
        self.assertEqual(len(events), 1)
        self.assertNotIn(token.decode(), events[0]["note"])
        self.assertNotIn(token.decode(), events[0]["source"])

    def test_verify_rejects_forged_projection(self) -> None:
        self._record(b"original evidence\n")
        path = self._projection_file()

        for field in ("coverage", "excerpt"):
            with self.subTest(field=field):
                projection = json.loads(path.read_text(encoding="utf-8"))
                if field == "coverage":
                    projection["core"]["coverage"]["captured_bytes"] -= 1
                else:
                    projection["core"]["records"][0]["excerpt"] = "fabricated"
                    projection["core"]["records"][0]["excerpt_hash"] = compactation.digest(
                        b"fabricated"
                    )
                projection["id"] = compactation.digest(
                    compactation.canonical_json(projection["core"])
                )
                path.write_text(json.dumps(projection), encoding="utf-8")
                result = self.run_cli("verify", "--projection", str(path))
                self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)
                checks = json.loads(result.stdout)["checks"]
                derived = next(
                    item for item in checks
                    if item["check"] == "derived_from_store_and_policy"
                )
                self.assertFalse(derived["pass"])

    def test_total_bounds_after_redaction_counts_bytes_once(self) -> None:
        self._record(b"https://example.com/a/very/long/path " + b"x" * 40)
        projection, code = self.project(
            redact=[{"pattern": "https://[^ ]+", "replacement": "[URL]"}],
            max_chars_total=1,
        )
        self.assertEqual(code, 0)
        coverage = projection["core"]["coverage"]
        self.assertTrue(coverage["balanced"])
        self.assertEqual(coverage["declared_omitted_bytes"], coverage["captured_bytes"])
        self.assertEqual(coverage["referenced_bytes"], 0)

    def test_expanding_redaction_is_refused(self) -> None:
        self._record(b"short\n")
        self.policy(
            redact=[{"pattern": "short", "replacement": "much longer replacement"}]
        )
        result = self.run_cli("project", "--policy", str(self.root / "policy.json"))
        self.assertEqual(result.returncode, compactation.EXIT_POLICY)
        self.assertIn(b"expands bytes", result.stderr)

    def test_report_uses_canonical_field_names(self) -> None:
        data = b"error at line 42: null pointer\n"
        record_id = self._record(data)
        projection_path = self._projection_file()
        claims_path = self.root / "claims.json"
        claims_path.write_text(
            json.dumps([{"claim": "null pointer", "record_ids": [record_id]}]),
            encoding="utf-8",
        )
        result = self.run_cli(
            "report", "--projection", str(projection_path), "--claims", str(claims_path)
        )
        self.assertEqual(result.returncode, 0)
        report = result.stdout.decode()
        for field in (
            "## Compactation - ", "Model: ", "Status: ", "Projection: ", "Coverage: ",
            "Records: ", "Omitted: ", "Redactions: ", "Token estimate: ",
            "Rehydrated for decisions: ", "Integrity: ", "UNVERIFIED: ",
            "Validation status: unvalidated (see docs/VALIDATION.md)",
        ):
            self.assertIn(field, report)

    def test_projection_declares_context_budget(self) -> None:
        self._record(b"budget evidence\n")
        projection, code = self.project()
        self.assertEqual(code, 0)
        core = projection["core"]
        self.assertEqual(core["context_budget"], "advisory-unknown")
        self.assertFalse(core["budget_enforced"])

    def test_span_counts_bytes_not_characters(self) -> None:
        data = "héllo wörld evidence ünicode\n".encode("utf-8")
        self._record(data)
        projection, code = self.project()
        self.assertEqual(code, 0)
        span = projection["core"]["records"][0]["span"]
        self.assertEqual(span["end"], len(data))
        self.assertEqual(span["total"], len(data))

    def test_malformed_ledger_hash_is_structured(self) -> None:
        record_id = self.capture_bytes(b"valid bytes")
        self.store.append({"id": record_id, "hash": "not-a-hash", "bytes": 11})
        self.policy()
        result = self.run_cli(
            "project", "--policy", str(self.root / "policy.json")
        )
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_redaction_pattern_complexity_is_bounded(self) -> None:
        self._record(b"aaaa\n")
        self.policy(redact=[{"pattern": "(a+)+$", "replacement": "x"}])
        result = self.run_cli("project", "--policy", str(self.root / "policy.json"))
        self.assertEqual(result.returncode, compactation.EXIT_INPUT)
        self.assertIn(b"nested quantifier", result.stderr)

    def test_git_sha_is_not_treated_as_a_secret(self) -> None:
        sha = b"commit 4cf37e44a962aec29c4e12a31840ccaa823962c5 pushed"
        result = self.run_cli("capture", "--file", "-", data=sha)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual([], compactation.detect_secrets(sha))

    def test_placeholder_assignments_are_not_refused(self) -> None:
        for payload in (
            b"token=disabled\n",
            b"token=placeholder\n",
            b"password=changeme\n",
            b"secret=REDACTED\n",
            b'api_key="YOUR_API_KEY_HERE"\n',
        ):
            with self.subTest(payload=payload):
                result = self.run_cli("capture", "--file", "-", data=payload)
                self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_secret_key_assignment_variants_are_detected(self) -> None:
        value = b"abcdefghijklmnop"
        for key in (
            b"secret_key", b"secretkey", b"secret-key", b"my_secret",
            b"token_key", b"password2", b"passwd2", b"aws_secret_access_key",
        ):
            with self.subTest(key=key):
                self.assertTrue(compactation.detect_secrets(key + b"=" + value))
        quoted = b'{"secret_key": "abcdefghijklmnop"}'
        self.assertTrue(compactation.detect_secrets(quoted))
        aws = b"aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        self.assertIn("aws_secret_key", compactation.detect_secrets(aws))

    def test_catastrophic_redaction_patterns_are_rejected(self) -> None:
        for pattern in ("((a+))+$", "(a|a)+$", "a+a+", "(.*)(.*)"):
            with self.subTest(pattern=pattern):
                self.assertFalse(compactation.safe_redact_pattern(pattern))

    def test_nested_redaction_patterns_are_rejected(self) -> None:
        for pattern in (
            "(a?a?)+$", "(a??a?)+$", "(a{0,1}a{0,1})+$", "(?:a+)+$",
            "((a|a))+$", "((a|aa))+$", "((a+))+$", "(a|a)+$",
            r"(a+)\1\1$", r"((a+))\1\1$", r"(?P<x>a+)(?P=x)",
            r"(?=(a+))a+", "a{0,100000}", "a{0,}",
        ):
            with self.subTest(pattern=pattern):
                self.assertFalse(compactation.safe_redact_pattern(pattern))
        self._record(b"aaaa\n")
        for pattern in ("(a?a?)+$", "((a|a))+$", r"(a+)\1\1$"):
            with self.subTest(end_to_end=pattern):
                self.policy(redact=[{"pattern": pattern, "replacement": "x"}])
                result = self.run_cli(
                    "project", "--policy", str(self.root / "policy.json")
                )
                self.assertEqual(result.returncode, compactation.EXIT_INPUT)

    def test_benign_redaction_patterns_are_accepted(self) -> None:
        for pattern in (
            "literal", "[A-Za-z0-9_]+", "ghp_[A-Za-z0-9]{20,}", r"foo\d+",
            "(foo|bar)", "a{2,4}b",
        ):
            with self.subTest(pattern=pattern):
                self.assertTrue(compactation.safe_redact_pattern(pattern))

    def test_report_refuses_forged_projection(self) -> None:
        record_id = self._record(b"evidence for report\n")
        projection_path = self._projection_file()
        claims_path = self.root / "claims.json"
        claims_path.write_text("[]", encoding="utf-8")
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        projection["core"]["coverage"]["captured_bytes"] -= 1
        projection["id"] = compactation.digest(
            compactation.canonical_json(projection["core"])
        )
        projection_path.write_text(json.dumps(projection), encoding="utf-8")
        result = self.run_cli(
            "report", "--projection", str(projection_path), "--claims", str(claims_path)
        )
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)
        self.assertNotIn(record_id[:16].encode(), result.stdout)

    def test_projection_rejects_byte_count_mismatch(self) -> None:
        data = b"thirteen bytes"
        record_id = self.capture_bytes(data)
        self.store.append(
            {"id": record_id, "hash": record_id, "bytes": 100, "kind": "log"}
        )
        projection, code = self.project()
        self.assertEqual(code, compactation.EXIT_POLICY)
        self.assertEqual(projection["core"]["unresolved"], [record_id])

    def test_non_object_ledger_event_is_structured(self) -> None:
        self.store.ledger.write_text("[1, 2, 3]\n", encoding="utf-8")
        self.policy()
        result = self.run_cli("project", "--policy", str(self.root / "policy.json"))
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_verify_malformed_projection_is_structured(self) -> None:
        path = self.root / "bad-projection.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        result = self.run_cli("verify", "--projection", str(path))
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)
        self.assertFalse(json.loads(result.stdout)["pass"])

    def test_verify_malformed_records_list_is_structured(self) -> None:
        record_id = self._record(b"malformed records evidence\n")
        projection = json.loads(self._projection_file().read_text(encoding="utf-8"))
        projection["core"]["records"] = [1]
        path = self.root / "bad-records.json"
        path.write_text(json.dumps(projection), encoding="utf-8")
        result = self.run_cli("verify", "--projection", str(path))
        self.assertEqual(result.returncode, compactation.EXIT_INTEGRITY)
        self.assertFalse(json.loads(result.stdout)["pass"])

    def test_allow_reason_secrets_are_redacted(self) -> None:
        token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        result = self.run_cli(
            "capture", "--file", "-", "--allow-secrets", "--reason", f"synthetic {token}",
            data=b"clean bytes\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        event = self.store.events()[0]
        self.assertNotIn(token, event["allow_reason"])
        self.assertTrue(event["metadata_secret_flags"])

    def test_model_and_kind_are_scanned_for_secrets(self) -> None:
        result = self.run_cli(
            "capture", "--file", "-", "--model", "sk-abcdefghijklmnopqrstuvwxyz12",
            data=b"clean bytes\n",
        )
        self.assertEqual(result.returncode, compactation.EXIT_REFUSED)

    def test_store_option_is_accepted_after_subcommand(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "capture", "--store", str(self.store.root),
             "--file", "-"],
            input=b"store after subcommand\n", stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_boolean_is_rejected_as_integer_policy_value(self) -> None:
        self.policy(max_chars_total=True)
        result = self.run_cli("project", "--policy", str(self.root / "policy.json"))
        self.assertEqual(result.returncode, compactation.EXIT_INPUT)

    def test_total_bounds_record_is_not_a_dedupe_ancestor(self) -> None:
        self._record(b"identical payload\n")
        self._record(b"identical payload\n")
        projection, code = self.project(max_chars_total=1)
        self.assertEqual(code, 0)
        omissions = projection["core"]["omissions"]
        self.assertEqual(sum(o["policy"] == "total_bounds" for o in omissions), 2)
        self.assertFalse(any(o["policy"] == "dedupe" for o in omissions))

    def test_token_count_estimate_matches_bytes_heuristic(self) -> None:
        self.assertEqual(compactation.token_count_estimate(1000), 250)
        self.assertEqual(compactation.token_estimate(b"x" * 1000), 250)


if __name__ == "__main__":
    unittest.main()
