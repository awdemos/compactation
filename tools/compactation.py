#!/usr/bin/env python3
"""Compactation reference implementation.

A small, dependency-free CLI that implements the operations required by
COMPACTATION.md: an append-only content-addressed evidence store, deterministic
projections with coverage accounting, verified retrieval, verification, and
provenance reports.

Token estimates are a documented heuristic (UTF-8 bytes / 4), not a model
tokenizer. Performance figures produced by this tool are estimates and remain
UNVALIDATED as described in docs/VALIDATION.md.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "compactation/0.0.2"
VERSION = "0.0.2"
POLICY_SCHEMAS = {"compactation/policy/0.0.2", "compactation/policy/0.0.1"}
ID_RE = re.compile(r"^[0-9a-f]{64}$")

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "aws_secret_key",
        re.compile(
            r"(?i)\b(?:aws_secret_access_key|secret_access_key|aws_secret_key|secret_key)"
            r"['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{32,}"
        ),
    ),
    (
        "aws_secret_key_shape",
        re.compile(
            r"\b(?=[A-Za-z0-9/+=]{40}\b)(?=[A-Za-z0-9/+=]*[a-z])"
            r"(?=[A-Za-z0-9/+=]*[A-Z])(?=[A-Za-z0-9/+=]*[0-9])"
            r"(?=[A-Za-z0-9/+=]*[/+=])[A-Za-z0-9/+=]{40}\b"
        ),
    ),
    ("private_key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY(?: BLOCK)?-----")),
    ("openai_style_key", re.compile(r"\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{16,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}\b")),
    (
        "github_token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b")),
    (
        "secret_assignment",
        re.compile(
            r"(?i)['\"]?(?:[A-Za-z0-9]*[_-])?"
            r"(?:pass(?:word|wd)\d*|secret(?:[_-]?(?:access[_-]?)?key)?|"
            r"access[_-]?token|token(?:[_-]?key)?|api[_-]?key)['\"]?\s*[:=]\s*['\"]?"
            r"(?!(?:disabled|undefined|redacted|placeholder|synthetic|notset|changeme|removed|"
            r"none|null|your[_-]?api[_-]?key(?:[_-]?here)?|not[_-]?configured|example|dummy|fake)\b)"
            r"[A-Za-z0-9._~+/=-]{12,}"
        ),
    ),
)
TEXT_ENCODINGS = ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be")

EXIT_OK = 0
EXIT_INTEGRITY = 1
EXIT_POLICY = 2
EXIT_REFUSED = 3
EXIT_INPUT = 4


class CompactationError(Exception):
    """An error with a stable process exit code."""

    def __init__(self, message: str, code: int = EXIT_INTEGRITY) -> None:
        super().__init__(message)
        self.code = code


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def token_count_estimate(byte_count: int) -> int:
    """Documented heuristic: ceil(UTF-8 bytes / 4). Not a model tokenizer."""
    return max(1, math.ceil(byte_count / 4)) if byte_count else 0


def token_estimate(data: bytes) -> int:
    return token_count_estimate(len(data))


def decoded_views(data: bytes) -> list[str]:
    """Return the byte views a credential could be encoded in."""
    views = [data.decode("utf-8", errors="ignore")]
    for encoding in TEXT_ENCODINGS:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text and any(char.isprintable() for char in text):
            views.append(text)
    return views


def detect_secrets(data: bytes) -> list[str]:
    found: set[str] = set()
    for text in decoded_views(data):
        found.update(name for name, pattern in SECRET_PATTERNS if pattern.search(text))
    return sorted(found)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".compactation-", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def guard_output_path(out: str, store: Store) -> Path:
    """Refuse output paths that would mutate the evidence store itself."""
    if not out or out == "-":
        raise CompactationError("--out must name a file outside the store", EXIT_INPUT)
    path = Path(out).resolve()
    root = store.root.resolve()
    if path == root or root in path.parents:
        raise CompactationError(
            "refusing to write inside the store root; --out must be external", EXIT_INPUT
        )
    return path


class Store:
    """Append-only, content-addressed evidence store."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = root / "objects"
        self.ledger = root / "ledger.jsonl"

    def init(self) -> dict[str, Any]:
        self.objects.mkdir(parents=True, exist_ok=True)
        if not self.ledger.exists():
            atomic_write(self.ledger, b"")
        return {"store": str(self.root), "status": "ready"}

    @staticmethod
    def validate_id(record_id: str) -> str:
        if not ID_RE.fullmatch(record_id):
            raise CompactationError(
                "record id must be 64 lowercase hex characters", EXIT_INPUT
            )
        return record_id

    def object_path(self, record_id: str) -> Path:
        record_id = self.validate_id(record_id)
        return self.objects / record_id[:2] / record_id

    def put_object(self, data: bytes) -> str:
        record_id = digest(data)
        path = self.object_path(record_id)
        if path.exists():
            if path.read_bytes() != data:
                raise CompactationError(
                    f"object {record_id} exists with different bytes", EXIT_INTEGRITY
                )
            return record_id
        atomic_write(path, data)
        return record_id

    def get_object(self, record_id: str) -> bytes:
        path = self.object_path(record_id)
        if not path.exists():
            raise CompactationError(
                f"object {record_id} missing from store", EXIT_INTEGRITY
            )
        data = path.read_bytes()
        if digest(data) != record_id:
            raise CompactationError(
                f"object {record_id} failed hash verification", EXIT_INTEGRITY
            )
        return data

    def events(self) -> list[dict[str, Any]]:
        """Read the ledger, failing closed on any malformed event."""
        if not self.ledger.exists():
            return []
        result: list[dict[str, Any]] = []
        for number, line in enumerate(
            self.ledger.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except (ValueError, TypeError) as exc:
                raise CompactationError(
                    f"ledger line {number} is not valid JSON", EXIT_INTEGRITY
                ) from exc
            if not isinstance(event, dict):
                raise CompactationError(
                    f"ledger line {number} is not an object", EXIT_INTEGRITY
                )
            self.validate_id(str(event.get("id", "")))
            size = event.get("bytes")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise CompactationError(
                    f"ledger line {number} has an invalid byte count", EXIT_INTEGRITY
                )
            result.append(event)
        return result

    def append(self, event: dict[str, Any]) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger, "a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0, os.SEEK_END)
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def event_hash(event: dict[str, Any], record_id: str) -> str:
    """Read a ledger hash without letting a malformed event crash the CLI."""
    value = event.get("hash", record_id)
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise CompactationError(
            f"ledger event {record_id[:12]} has an invalid hash", EXIT_INTEGRITY
        )
    return value


def load_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompactationError(f"cannot read JSON from {path}: {exc}", EXIT_INPUT) from exc


def read_source(path: str | None) -> tuple[bytes, str]:
    if path is None or path == "-":
        return sys.stdin.buffer.read(), "stdin"
    source = Path(path)
    if not source.is_file():
        raise CompactationError(f"source file not found: {path}", EXIT_INPUT)
    return source.read_bytes(), str(source)


def cmd_init(args: argparse.Namespace) -> int:
    result = Store(Path(args.store)).init()
    if not args.quiet:
        print(json.dumps(result, sort_keys=True))
    return EXIT_OK


def cmd_capture(args: argparse.Namespace) -> int:
    store = Store(Path(args.store))
    store.init()
    data, source = read_source(args.file)
    flags = detect_secrets(data)
    metadata = " ".join(
        part for part in (
            args.note or "", args.reason or "", args.kind, args.model, source
        ) if part
    )
    metadata_flags = detect_secrets(metadata.encode("utf-8"))
    all_flags = sorted(set(flags) | set(metadata_flags))
    if all_flags and not args.allow_secrets:
        raise CompactationError(
            "secret-like patterns detected (" + ", ".join(all_flags)
            + "); use --allow-secrets only with an explicit --reason",
            EXIT_REFUSED,
        )
    if args.allow_secrets and not args.reason:
        raise CompactationError(
            "--allow-secrets requires --reason", EXIT_REFUSED
        )
    record_id = digest(data)
    object_existed = store.object_path(record_id).exists()
    existing = {event["id"] for event in store.events()} if object_existed else set()
    duplicate = record_id in existing
    note = args.note or ""
    reason = args.reason or ""
    safe_kind, safe_model, safe_source = args.kind, args.model, source
    if metadata_flags:
        redaction = "[REDACTED: metadata contained secret-like bytes]"
        note = safe_kind = safe_model = safe_source = reason = redaction
    store.put_object(data)
    if not duplicate:
        store.append(
            {
                "id": record_id,
                "hash": record_id,
                "bytes": len(data),
                "kind": safe_kind,
                "model": safe_model,
                "source": safe_source,
                "note": note,
                "secret_flags": flags,
                "metadata_secret_flags": metadata_flags,
                "allow_reason": reason,
                "captured_at": now_iso(),
            }
        )
    print(
        json.dumps(
            {
                "id": record_id,
                "bytes": len(data),
                "secret_flags": all_flags,
                "duplicate": duplicate,
            },
            sort_keys=True,
        )
    )
    return EXIT_OK


def safe_redact_pattern(pattern_text: str) -> bool:
    """Accept only a conservative regex subset that cannot backtrack catastrophically.

    Catastrophic patterns in Python ``re`` pair repetition with repetition or
    alternation: ``(a+)+$``, ``(a?a?)+$``, ``(a{0,1}a{0,1})+$``, ``(a|a)+``,
    ``a+a+``. Optional and bounded quantifiers count as repetition here too;
    otherwise a guard that only counts ``*`` and ``+`` is trivially bypassed.
    A quantified group is rejected outright rather than inspecting its body:
    nested parentheses make body inspection easy to bypass (``((a|a))+$``).
    Backreferences and group extensions are rejected because they add retry
    paths that token counting cannot see (``(a+)\\1\\1$``). Policy files are
    operator-controlled, but a redaction rule is still applied to every
    captured record, so this guard bounds that risk statically.
    """
    repetition = re.compile(r"[*+?]|\{\d+(?:,\d*)?\}")
    if re.search(r"\\[1-9]|\\g<|\(\?(?!:)", pattern_text):
        return False
    for lower, upper in re.findall(r"\{(\d+)(?:,(\d*))?\}", pattern_text):
        if upper and int(upper) > 1000:
            return False
        if lower == "0" and upper == "":
            return False
    cleaned = re.sub(r"\\.", "", pattern_text)
    cleaned = re.sub(r"\[(?:\\.|[^\]])*\]", "", cleaned)
    cleaned = re.sub(r"\(\?:", "(", cleaned)
    if len(repetition.findall(cleaned)) > 1:
        return False
    depth = 0
    for index, char in enumerate(cleaned):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
            if index + 1 < len(cleaned) and cleaned[index + 1] in "*+?{":
                return False
    if depth != 0:
        return False
    if "|" in cleaned and repetition.search(cleaned):
        return False
    return True


def validate_policy(policy: Any) -> dict[str, Any]:
    if not isinstance(policy, dict) or policy.get("schema") not in POLICY_SCHEMAS:
        raise CompactationError(
            "policy must be an object with schema 'compactation/policy/0.0.2' "
            "or the legacy 'compactation/policy/0.0.1'",
            EXIT_INPUT,
        )
    for key, default in (
        ("keep_ids", []),
        ("drop_kinds", []),
        ("redact", []),
    ):
        if key in policy and not isinstance(policy[key], list):
            raise CompactationError(f"policy.{key} must be a list", EXIT_INPUT)
        policy.setdefault(key, default)
    policy.setdefault("name", "unnamed")
    policy.setdefault("dedupe", True)
    policy.setdefault("max_chars_per_record", 4000)
    policy.setdefault("max_chars_total", 20000)
    def positive_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 1

    if not positive_int(policy["max_chars_per_record"]):
        raise CompactationError("max_chars_per_record must be a positive integer", EXIT_INPUT)
    if not positive_int(policy["max_chars_total"]):
        raise CompactationError("max_chars_total must be a positive integer", EXIT_INPUT)
    for record_id in policy["keep_ids"]:
        Store.validate_id(str(record_id))
    if len(policy["redact"]) > 32:
        raise CompactationError("at most 32 redact rules are allowed", EXIT_INPUT)
    if "context_budget" in policy and not (
        isinstance(policy["context_budget"], str)
        or (
            isinstance(policy["context_budget"], int)
            and not isinstance(policy["context_budget"], bool)
        )
    ):
        raise CompactationError("policy.context_budget must be a string or integer", EXIT_INPUT)
    for rule in policy["redact"]:
        if not isinstance(rule, dict) or "pattern" not in rule or "replacement" not in rule:
            raise CompactationError(
                "each redact rule needs pattern and replacement strings", EXIT_INPUT
            )
        pattern_text = str(rule["pattern"])
        if len(pattern_text) > 256:
            raise CompactationError("redact pattern is too long", EXIT_INPUT)
        if not safe_redact_pattern(pattern_text):
            raise CompactationError(
                "redact pattern uses a nested quantifier or repeated unbounded "
                "repetition and is rejected",
                EXIT_INPUT,
            )
        try:
            re.compile(pattern_text)
        except re.error as exc:
            raise CompactationError(f"invalid redact pattern: {exc}", EXIT_INPUT) from exc
    return policy


def derive_core(
    store: Store,
    policy: dict[str, Any],
    model: str,
    context_budget: str | int,
) -> dict[str, Any]:
    """Derive the projection core from store bytes and the recorded policy.

    Both `project` and `verify` call this function. Verification therefore
    recomputes coverage and excerpts from the store instead of trusting values
    written into a projection file.
    """
    policy_hash = digest(canonical_json(policy))
    events = store.events()
    if not events:
        raise CompactationError("store has no captured records", EXIT_POLICY)

    keep_ids = set(policy["keep_ids"])
    drop_kinds = set(policy["drop_kinds"])
    seen_hashes: set[str] = set()
    records: list[dict[str, Any]] = []
    omissions: list[dict[str, Any]] = []
    redactions: list[dict[str, Any]] = []
    unresolved: list[str] = []
    captured_bytes = 0
    referenced_bytes = 0
    total_chars = 0

    for event in events:
        record_id = event["id"]
        source_bytes = event["bytes"]
        captured_bytes += source_bytes
        try:
            raw = store.get_object(record_id)
        except CompactationError:
            unresolved.append(record_id)
            omissions.append(
                {
                    "policy": "integrity",
                    "reason": "object missing or hash mismatch",
                    "ids": [record_id],
                    "bytes": source_bytes,
                }
            )
            continue
        if len(raw) != source_bytes:
            unresolved.append(record_id)
            omissions.append(
                {
                    "policy": "integrity",
                    "reason": "record byte count differs from stored object",
                    "ids": [record_id],
                    "bytes": source_bytes,
                }
            )
            continue
        source_hash = event_hash(event, record_id)
        record_omissions: list[dict[str, Any]] = []

        if record_id in keep_ids:
            pass
        elif event.get("kind") in drop_kinds:
            omissions.append(
                {
                    "policy": "drop_kinds",
                    "reason": f"kind {event.get('kind')} excluded by policy",
                    "ids": [record_id],
                    "bytes": source_bytes,
                }
            )
            continue
        elif policy["dedupe"] and source_hash in seen_hashes:
            omissions.append(
                {
                    "policy": "dedupe",
                    "reason": "identical content hash already referenced",
                    "ids": [record_id],
                    "bytes": source_bytes,
                }
            )
            continue

        text = raw.decode("utf-8", errors="replace")
        effective_bytes = len(text.encode("utf-8"))
        if effective_bytes > source_bytes:
            unresolved.append(record_id)
            omissions.append(
                {
                    "policy": "decode",
                    "reason": "invalid UTF-8 expands on replacement",
                    "ids": [record_id],
                    "bytes": source_bytes,
                }
            )
            continue
        if effective_bytes < source_bytes:
            record_omissions.append(
                {
                    "policy": "decode",
                    "reason": "invalid UTF-8 bytes replaced before projection",
                    "ids": [record_id],
                    "bytes": source_bytes - effective_bytes,
                }
            )

        for index, rule in enumerate(policy["redact"]):
            pattern = re.compile(str(rule["pattern"]))
            replacement = str(rule["replacement"])
            count = len(pattern.findall(text))
            if count:
                before_len = len(text.encode("utf-8"))
                text = pattern.sub(lambda _match: replacement, text)
                after_len = len(text.encode("utf-8"))
                if after_len > before_len:
                    raise CompactationError(
                        f"redact[{index}] expands bytes; use a shorter replacement",
                        EXIT_POLICY,
                    )
                if before_len > after_len:
                    record_omissions.append(
                        {
                            "policy": "redaction",
                            "reason": f"redact[{index}] shortened matching bytes",
                            "ids": [record_id],
                            "bytes": before_len - after_len,
                        }
                    )
                redactions.append({"pattern": f"redact[{index}]", "count": count})

        if policy["dedupe"]:
            seen_lines: set[str] = set()
            kept_lines: list[str] = []
            duplicate_bytes = 0
            for line in text.splitlines(keepends=True):
                key = line.strip()
                if key and key in seen_lines:
                    duplicate_bytes += len(line.encode("utf-8"))
                else:
                    seen_lines.add(key)
                    kept_lines.append(line)
            if duplicate_bytes:
                text = "".join(kept_lines)
                record_omissions.append(
                    {
                        "policy": "dedupe",
                        "reason": "repeated line collapsed within record",
                        "ids": [record_id],
                        "bytes": duplicate_bytes,
                    }
                )

        limit = policy["max_chars_per_record"]
        if total_chars + min(len(text), limit) > policy["max_chars_total"]:
            # A record skipped by the total cap must not also contribute
            # earlier per-record omissions, or its bytes are counted twice.
            omissions.append(
                {
                    "policy": "total_bounds",
                    "reason": "record exceeded total projected character budget",
                    "ids": [record_id],
                    "bytes": source_bytes,
                }
            )
            continue

        # Only a record that actually reaches the projection marks its hash as
        # seen; a record skipped by the total cap is not a dedupe ancestor.
        seen_hashes.add(source_hash)
        omissions.extend(record_omissions)
        excerpt = text[:limit] if len(text) > limit else text
        if len(excerpt) < len(text):
            omitted_byte_count = len(text.encode("utf-8")) - len(excerpt.encode("utf-8"))
            omissions.append(
                {
                    "policy": "bounds",
                    "reason": "record truncated at max_chars_per_record",
                    "ids": [record_id],
                    "bytes": max(0, omitted_byte_count),
                }
            )

        referenced_bytes += len(excerpt.encode("utf-8"))
        total_chars += len(excerpt)
        records.append(
            {
                "id": record_id,
                "hash": source_hash,
                "role": event.get("kind", "record"),
                "span": {
                    "start": 0,
                    "end": len(excerpt.encode("utf-8")),
                    "total": len(text.encode("utf-8")),
                },
                "excerpt": excerpt,
                "excerpt_hash": digest(excerpt.encode("utf-8")),
            }
        )

    omitted_bytes = sum(int(item["bytes"]) for item in omissions)
    balanced = captured_bytes == referenced_bytes + omitted_bytes
    estimator = "utf8_bytes_over_4"
    before = token_estimate(b"".join(
        store.get_object(e["id"]) for e in events if safe_object_exists(store, e["id"])
    ))
    after = token_estimate("".join(r["excerpt"] for r in records).encode("utf-8"))
    savings = round((1 - after / before) * 100, 2) if before else 0.0

    return {
        "policy": policy["name"],
        "policy_hash": policy_hash,
        "model": model,
        "estimator": estimator,
        "context_budget": context_budget,
        "budget_enforced": False,
        "records": records,
        "omissions": omissions,
        "redactions": redactions,
        "unresolved": unresolved,
        "coverage": {
            "captured_bytes": captured_bytes,
            "referenced_bytes": referenced_bytes,
            "declared_omitted_bytes": omitted_bytes,
            "balanced": balanced,
        },
        "token_estimate": {
            "before": before,
            "after": after,
            "saved_percent": savings,
            "is_estimate": True,
        },
        "exit_reason": (
            "stall" if unresolved or not balanced
            else "budget" if any(o["policy"] == "total_bounds" for o in omissions)
            else "green"
        ),
        "policy_object": policy,
    }


def cmd_project(args: argparse.Namespace) -> int:
    store = Store(Path(args.store))
    policy = validate_policy(load_json(args.policy))
    context_budget = args.context_budget or policy.get("context_budget", "advisory-unknown")
    core = derive_core(store, policy, args.model, context_budget)
    projection = {
        "schema": SCHEMA,
        "id": digest(canonical_json(core)),
        "created_at": now_iso(),
        "core": core,
        "validation_status": "unvalidated",
    }
    payload = canonical_json(projection) + b"\n"
    if args.out and args.out != "-":
        out = guard_output_path(args.out, store)
        atomic_write(out, payload)
        print(json.dumps({"projection": str(out), "id": projection["id"]}))
    else:
        sys.stdout.buffer.write(payload)
    return EXIT_OK if core["exit_reason"] in ("green", "budget") else EXIT_POLICY


def safe_object_exists(store: Store, record_id: str) -> bool:
    try:
        store.get_object(record_id)
        return True
    except CompactationError:
        return False


def projection_core(projection: Any) -> dict[str, Any]:
    core = projection.get("core") if isinstance(projection, dict) else None
    if not isinstance(core, dict):
        raise CompactationError("projection has no core object", EXIT_INPUT)
    return core


def verify_projection(
    store: Store, projection: Any
) -> tuple[bool, list[dict[str, Any]], bool, bool]:
    """Recompute all checks from store bytes; return (passed, checks, identity_ok, derived_ok)."""
    core = projection_core(projection)
    checks: list[dict[str, Any]] = []
    passed = True

    identity_ok = digest(canonical_json(core)) == projection.get("id")
    checks.append({"check": "projection_id", "pass": identity_ok})
    passed &= identity_ok

    policy_object = core.get("policy_object")
    derived_ok = False
    if isinstance(policy_object, dict):
        try:
            copied_policy = json.loads(json.dumps(policy_object))
            derived = derive_core(
                store,
                validate_policy(copied_policy),
                str(core.get("model", "")),
                core.get("context_budget", "advisory-unknown"),
            )
            derived_ok = canonical_json(derived) == canonical_json(core)
        except (CompactationError, ValueError, TypeError, KeyError, AttributeError):
            derived_ok = False
    checks.append({"check": "derived_from_store_and_policy", "pass": derived_ok})
    passed &= derived_ok

    records = core.get("records", [])
    if not isinstance(records, list):
        checks.append({"check": "records_well_formed", "pass": False})
        passed = False
        records = []
    for record in records:
        if not isinstance(record, dict):
            checks.append({"check": "records_well_formed", "pass": False})
            passed = False
            continue
        record_id = str(record.get("id", ""))
        try:
            raw = store.get_object(record_id)
            object_ok = digest(raw) == record.get("hash")
            excerpt_ok = (
                digest(str(record.get("excerpt", "")).encode("utf-8"))
                == record.get("excerpt_hash")
            )
            ok = object_ok and excerpt_ok
        except (CompactationError, ValueError, TypeError, AttributeError):
            ok = False
        checks.append({"check": f"reference:{record_id[:12]}", "pass": ok})
        passed &= ok

    coverage = core.get("coverage", {})
    if not isinstance(coverage, dict):
        coverage = {}
    balanced = (
        coverage.get("captured_bytes")
        == coverage.get("referenced_bytes", 0)
        + coverage.get("declared_omitted_bytes", 0)
    )
    checks.append({"check": "coverage_arithmetic", "pass": bool(balanced)})
    passed &= bool(balanced)

    unresolved_ok = not core.get("unresolved")
    checks.append({"check": "references_resolved", "pass": unresolved_ok})
    passed &= unresolved_ok

    return bool(passed), checks, identity_ok, derived_ok


def cmd_verify(args: argparse.Namespace) -> int:
    store = Store(Path(args.store))
    try:
        projection = load_json(args.projection)
        passed, checks, _identity_ok, _derived_ok = verify_projection(store, projection)
    except CompactationError as exc:
        print(
            json.dumps(
                {
                    "pass": False,
                    "checks": [{"check": "projection_readable", "pass": False}],
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return EXIT_INTEGRITY
    print(json.dumps({"pass": passed, "checks": checks}, sort_keys=True))
    return EXIT_OK if passed else EXIT_INTEGRITY


def cmd_retrieve(args: argparse.Namespace) -> int:
    store = Store(Path(args.store))
    data = store.get_object(args.id)
    if args.out and args.out != "-":
        out = guard_output_path(args.out, store)
        atomic_write(out, data)
        print(
            json.dumps(
                {"id": args.id, "bytes": len(data), "out": str(out)}, sort_keys=True
            )
        )
    else:
        sys.stdout.buffer.write(data)
    return EXIT_OK


def cmd_ledger(args: argparse.Namespace) -> int:
    for event in Store(Path(args.store)).events():
        print(json.dumps(event, sort_keys=True))
    return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    """Render the stable report shape defined in COMPACTATION.md."""
    store = Store(Path(args.store))
    projection = load_json(args.projection)
    core = projection_core(projection)
    try:
        passed, _checks, identity_ok, derived_ok = verify_projection(store, projection)
    except CompactationError as exc:
        raise CompactationError(
            f"cannot verify projection for report: {exc}", EXIT_INTEGRITY
        ) from exc
    if not identity_ok or not derived_ok:
        raise CompactationError(
            "projection failed identity/derivation verification; refusing to report",
            EXIT_INTEGRITY,
        )
    claims = load_json(args.claims)
    if not isinstance(claims, list):
        raise CompactationError("claims must be a JSON list", EXIT_INPUT)

    available = {record["id"]: record for record in core.get("records", [])}
    coverage = core.get("coverage", {})
    estimate = core.get("token_estimate", {})
    records = core.get("records", [])
    omissions = core.get("omissions", [])
    redactions = core.get("redactions", [])

    lines: list[str] = [
        f"## Compactation - {args.scope} ({datetime.now(timezone.utc).date()})",
        "",
        f"Model: {core.get('model')} · Estimator: {core.get('estimator')} · "
        f"Policy: {core.get('policy')} · Status: {core.get('exit_reason', 'stall')}",
        "",
        f"Projection: {projection.get('id')}",
        "Coverage: "
        f"{coverage.get('captured_bytes', 0)} = "
        f"{coverage.get('referenced_bytes', 0)} + "
        f"{coverage.get('declared_omitted_bytes', 0)}",
        "Records: "
        + (", ".join(
            f"{str(record.get('id', ''))[:16]}:{record.get('role')} "
            f"({record.get('span', {}).get('end', 0)} bytes)"
            for record in records
        ) if records else "none"),
        "Omitted: "
        + (" ; ".join(
            f"{item.get('policy')} - {item.get('reason')} - "
            f"{','.join(str(rid)[:16] for rid in item.get('ids', []))} - "
            f"{item.get('bytes', 0)} bytes"
            for item in omissions
        ) if omissions else "none"),
        "Redactions: "
        + (" ; ".join(
            f"{item.get('pattern')} - {item.get('count')}" for item in redactions
        ) if redactions else "none"),
        f"Token estimate: {estimate.get('before', 0)} -> {estimate.get('after', 0)} "
        f"({estimate.get('saved_percent', 0)} percent saved, estimate only)",
        "",
    ]

    all_cited = True
    integrity = "verified" if passed else "invalidated and re-derived"
    rehydrated: list[str] = []
    verbatim: list[str] = []
    unverified: list[str] = []

    for index, claim in enumerate(claims, start=1):
        statement = claim.get("claim") if isinstance(claim, dict) else None
        ids = claim.get("record_ids", []) if isinstance(claim, dict) else []
        if not statement or not isinstance(ids, list):
            unverified.append(f"{index}. UNVERIFIED - malformed claim entry")
            all_cited = False
            continue
        valid_ids = [rid for rid in ids if isinstance(rid, str) and rid in available]
        if not valid_ids:
            unverified.append(
                f"{index}. UNVERIFIED - {statement} - no cited record in projection"
            )
            all_cited = False
            continue
        for record_id in valid_ids:
            try:
                raw = store.get_object(record_id)
            except CompactationError:
                unverified.append(
                    f"{index}. UNVERIFIED - {statement} - record {record_id[:16]} unavailable"
                )
                integrity = "invalidated and re-derived"
                all_cited = False
                continue
            if digest(raw) != available[record_id].get("hash"):
                unverified.append(
                    f"{index}. UNVERIFIED - {statement} - integrity failure on {record_id[:16]}"
                )
                integrity = "invalidated and re-derived"
                all_cited = False
                continue
            rehydrated.append(record_id[:16])
            excerpt = raw.decode("utf-8", errors="replace")[:500]
            verbatim.extend([
                f"### {record_id[:16]}",
                "```text",
                *excerpt.splitlines(),
                "```",
                "",
            ])

    for record_id in core.get("unresolved", []):
        unverified.append(f"unresolved reference {str(record_id)[:16]} - not used as evidence")

    lines.append(
        "Rehydrated for decisions: "
        + (", ".join(dict.fromkeys(rehydrated)) if rehydrated else "none")
    )
    lines.append(f"Integrity: {integrity}")
    lines.append("UNVERIFIED: " + (" ; ".join(unverified) if unverified else "none"))
    lines.append("")
    lines.append("Validation status: unvalidated (see docs/VALIDATION.md)")
    lines.append("")
    if verbatim:
        lines.append("### Verbatim rehydrated evidence")
        lines.append("")
        lines.extend(verbatim)

    payload = "\n".join(lines).encode("utf-8")
    if args.out and args.out != "-":
        out = guard_output_path(args.out, store)
        atomic_write(out, payload)
        print(json.dumps({"report": str(out), "all_claims_cited": all_cited}))
    else:
        sys.stdout.buffer.write(payload)
    if integrity != "verified":
        return EXIT_INTEGRITY
    return EXIT_OK if all_cited else EXIT_POLICY


def cmd_estimate(args: argparse.Namespace) -> int:
    total_before = 0
    for name in args.files:
        data, _source = read_source(name)
        total_before += len(data)
    print(
        json.dumps(
            {
                "estimator": "utf8_bytes_over_4",
                "bytes": total_before,
                "estimated_tokens": token_count_estimate(total_before),
                "is_estimate": True,
            },
            sort_keys=True,
        )
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compactation",
        description="Content-addressed evidence ledger for agent compactation strategy.",
    )
    parser.add_argument("--version", action="version", version=f"compactation {VERSION}")
    parser.add_argument(
        "--store",
        default=os.environ.get("COMPACTATION_STORE", ".compactation"),
        help="store directory (default: .compactation or COMPACTATION_STORE)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a store without destroying one")
    p_init.add_argument("--quiet", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_capture = sub.add_parser("capture", help="store immutable evidence bytes")
    p_capture.add_argument("--file", help="file to capture, or - for stdin")
    p_capture.add_argument("--kind", default="log")
    p_capture.add_argument("--model", default="unspecified")
    p_capture.add_argument("--note", default="")
    p_capture.add_argument("--allow-secrets", action="store_true")
    p_capture.add_argument("--reason", default="")
    p_capture.set_defaults(func=cmd_capture)

    p_project = sub.add_parser("project", help="derive a compact projection")
    p_project.add_argument("--policy", required=True)
    p_project.add_argument("--out", default="-")
    p_project.add_argument("--model", default="unspecified")
    p_project.add_argument(
        "--context-budget",
        default="",
        help="declared context budget; advisory unless a runtime enforces it",
    )
    p_project.set_defaults(func=cmd_project)

    p_verify = sub.add_parser("verify", help="verify hashes, references, coverage")
    p_verify.add_argument("--projection", required=True)
    p_verify.set_defaults(func=cmd_verify)

    p_retrieve = sub.add_parser("retrieve", help="restore verbatim bytes by ID")
    p_retrieve.add_argument("--id", required=True)
    p_retrieve.add_argument("--out", default="-")
    p_retrieve.set_defaults(func=cmd_retrieve)

    p_ledger = sub.add_parser("ledger", help="print the append-only event ledger")
    p_ledger.set_defaults(func=cmd_ledger)

    p_report = sub.add_parser("report", help="render a provenance report")
    p_report.add_argument("--projection", required=True)
    p_report.add_argument("--claims", required=True)
    p_report.add_argument("--scope", default="session")
    p_report.add_argument("--out", default="-")
    p_report.set_defaults(func=cmd_report)

    p_estimate = sub.add_parser("estimate", help="estimate tokens with the named heuristic")
    p_estimate.add_argument("files", nargs="+")
    p_estimate.set_defaults(func=cmd_estimate)

    # Accept --store on either side of the subcommand. SUPPRESS keeps the
    # top-level value when the subcommand form is not used.
    for subparser in sub.choices.values():
        subparser.add_argument(
            "--store",
            default=argparse.SUPPRESS,
            help="store directory (default: .compactation or COMPACTATION_STORE)",
        )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except CompactationError as exc:
        print(f"compactation: {exc}", file=sys.stderr)
        return exc.code
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"compactation: malformed input or store: {exc}", file=sys.stderr)
        return EXIT_INTEGRITY


if __name__ == "__main__":
    raise SystemExit(main())
