# usb_toolkit.core.audit
#
# Append-only, tamper-evident event log.
#
# Each record is one JSON object on its own line (JSON Lines). Every record
# carries prev_hash and hash, where:
#
#     hash = SHA-256( prev_hash + canonical_json(payload) )
#
# and the first record's prev_hash is 64 zeros (genesis). Any insertion,
# deletion, reordering or edit breaks the chain and is caught by verify().
#
# This replaces the original logger, which json.dump'd a fresh array on every
# event and produced a file no JSON parser could load.
#
# Durability: each append is flushed and fsync'd. Compaction/rewrite (rare)
# goes through a temp file + atomic os.replace so a crash never corrupts the log.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

GENESIS = "0" * 64


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _chain_hash(prev_hash: str, payload: dict) -> str:
    data = (prev_hash + _canonical(payload)).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    records: int
    broken_line: Optional[int] = None
    reason: str = ""


class AuditLog:
    """A chain-hashed JSONL event log."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- reading ------------------------------------------------------------

    def _last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS
        last = GENESIS
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    last = rec.get("hash", last)
                except json.JSONDecodeError:
                    # Stop at first unreadable line; append() will chain from
                    # the last good hash rather than silently forking.
                    break
        return last

    def records(self) -> list[dict]:
        out: list[dict] = []
        if not self.path.exists():
            return out
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
        return out

    # -- writing ------------------------------------------------------------

    def append(self, payload: dict) -> str:
        """Append one record, returning its hash. Flushed + fsync'd."""
        prev = self._last_hash()
        this_hash = _chain_hash(prev, payload)
        record = {"prev_hash": prev, "payload": payload, "hash": this_hash}
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        return this_hash

    # -- integrity ----------------------------------------------------------

    def verify(self) -> VerifyResult:
        """Recompute the whole chain and confirm it is intact."""
        prev = GENESIS
        count = 0
        if not self.path.exists():
            return VerifyResult(True, 0)
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    return VerifyResult(False, count, lineno, "malformed JSON")
                if rec.get("prev_hash") != prev:
                    return VerifyResult(False, count, lineno, "prev_hash mismatch")
                expected = _chain_hash(prev, rec.get("payload", {}))
                if rec.get("hash") != expected:
                    return VerifyResult(False, count, lineno, "hash mismatch")
                prev = rec["hash"]
                count += 1
        return VerifyResult(True, count)

    def compact(self, keep: Iterable[dict]) -> None:
        """Atomically rewrite the log from a fresh payload sequence.

        Used only for deliberate maintenance (e.g. trimming). Rebuilds a valid
        chain from genesis via temp file + os.replace so a crash mid-write
        cannot leave a partial log in place.
        """
        prev = GENESIS
        lines: list[str] = []
        for payload in keep:
            this_hash = _chain_hash(prev, payload)
            lines.append(json.dumps({"prev_hash": prev, "payload": payload, "hash": this_hash}, ensure_ascii=False))
            prev = this_hash
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
                if lines:
                    fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
