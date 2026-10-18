#!/usr/bin/env python3
"""
Mnemosyne Core Engine — Deterministic CLI-First FSRS-4.5 & Zettelkasten Study Engine.

Implements RFC-MNEMOSYNE-CORE-001 (v1.1.0) and PRD-MNEMOSYNE-CORE-001 (v1.1.0).
Air-gapped Python 3.10+ standard-library-only engine structured into 8 strict LLD layers:
  Section 0 — Domain Exceptions & Value Objects
  Section 1 — VaultGate (Security, Sanctuary & Path Boundary)
  Section 2 — LockMgr & StateStore (POSIX PID Mutex, Atomic I/O & OCC)
  Section 3 — DAGEngine (Kahn's O(V+E) Topo-Sort, Prerequisite Propagation & OPT-02 Frontier Probe)
  Section 4 — FSRSEngine (Exact 17-Weight FSRS-4.5, Coordinate-Search Refit & OPT-01 sync-sr Bridge)
  Section 5 — StashEngine (Claim-Check SHA-256 & Zero-Context Assessor Isolation)
  Section 6 — ASTEval (Restricted Math Verifier, OPT-03 Cached Vector & 5-Slip Diagnosis)
  Section 7 — MDCompiler (SEC-YAML-01 Span-Preserving YAML Patcher, OCC Managed Blocks & MoC)
  Section 8 — CLIGate & Selftest (>= 350 Deterministic Assertions in Isolated Tempdirs)
"""

import argparse
import ast
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import hashlib
import html
import json
import math
import os
from pathlib import Path
import random
import re
import shlex
import statistics
import sys
import tempfile
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union
import unicodedata
import uuid

# ==============================================================================
# SECTION 0 — DOMAIN EXCEPTIONS & VALUE OBJECTS
# ==============================================================================

ENGINE_VERSION = "1.0.0"
SCHEMA_VERSION = 1

ALLOWED_STDLIB_IMPORTS: Tuple[str, ...] = (
    "argparse",
    "ast",
    "dataclasses",
    "datetime",
    "enum",
    "hashlib",
    "html",
    "json",
    "math",
    "os",
    "pathlib",
    "random",
    "re",
    "shlex",
    "statistics",
    "sys",
    "tempfile",
    "time",
    "typing",
    "unicodedata",
    "uuid",
)

FORBIDDEN_AST_CALLS: Tuple[str, ...] = (
    "eval",
    "exec",
    "compile",
    "__import__",
    "system",
    "popen",
)


class ExitCode(int, Enum):
    OK = 0
    VALIDATION_ERROR = 1
    SANCTUARY_VIOLATION = 2
    CONCURRENCY_OR_CORRUPTION = 3


class MnemosyneError(Exception):
    """Base domain exception mapped deterministically to CLI exit codes 1, 2, or 3."""

    exit_code: int = ExitCode.VALIDATION_ERROR

    def __init__(
        self,
        message: str,
        *,
        exit_code: Optional[int] = None,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if exit_code is not None:
            self.exit_code = int(exit_code)
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ok": False,
            "error": self.__class__.__name__,
            "exit_code": self.exit_code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class ValidationError(MnemosyneError):
    """Exit code 1: Domain, schema, DAG cycle, rubric, or receipt validation failure."""

    exit_code = ExitCode.VALIDATION_ERROR


class SanctuaryViolationError(MnemosyneError):
    """Exit code 2: Sanctuary violation (05 - Fleeting, .git, .obsidian, traversal, allowlist)."""

    exit_code = ExitCode.SANCTUARY_VIOLATION


class ConcurrencyOrCorruptionError(MnemosyneError):
    """Exit code 3: Lock timeout, malformed YAML frontmatter, or missing managed-block markers."""

    exit_code = ExitCode.CONCURRENCY_OR_CORRUPTION


@dataclass(frozen=True)
class FSRSState:
    s: Optional[float] = None
    d: Optional[float] = None
    due: Optional[str] = None
    last: Optional[str] = None
    interval: int = 0
    reps: int = 0
    lapses: int = 0
    relearn_step: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "s": round(self.s, 4) if self.s is not None else None,
            "d": round(self.d, 4) if self.d is not None else None,
            "due": self.due,
            "last": self.last,
            "interval": int(self.interval),
            "reps": int(self.reps),
            "lapses": int(self.lapses),
            "relearn_step": int(self.relearn_step),
        }

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]]) -> "FSRSState":
        if not isinstance(raw, dict):
            return cls()
        s_val = as_finite_float(raw.get("s"))
        d_val = as_finite_float(raw.get("d"))
        due_val = raw.get("due") if isinstance(raw.get("due"), str) else None
        last_val = raw.get("last") if isinstance(raw.get("last"), str) else None
        ivl_val = int(as_finite_float(raw.get("interval"), 0.0) or 0)
        reps_val = max(0, int(as_finite_float(raw.get("reps"), 0.0) or 0))
        lapses_val = max(0, int(as_finite_float(raw.get("lapses"), 0.0) or 0))
        relearn_val = max(0, int(as_finite_float(raw.get("relearn_step"), 0.0) or 0))
        return cls(
            s=s_val,
            d=d_val,
            due=due_val,
            last=last_val,
            interval=ivl_val,
            reps=reps_val,
            lapses=lapses_val,
            relearn_step=relearn_val,
        )


@dataclass(frozen=True)
class SRFrontmatter:
    sr_due: str
    sr_interval: int
    sr_ease: int
    mnemosyne_sid: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sr-due": self.sr_due,
            "sr-interval": int(self.sr_interval),
            "sr-ease": int(self.sr_ease),
            "mnemosyne_sid": self.mnemosyne_sid,
        }


@dataclass(frozen=True)
class StashRecord:
    sid: str
    captured_at: str
    topic: str
    node: str
    event_kind: str
    node_kind: str
    claim: str
    probe: str
    rubric: Tuple[str, ...]
    production: str
    production_clipped: bool
    confidence: Optional[int]
    hint_used: int
    stash_sha256: str
    produced: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sid": self.sid,
            "captured_at": self.captured_at,
            "topic": self.topic,
            "node": self.node,
            "kind": self.event_kind,
            "event_kind": self.event_kind,
            "node_kind": self.node_kind,
            "claim": self.claim,
            "probe": self.probe,
            "rubric": list(self.rubric),
            "production": self.production,
            "produced": self.produced,
            "production_clipped": self.production_clipped,
            "confidence": self.confidence,
            "hint_used": self.hint_used,
            "stash_sha256": self.stash_sha256,
        }


@dataclass(frozen=True)
class AssessorEnvelope:
    sid: str
    stash_sha256: str
    topic: str
    node: str
    kind: str
    event_kind: str
    node_kind: str
    claim: str
    probe: str
    rubric: Tuple[str, ...]
    production: str
    production_clipped: bool
    confidence: Optional[int]
    produced: bool = True

    def to_dict(self) -> Dict[str, Any]:
        # Strict zero-context whitelist: never includes FSRS state or conversation history
        return {
            "sid": self.sid,
            "stash_sha256": self.stash_sha256,
            "topic": self.topic,
            "node": self.node,
            "kind": self.kind,
            "event_kind": self.event_kind,
            "node_kind": self.node_kind,
            "claim": self.claim,
            "probe": self.probe,
            "rubric": list(self.rubric),
            "production": self.production,
            "produced": self.produced,
            "production_clipped": self.production_clipped,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ReceiptRecord:
    id: str
    sid: str
    stash_sha256: str
    ts: str
    captured_at: str
    settled_at: str
    source: str
    topic: str
    node: str
    kind: str
    node_kind: str
    grade: str
    rating: str
    score: int
    produced: bool
    confidence: Optional[int]
    error_class: Optional[str]
    criteria_met: Tuple[bool, ...]
    probe_gap: Tuple[int, ...]
    misconceptions: Tuple[str, ...]
    production: str
    rationale: str
    fsrs_transition: Dict[str, Any]
    artifact_present: bool
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sid": self.sid,
            "stash_sha256": self.stash_sha256,
            "ts": self.ts,
            "captured_at": self.captured_at,
            "settled_at": self.settled_at,
            "source": self.source,
            "topic": self.topic,
            "node": self.node,
            "kind": self.kind,
            "node_kind": self.node_kind,
            "grade": self.grade,
            "rating": self.rating,
            "score": self.score,
            "produced": self.produced,
            "confidence": self.confidence,
            "error_class": self.error_class,
            "criteria_met": list(self.criteria_met),
            "probe_gap": list(self.probe_gap),
            "misconceptions": list(self.misconceptions),
            "production": self.production,
            "rationale": self.rationale,
            "fsrs_transition": dict(self.fsrs_transition),
            "artifact_present": self.artifact_present,
            "engine_version": self.engine_version,
        }


@dataclass(frozen=True)
class NoteEnvelope:
    note_path: str
    body_hash: str
    st_mtime_ns: int
    st_size: int
    status: str = "permanent"
    fleeting_path: Optional[str] = None
    conflict_snapshot: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "note_path": self.note_path,
            "status": self.status,
            "body_hash": self.body_hash,
            "st_mtime_ns": int(self.st_mtime_ns),
            "st_size": int(self.st_size),
        }
        if self.fleeting_path:
            d["fleeting_path"] = self.fleeting_path
        if self.conflict_snapshot:
            d["conflict_snapshot"] = self.conflict_snapshot
        return d


@dataclass(frozen=True)
class VerifyExprReport:
    expected: str
    actual: str
    variables: Tuple[str, ...]
    equivalent: bool
    slip_candidate: bool
    slip_kind: Optional[str]
    error_class_hint: Optional[str]
    max_abs_error: float
    max_rel_error: float
    points_tested: int
    runtime_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "expected": self.expected,
            "actual": self.actual,
            "variables": list(self.variables),
            "equivalent": self.equivalent,
            "slip_candidate": self.slip_candidate,
            "slip_kind": self.slip_kind,
            "error_class_hint": self.error_class_hint,
            "max_abs_error": round(self.max_abs_error, 12),
            "max_rel_error": round(self.max_rel_error, 12),
            "points_tested": self.points_tested,
            "runtime_ms": round(self.runtime_ms, 3),
        }


# ------------------------------------------------------------------------------
# Common Pure Utilities
# ------------------------------------------------------------------------------

def as_finite_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    if isinstance(x, bool) or x is None:
        return default
    if isinstance(x, (int, float)):
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    if isinstance(x, str):
        try:
            v = float(x.strip())
            if math.isnan(v) or math.isinf(v):
                return default
            return v
        except ValueError:
            return default
    return default


def clamp_num(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def current_date() -> date:
    env_today = os.environ.get("MNEMOSYNE_TODAY")
    if env_today:
        try:
            return date.fromisoformat(env_today.strip()[:10])
        except ValueError as exc:
            raise ValidationError(f"Invalid MNEMOSYNE_TODAY={env_today!r}: {exc}") from exc
    return date.today()


def current_iso_timestamp() -> str:
    env_today = os.environ.get("MNEMOSYNE_TODAY")
    if env_today:
        d = current_date()
        return f"{d.isoformat()}T12:00:00Z"
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_date(s: Any) -> Optional[date]:
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except ValueError:
        return None


# ==============================================================================
# SECTION 1 — VAULTGATE (SECURITY, SANCTUARY & PATH BOUNDARY)
# ==============================================================================

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SANCTUARY_PARTS = frozenset({"05 - fleeting", ".git", ".obsidian"})
_ILLEGAL_FILENAME_CHARS_RE = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

WRITE_ALLOWLIST_PREFIXES: Tuple[str, ...] = (
    "00 - Maps of Content",
    "02 - Areas",
    "04 - Permanent",
    "05 - Fleeting/mnemosyne",
    "99 - Meta/attachments",
    "99 - Meta/mnemosyne-state",
)

READ_ALLOWLIST_PREFIXES: Tuple[str, ...] = (
    "00 - Maps of Content",
    "02 - Areas",
    "04 - Permanent",
    "05 - Fleeting/mnemosyne",
    "99 - Meta/attachments",
    "99 - Meta/mnemosyne-state",
    "99 - Meta/00 - Templates",
)

REQUIRED_CSP_DIRECTIVES: Tuple[str, ...] = (
    "default-src 'none'",
    "connect-src 'none'",
)


class VaultGate:
    """Single security boundary enforcing Sanctuary exclusions (Exit Code 2) and path containment."""

    DEFAULT_HOST_VAULT = Path("/home/ozymandias/GoogleDrive/Obsidian/Vault")

    def __init__(
        self,
        vault_override: Optional[Union[str, Path]] = None,
        state_override: Optional[Union[str, Path]] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parent.parent).resolve()
        self.vault_root, self.is_canonical_vault = self._resolve_vault(vault_override)
        self.state_dir, self.mirror_state_dir = self._resolve_state_dirs(state_override)

    def _resolve_vault(self, vault_override: Optional[Union[str, Path]]) -> Tuple[Path, bool]:
        raw_override = vault_override or os.environ.get("MNEMOSYNE_VAULT_PATH")
        if raw_override:
            p = Path(str(raw_override)).expanduser()
            self._check_parts_for_sanctuary(p)
            resolved = p.resolve(strict=False)
            self._check_parts_for_sanctuary(resolved)
            if (resolved / "Vault" / "00 - Maps of Content").is_dir():
                resolved = (resolved / "Vault").resolve(strict=False)
            is_canon = resolved == self.DEFAULT_HOST_VAULT.resolve(strict=False) or (
                resolved == (self.repo_root / "vault" / "Vault").resolve(strict=False)
            )
            return resolved, is_canon

        # Priority 2: /home/ozymandias/GoogleDrive/Obsidian/Vault
        host_vault = self.DEFAULT_HOST_VAULT
        if (host_vault / "Vault" / "00 - Maps of Content").is_dir():
            return (host_vault / "Vault").resolve(strict=False), True
        if host_vault.is_dir():
            return host_vault.resolve(strict=False), True

        # Priority 3: <repo>/vault/Vault
        sub_vault = self.repo_root / "vault" / "Vault"
        if sub_vault.is_dir():
            return sub_vault.resolve(strict=False), True

        return (self.repo_root / "vault" / "Vault").resolve(strict=False), False

    def _resolve_state_dirs(
        self, state_override: Optional[Union[str, Path]]
    ) -> Tuple[Path, Optional[Path]]:
        raw_state = state_override or os.environ.get("MNEMOSYNE_STATE_DIR")
        if raw_state:
            sp = Path(str(raw_state)).expanduser()
            self._check_parts_for_sanctuary(sp)
            resolved_sp = sp.resolve(strict=False)
            self._check_parts_for_sanctuary(resolved_sp)
            return resolved_sp, None

        canon_state = self.vault_root / "99 - Meta" / "mnemosyne-state"
        mirror_dir: Optional[Path] = None
        if self.is_canonical_vault:
            mirror_dir = (self.repo_root / "state").resolve(strict=False)
        return canon_state, mirror_dir

    @staticmethod
    def _normalize_part(part: str) -> str:
        return unicodedata.normalize("NFC", part).strip().rstrip(".").strip().lower()

    @classmethod
    def _check_parts_for_sanctuary(cls, path_obj: Path) -> None:
        parts = path_obj.parts
        for idx, part in enumerate(parts):
            norm = cls._normalize_part(part)
            if norm in (".git", ".obsidian"):
                raise SanctuaryViolationError(
                    f"SANCTUARY VIOLATION: Access to {part!r} is strictly forbidden (Exit Code 2).",
                    details={"violating_path": str(path_obj), "component": part},
                )
            if norm == "05 - fleeting":
                next_part = parts[idx + 1] if (idx + 1) < len(parts) else ""
                if part.strip() != "05 - Fleeting" or next_part.strip() != "mnemosyne":
                    raise SanctuaryViolationError(
                        f"SANCTUARY VIOLATION: Access to {part!r} outside '05 - Fleeting/mnemosyne' is strictly forbidden (Exit Code 2).",
                        details={"violating_path": str(path_obj), "component": part, "subcomponent": next_part},
                    )

    @staticmethod
    def _is_subpath(child: Path, parent: Path) -> bool:
        try:
            return child.is_relative_to(parent)
        except ValueError:
            return False

    def _enforce_vault_allowlist(self, resolved_target: Path, mode: str) -> None:
        rel = resolved_target.relative_to(self.vault_root)
        rel_posix = rel.as_posix()
        allowed = WRITE_ALLOWLIST_PREFIXES if mode == "w" else READ_ALLOWLIST_PREFIXES
        for prefix in allowed:
            if rel_posix == prefix or rel_posix.startswith(prefix + "/"):
                return
        raise SanctuaryViolationError(
            f"VAULT ALLOWLIST VIOLATION: {mode.upper()} operation on {rel_posix!r} is outside allowlisted vault directories.",
            details={"path": str(resolved_target), "relative": rel_posix, "mode": mode},
        )

    def validate_path(
        self,
        target_path: Union[str, Path],
        mode: str = "r",
        *,
        require_in_vault: bool = False,
        allow_external_io: bool = False,
    ) -> Path:
        """
        Inspects lexical and resolved canonical path components.
        Raises SanctuaryViolationError (Exit Code 2) on:
          - Any component matching '05 - Fleeting', '.git', or '.obsidian'
          - Any '..' traversal component
          - Symlink escapes out of vault_root when targeting vault paths
          - Reads/writes inside vault_root outside the explicit allowlists
        """
        if not isinstance(target_path, (str, Path)) or not str(target_path).strip():
            raise ValidationError("Empty or invalid file path.")
        raw_str = str(target_path)
        if "\x00" in raw_str:
            raise SanctuaryViolationError("NUL byte injection in file path.")

        lexical = Path(raw_str)
        if ".." in lexical.parts:
            raise SanctuaryViolationError(
                f"PATH TRAVERSAL BLOCKED: '..' component detected in {raw_str!r}.",
                details={"path": raw_str},
            )
        self._check_parts_for_sanctuary(lexical)

        # If relative and require_in_vault, anchor to vault_root
        if not lexical.is_absolute() and require_in_vault:
            candidate = self.vault_root / lexical
        else:
            candidate = lexical.expanduser()

        if ".." in candidate.parts:
            raise SanctuaryViolationError(
                f"PATH TRAVERSAL BLOCKED: '..' component in candidate path {str(candidate)!r}."
            )
        self._check_parts_for_sanctuary(candidate)

        resolved = candidate.resolve(strict=False)
        self._check_parts_for_sanctuary(resolved)

        # Check symlink escape if the lexical candidate was inside vault_root
        abs_candidate = Path(os.path.abspath(str(candidate)))
        if self._is_subpath(abs_candidate, self.vault_root) and not self._is_subpath(
            resolved, self.vault_root
        ):
            raise SanctuaryViolationError(
                f"SYMLINK ESCAPE BLOCKED: {str(candidate)!r} resolves outside vault root to {str(resolved)!r}."
            )

        if require_in_vault and not self._is_subpath(resolved, self.vault_root):
            raise SanctuaryViolationError(
                f"CONTAINMENT VIOLATION: {str(resolved)!r} is outside vault root {str(self.vault_root)!r}."
            )

        if self._is_subpath(resolved, self.vault_root):
            # Allow state_dir if explicitly configured inside vault allowlist
            self._enforce_vault_allowlist(resolved, mode=mode)
            return resolved

        if self._is_subpath(resolved, self.state_dir):
            return resolved

        if self.mirror_state_dir and self._is_subpath(resolved, self.mirror_state_dir):
            return resolved

        if allow_external_io:
            return resolved

        raise SanctuaryViolationError(
            f"UNTRUSTED PATH BLOCKED: {str(resolved)!r} is outside vault and state directories."
        )

    @classmethod
    def validate_slug(cls, slug: Any, what: str = "slug") -> str:
        if not isinstance(slug, str) or not slug:
            raise ValidationError(f"Invalid {what}: must be a non-empty string.")
        if "\x00" in slug or ".." in slug or "/" in slug or "\\" in slug:
            norm = cls._normalize_part(slug)
            for s_part in _SANCTUARY_PARTS:
                if s_part in norm:
                    raise SanctuaryViolationError(f"Sanctuary reference in {what}: {slug!r}")
            if ".." in slug or "/" in slug or "\\" in slug or "\x00" in slug:
                raise SanctuaryViolationError(f"Path traversal or separator in {what}: {slug!r}")
        norm = cls._normalize_part(slug)
        if norm in _SANCTUARY_PARTS:
            raise SanctuaryViolationError(f"Sanctuary keyword in {what}: {slug!r}")
        if not _SLUG_RE.match(slug):
            raise ValidationError(
                f"Invalid {what} {slug!r}: must match ^[A-Za-z0-9][A-Za-z0-9._-]{{0,127}}$."
            )
        return slug

    @classmethod
    def sanitize_title(cls, title: str, fallback: str = "Untitled") -> str:
        if not isinstance(title, str) or not title.strip():
            return fallback
        nfc = unicodedata.normalize("NFC", title)
        cleaned = _ILLEGAL_FILENAME_CHARS_RE.sub("-", nfc)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
        if not cleaned or cls._normalize_part(cleaned) in _SANCTUARY_PARTS or cleaned in (".", ".."):
            raise SanctuaryViolationError(f"Title {title!r} sanitizes to a reserved or sanctuary name.")
        return cleaned[:180].strip()

    @staticmethod
    def validate_offline_html_csp(html_content: str) -> None:
        if not isinstance(html_content, str):
            raise ValidationError("HTML content must be a string.")
        lower = html_content.lower()
        if "content-security-policy" not in lower:
            raise ValidationError("HTML artifact missing Content-Security-Policy meta tag.")
        for directive in REQUIRED_CSP_DIRECTIVES:
            if directive not in lower:
                raise ValidationError(f"HTML artifact CSP missing required directive: {directive!r}")
        # Reject external network URLs in src/href
        if re.search(r'\b(?:src|href)\s*=\s*["\']\s*https?://', html_content, re.I):
            raise ValidationError("HTML artifact contains forbidden external http(s):// src/href resource.")


# ==============================================================================
# SECTION 2 — LOCKMGR & ATOMIC I/O (STATESTORE)
# ==============================================================================

LOCK_TIMEOUT_S = 10.0
LOCK_STALE_S = 60.0

DEFAULT_LEARNER_MODEL: Dict[str, Any] = {
    "schema": SCHEMA_VERSION,
    "engine_version": ENGINE_VERSION,
    "created": None,
    "memory": {
        "fsrs_params": [
            0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031,
            1.6474, 1.0461 if False else 0.1367, 1.0461, 2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755,
        ],
        "desired_retention": 0.90,
        "interval_multiplier": 1.0,
        "last_refit": None,
    },
    "challenge_band": {
        "target_success": 0.85,
        "hint_budget": 2,
    },
    "strategy_weights": {
        "derivation_first": 0.65,
        "example_first": 0.35,
    },
    "settings": {
        "default_mode": "standard",
        "artifacts": "threshold-only",
        "ambient": "quiet",
        "decay_notice": "on",
        "relearning": "on",
    },
    "interests": ["distributed systems", "category theory", "systems engineering"],
    "goals": [],
}


class LockMgr:
    """
    DBA-LOCK-02: Re-entrant in-process lock depth counter + POSIX O_CREAT | O_EXCL +
    os.kill(pid, 0) ESRCH dead-holder detection + race-free stale break.
    """

    _depths: Dict[str, int] = {}

    def __init__(
        self,
        lock_path: Path,
        timeout_s: float = LOCK_TIMEOUT_S,
        stale_s: float = LOCK_STALE_S,
    ) -> None:
        self.lock_path = lock_path.resolve(strict=False)
        self.key = str(self.lock_path)
        self.timeout_s = timeout_s
        self.stale_s = stale_s

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

    def _read_holder(self) -> Tuple[Optional[int], Optional[float]]:
        try:
            raw = self.lock_path.read_text(encoding="utf-8").strip()
            if ":" in raw:
                pid_str, ts_str = raw.split(":", 1)
                return int(pid_str), float(ts_str)
            return int(raw), None
        except (OSError, ValueError):
            return None, None

    def acquire(self) -> "LockMgr":
        cur_depth = self._depths.get(self.key, 0)
        if cur_depth > 0:
            self._depths[self.key] = cur_depth + 1
            return self

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_s
        my_pid = os.getpid()

        while True:
            try:
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                try:
                    payload = f"{my_pid}:{time.time():.6f}\n".encode("utf-8")
                    os.write(fd, payload)
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self._depths[self.key] = 1
                return self
            except FileExistsError:
                holder_pid, holder_ts = self._read_holder()
                if holder_pid == my_pid:
                    # Re-entrant recovery within same process
                    self._depths[self.key] = 1
                    return self

                stale = False
                if holder_pid is not None and not self._is_pid_alive(holder_pid):
                    stale = True
                else:
                    try:
                        mtime = holder_ts if holder_ts is not None else self.lock_path.stat().st_mtime
                        if (time.time() - mtime) > self.stale_s:
                            stale = True
                    except OSError:
                        continue

                if stale:
                    try:
                        os.unlink(self.lock_path)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
                    continue

                if time.monotonic() >= deadline:
                    raise ConcurrencyOrCorruptionError(
                        f"Timed out waiting for lock {str(self.lock_path)!r} held by PID {holder_pid}.",
                        details={"lock_path": str(self.lock_path), "holder_pid": holder_pid},
                    )
                time.sleep(0.02)

    def release(self) -> None:
        cur_depth = self._depths.get(self.key, 0)
        if cur_depth <= 0:
            return
        if cur_depth > 1:
            self._depths[self.key] = cur_depth - 1
            return
        self._depths.pop(self.key, None)
        try:
            os.unlink(self.lock_path)
        except OSError:
            pass

    def __enter__(self) -> "LockMgr":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


class StateStore:
    """
    Crash-safe atomic I/O (.mnemosyne_tmp_* + fsync + os.replace), passive mirror sync,
    JSON corruption quarantine, and OCC conflict snapshotting.
    """

    def __init__(self, gate: VaultGate, lock_timeout_s: float = LOCK_TIMEOUT_S) -> None:
        self.gate = gate
        self.state_dir = gate.state_dir
        self.mirror_dir = gate.mirror_state_dir
        self.lock_timeout_s = lock_timeout_s

    def lock(self) -> LockMgr:
        return LockMgr(self.state_dir / ".mnemosyne.lock", timeout_s=self.lock_timeout_s)

    @staticmethod
    def _fsync_dir(dir_path: Path) -> None:
        try:
            dfd = os.open(str(dir_path), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass

    def atomic_write_text(
        self,
        target_path: Union[str, Path],
        content: str,
        *,
        require_in_vault: bool = False,
        allow_external_io: bool = False,
    ) -> Path:
        resolved = self.gate.validate_path(
            target_path,
            mode="w",
            require_in_vault=require_in_vault,
            allow_external_io=allow_external_io,
        )
        resolved.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(resolved.parent),
            prefix=".mnemosyne_tmp_",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(resolved))
            self._fsync_dir(resolved.parent)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return resolved

    def atomic_write_bytes(
        self,
        target_path: Union[str, Path],
        data: bytes,
        *,
        require_in_vault: bool = False,
        allow_external_io: bool = False,
    ) -> Path:
        resolved = self.gate.validate_path(
            target_path,
            mode="w",
            require_in_vault=require_in_vault,
            allow_external_io=allow_external_io,
        )
        resolved.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(resolved.parent),
            prefix=".mnemosyne_tmp_",
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(resolved))
            self._fsync_dir(resolved.parent)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return resolved

    def _mirror_if_needed(self, rel_parts: Sequence[str], content: str) -> None:
        if self.mirror_dir is None:
            return
        try:
            mirror_target = self.mirror_dir.joinpath(*rel_parts)
            if mirror_target.resolve(strict=False) == self.state_dir.joinpath(*rel_parts).resolve(strict=False):
                return
            self.atomic_write_text(mirror_target, content)
        except OSError:
            pass

    def state_path(self, *parts: str) -> Path:
        return self.state_dir.joinpath(*parts)

    def quarantine_corrupt(self, file_path: Path) -> Optional[Path]:
        if not file_path.exists():
            return None
        q_path = file_path.with_name(f"{file_path.name}.corrupt.{current_date().isoformat()}")
        try:
            os.replace(str(file_path), str(q_path))
            return q_path
        except OSError:
            return None

    def read_json(
        self,
        *rel_parts: str,
        default: Any = None,
        quarantine: bool = True,
    ) -> Any:
        target = self.gate.validate_path(self.state_path(*rel_parts), mode="r")
        if not target.exists():
            # Fallback to passive mirror if canonical does not exist yet
            if self.mirror_dir is not None:
                m_target = self.mirror_dir.joinpath(*rel_parts)
                if m_target.exists():
                    target = m_target
                else:
                    return default
            else:
                return default
        try:
            raw = target.read_text(encoding="utf-8")
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if quarantine:
                self.quarantine_corrupt(target)
            return default
        except FileNotFoundError:
            return default

    def write_json(self, obj: Any, *rel_parts: str) -> Path:
        text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
        target = self.state_path(*rel_parts)
        written = self.atomic_write_text(target, text)
        self._mirror_if_needed(rel_parts, text)
        return written

    def read_jsonl(self, *rel_parts: str) -> List[Dict[str, Any]]:
        target = self.gate.validate_path(self.state_path(*rel_parts), mode="r")
        if not target.exists():
            if self.mirror_dir is not None:
                m_target = self.mirror_dir.joinpath(*rel_parts)
                if m_target.exists():
                    target = m_target
                else:
                    return []
            else:
                return []
        rows: List[Dict[str, Any]] = []
        try:
            for line in target.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s:
                    continue
                try:
                    item = json.loads(s)
                    if isinstance(item, dict):
                        rows.append(item)
                except json.JSONDecodeError:
                    continue
        except FileNotFoundError:
            return []
        return rows

    def write_jsonl(self, rows: Iterable[Dict[str, Any]], *rel_parts: str) -> Path:
        lines = [json.dumps(r, ensure_ascii=False) for r in rows]
        text = ("\n".join(lines) + "\n") if lines else ""
        target = self.state_path(*rel_parts)
        written = self.atomic_write_text(target, text)
        self._mirror_if_needed(rel_parts, text)
        return written

    def append_jsonl(self, row: Dict[str, Any], *rel_parts: str) -> Path:
        existing = self.read_jsonl(*rel_parts)
        existing.append(row)
        return self.write_jsonl(existing, *rel_parts)

    def ensure_initialized(self) -> Dict[str, Any]:
        with self.lock():
            for subdir in ("topics", "receipts", "conflicts"):
                self.state_path(subdir).mkdir(parents=True, exist_ok=True)
                if self.mirror_dir is not None:
                    (self.mirror_dir / subdir).mkdir(parents=True, exist_ok=True)
            for vault_subdir in (
                "00 - Maps of Content",
                "02 - Areas",
                "04 - Permanent",
                "05 - Fleeting/mnemosyne/inbox",
                "99 - Meta/attachments",
                "99 - Meta/mnemosyne-state",
            ):
                (self.gate.vault_root / vault_subdir).mkdir(parents=True, exist_ok=True)

            model = self.load_learner_model(persist=True)
            if not self.state_path("stash.jsonl").exists():
                self.write_jsonl([], "stash.jsonl")
            if self.read_json("misconceptions.json", quarantine=False) is None:
                self.write_json([], "misconceptions.json")
            if self.read_json("experiments.json", quarantine=False) is None:
                self.write_json([], "experiments.json")
            return model

    def load_learner_model(self, persist: bool = False) -> Dict[str, Any]:
        raw = self.read_json("learner-model.json")
        model = json.loads(json.dumps(DEFAULT_LEARNER_MODEL))
        model["created"] = current_date().isoformat()
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, dict) and isinstance(model.get(k), dict):
                    model[k].update(v)
                else:
                    model[k] = v
            if not model.get("created"):
                model["created"] = current_date().isoformat()
        if persist or raw is None:
            with self.lock():
                self.write_json(model, "learner-model.json")
        return model

    def list_topic_slugs(self) -> List[str]:
        t_dir = self.state_path("topics")
        slugs: Set[str] = set()
        if t_dir.is_dir():
            for p in t_dir.iterdir():
                if p.is_file() and p.name.endswith(".json") and not p.name.startswith("."):
                    stem = p.name[:-5]
                    if _SLUG_RE.match(stem):
                        slugs.add(stem)
        if self.mirror_dir is not None and (self.mirror_dir / "topics").is_dir():
            for p in (self.mirror_dir / "topics").iterdir():
                if p.is_file() and p.name.endswith(".json") and not p.name.startswith("."):
                    stem = p.name[:-5]
                    if _SLUG_RE.match(stem):
                        slugs.add(stem)
        return sorted(slugs)

    def load_topic(self, slug: str) -> Dict[str, Any]:
        self.gate.validate_slug(slug, "topic")
        t_path = self.state_path("topics", f"{slug}.json")
        existed = t_path.exists()
        data = self.read_json("topics", f"{slug}.json")
        if data is None:
            if existed:
                raise ConcurrencyOrCorruptionError(
                    f"Topic {slug!r} JSON is corrupted and was quarantined. Run 'doctor --repair'."
                )
            raise ValidationError(f"Unknown topic {slug!r}.")
        if not isinstance(data, dict):
            raise ConcurrencyOrCorruptionError(f"Topic {slug!r} has non-object root structure.")
        return DAGEngine.normalize_topic_shape(data, default_slug=slug)

    def save_topic(self, topic_data: Dict[str, Any]) -> Path:
        slug = self.gate.validate_slug(topic_data.get("slug") or topic_data.get("topic"), "topic")
        topic_data["slug"] = slug
        topic_data["updated"] = current_date().isoformat()
        return self.write_json(topic_data, "topics", f"{slug}.json")

    def snapshot_conflict(self, slug: str, node_id: str, existing_content: str) -> str:
        ts_compact = current_iso_timestamp().replace("-", "").replace(":", "")
        fname = f"{slug}--{node_id}--{ts_compact}.md"
        rel = ("conflicts", fname)
        self.atomic_write_text(self.state_path(*rel), existing_content)
        self._mirror_if_needed(rel, existing_content)
        return f"99 - Meta/mnemosyne-state/conflicts/{fname}"


# ==============================================================================
# SECTION 3 — DAGENGINE (PURE CURRICULUM & OPT-02 FRONTIER MATH)
# ==============================================================================

NODE_KINDS_ALLOWED: Tuple[str, ...] = ("concept", "procedure", "fact")
NOTE_TARGETS_ALLOWED: Tuple[str, ...] = ("04 - Permanent", "02 - Areas")
PREREQ_PROPAGATION_WEIGHT: float = 0.5

_STOPWORDS: Set[str] = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "that", "this", "these",
    "those", "it", "its", "as", "or", "and", "but", "if", "then", "than", "so",
    "what", "why", "how", "when", "where", "which", "who", "does", "do", "did",
    "can", "could", "would", "should", "states", "explains", "concludes", "identifies",
    "defines", "notes", "describes", "shows", "gives", "names",
}


class DAGEngine:
    """
    Kahn's O(V+E) topological sort, cycle & dangling-prereq detection,
    unconditional_truth / motivated_discovery schema enforcement, lexical stem-mirroring guard,
    prerequisite propagation (weight=0.5), and OPT-02 heavy-path binary-search frontier probe.
    """

    @staticmethod
    def _content_tokens(text: str) -> List[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return [w for w in words if len(w) > 2 and w not in _STOPWORDS]

    @classmethod
    def check_stem_mirroring(cls, probe: str, rubric: Sequence[str]) -> List[Dict[str, Any]]:
        """
        RN-06: Checks if a rubric criterion merely repeats facts already stated in the probe's
        declarative stem, or if there is a severe probe-rubric gap.
        Returns a list of stem-mirror violations.
        """
        violations: List[Dict[str, Any]] = []
        if not isinstance(probe, str) or not probe.strip():
            return violations
        # Extract declarative premises before the final question sentence, or full probe if no '?'
        probe_clean = re.sub(r"\s+", " ", probe.strip().lower())
        probe_tokens = set(cls._content_tokens(probe_clean))
        if not probe_tokens:
            return violations

        # Split probe into clauses; premises are clauses not starting with question words
        clauses = [c.strip() for c in re.split(r"[.?!;]+", probe_clean) if c.strip()]
        premise_clauses = [
            c for c in clauses
            if not re.match(r"^(why|how|what|when|where|which|who|prove|derive|compute|calculate|solve|explain|state|suppose)\b", c)
        ]
        premise_text = " ".join(premise_clauses)
        premise_tokens = set(cls._content_tokens(premise_text))

        for idx, crit in enumerate(rubric, start=1):
            if not isinstance(crit, str) or not crit.strip():
                continue
            # Strip leading rubric framing verbs like "States that", "Explains that"
            crit_body = re.sub(
                r"^(states|explains|concludes|identifies|defines|notes|describes|mentions|says)\s+(that\s+)?",
                "",
                crit.strip().lower(),
            )
            crit_tokens = cls._content_tokens(crit_body)
            if len(crit_tokens) >= 5 and premise_tokens:
                overlap = sum(1 for t in crit_tokens if t in premise_tokens) / float(len(crit_tokens))
                if overlap >= 0.85 or (len(crit_body) >= 24 and crit_body in premise_text):
                    violations.append({
                        "criterion": idx,
                        "kind": "stem_mirror",
                        "overlap": round(overlap, 3),
                        "message": f"Rubric criterion #{idx} mirrors a declarative premise in the probe stem ({overlap:.0%} token overlap).",
                    })
        return violations

    @classmethod
    def normalize_topic_shape(
        cls,
        raw: Dict[str, Any],
        default_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValidationError("Topic payload must be a JSON object.")
        out = dict(raw)
        slug = out.get("slug") or out.get("topic") or default_slug
        if not slug:
            raise ValidationError("Topic payload missing 'slug' (or 'topic').")
        VaultGate.validate_slug(slug, "topic")
        out["schema"] = SCHEMA_VERSION
        out["slug"] = slug
        out.setdefault("title", slug.replace("-", " ").title())
        out.setdefault("domain", "General")
        out.setdefault("note_target", "04 - Permanent")
        out.setdefault("goal", f"Master {out['title']} from first principles")
        out.setdefault("created", current_date().isoformat())
        out.setdefault("updated", current_date().isoformat())

        raw_nodes = out.get("nodes")
        node_list: List[Dict[str, Any]] = []
        if isinstance(raw_nodes, list):
            for n in raw_nodes:
                if not isinstance(n, dict):
                    raise ValidationError("Each node in 'nodes' list must be a JSON object.")
                node_list.append(dict(n))
        elif isinstance(raw_nodes, dict):
            for nid, n in raw_nodes.items():
                if not isinstance(n, dict):
                    raise ValidationError(f"Node {nid!r} must be a JSON object.")
                nd = dict(n)
                nd.setdefault("id", nid)
                node_list.append(nd)
        else:
            raise ValidationError("Topic 'nodes' must be a non-empty list or object map.")

        for nd in node_list:
            nid = nd.get("id")
            VaultGate.validate_slug(nid, "node id")
            nd.setdefault("title", nid.replace("-", " ").title())
            nd.setdefault("kind", "concept")
            nd.setdefault("arbitrary", nd.get("kind") == "fact")
            nd.setdefault("threshold", False)
            nd.setdefault("archived", False)
            edges = nd.get("edges")
            if not isinstance(edges, dict):
                reqs = nd.get("requires") if isinstance(nd.get("requires"), list) else []
                edges = {"requires": list(reqs), "contrasts_with": [], "analogous_to": []}
            else:
                edges = {
                    "requires": list(edges.get("requires") or []),
                    "contrasts_with": list(edges.get("contrasts_with") or []),
                    "analogous_to": list(edges.get("analogous_to") or []),
                }
            nd["edges"] = edges
            nd.setdefault("state", "new")
            nd.setdefault("last_sid", None)
            nd["fsrs"] = FSRSState.from_dict(nd.get("fsrs")).to_dict()
            if not isinstance(nd.get("obsidian"), dict):
                nd["obsidian"] = {
                    "note_path": None,
                    "body_hash": None,
                    "st_mtime_ns": None,
                    "st_size": None,
                }
        out["nodes"] = node_list
        return out

    @classmethod
    def validate_and_sort_dag(
        cls,
        raw_topic: Dict[str, Any],
        *,
        strict_stem_mirror: bool = True,
    ) -> Dict[str, Any]:
        """
        Validates topic DAG schema, node kinds, unconditional_truth & motivated_discovery
        requirements on concept/procedure nodes, dangling prerequisites, and executes
        Kahn's O(V+E) topological sort. Raises ValidationError (Exit Code 1) on any defect.
        """
        topic = cls.normalize_topic_shape(raw_topic)
        errors: List[str] = []

        note_target = topic.get("note_target", "04 - Permanent")
        if note_target not in NOTE_TARGETS_ALLOWED:
            errors.append(
                f"Invalid note_target {note_target!r}; must be one of {NOTE_TARGETS_ALLOWED}."
            )

        nodes: List[Dict[str, Any]] = topic["nodes"]
        if not nodes:
            raise ValidationError("Topic DAG must contain at least one node.")

        by_id: Dict[str, Dict[str, Any]] = {}
        for idx, nd in enumerate(nodes):
            nid = nd.get("id")
            if nid in by_id:
                errors.append(f"Duplicate node id {nid!r} at index {idx}.")
            by_id[nid] = nd

            kind = nd.get("kind", "concept")
            if kind not in NODE_KINDS_ALLOWED:
                errors.append(
                    f"Node {nid!r} has invalid kind {kind!r}; allowed: {NODE_KINDS_ALLOWED}."
                )

            ut = nd.get("unconditional_truth")
            md = nd.get("motivated_discovery")
            if kind in ("concept", "procedure"):
                if not isinstance(ut, str) or not ut.strip():
                    errors.append(
                        f"Node {nid!r} (kind={kind!r}) is missing required non-empty 'unconditional_truth'."
                    )
                if not isinstance(md, str) or not md.strip():
                    errors.append(
                        f"Node {nid!r} (kind={kind!r}) is missing required non-empty 'motivated_discovery'."
                    )
            else:
                # For 'fact' nodes, populate sensible defaults if omitted
                if not isinstance(ut, str) or not ut.strip():
                    nd["unconditional_truth"] = nd.get("claim") or nd.get("title") or nid
                if not isinstance(md, str) or not md.strip():
                    nd["motivated_discovery"] = (
                        f"Direct convention or factual anchor required for {nd.get('title', nid)}."
                    )

            claim = nd.get("claim")
            if not isinstance(claim, str) or not claim.strip():
                errors.append(f"Node {nid!r} is missing required non-empty 'claim'.")

            probe = nd.get("probe")
            if not isinstance(probe, str) or not probe.strip():
                errors.append(f"Node {nid!r} is missing required non-empty 'probe'.")

            rubric = nd.get("rubric")
            if not isinstance(rubric, list) or not rubric or not all(
                isinstance(c, str) and c.strip() for c in rubric
            ):
                errors.append(
                    f"Node {nid!r} must have a non-empty 'rubric' list of non-empty strings."
                )
            elif strict_stem_mirror and isinstance(probe, str):
                mirrors = cls.check_stem_mirroring(probe, rubric)
                for m in mirrors:
                    errors.append(f"Node {nid!r}: {m['message']}")

        # Check dangling prerequisites and build adjacency list for Kahn's O(V+E) topological sort
        in_degree: Dict[str, int] = {nid: 0 for nid in by_id}
        dependents: Dict[str, List[str]] = {nid: [] for nid in by_id}

        for nid, nd in by_id.items():
            if nd.get("archived"):
                continue
            reqs = nd.get("edges", {}).get("requires", [])
            if not isinstance(reqs, list):
                errors.append(f"Node {nid!r} edges.requires must be a list.")
                continue
            seen_reqs: Set[str] = set()
            for r in reqs:
                if not isinstance(r, str) or not r:
                    errors.append(f"Node {nid!r} has non-string prerequisite {r!r}.")
                    continue
                if r == nid:
                    errors.append(f"Node {nid!r} has a self-dependency cycle ({nid} -> {nid}).")
                    continue
                if r not in by_id:
                    errors.append(
                        f"Node {nid!r} references dangling prerequisite {r!r} not in topic."
                    )
                    continue
                if r not in seen_reqs:
                    seen_reqs.add(r)
                    in_degree[nid] += 1
                    dependents[r].append(nid)

        if errors:
            raise ValidationError(
                "DAG schema validation failed: " + "; ".join(errors),
                details={"errors": errors},
            )

        # Kahn's O(V+E) algorithm with deterministic tie-breaking by original position/order
        orig_pos = {nd["id"]: (nd.get("order") or idx, idx, nd["id"]) for idx, nd in enumerate(nodes)}
        ready = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0 and not by_id[nid].get("archived")],
            key=lambda x: orig_pos[x],
        )
        topo_order: List[str] = []

        while ready:
            curr = ready.pop(0)
            topo_order.append(curr)
            for dep in dependents[curr]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    ready.append(dep)
            ready.sort(key=lambda x: orig_pos[x])

        active_ids = [nid for nid, nd in by_id.items() if not nd.get("archived")]
        if len(topo_order) < len(active_ids):
            cycle_nodes = [nid for nid in active_ids if nid not in set(topo_order)]
            cycle_path = cls._extract_cycle_path(by_id, cycle_nodes)
            raise ValidationError(
                f"DAG cycle detected in 'requires' edges: {' -> '.join(cycle_path)}",
                details={"cycle": cycle_path},
            )

        # Assign 1-based topological order and sort nodes deterministically
        for rank, nid in enumerate(topo_order, start=1):
            by_id[nid]["order"] = rank
        archived_nodes = [by_id[nid] for nid in by_id if by_id[nid].get("archived")]
        for offset, nd in enumerate(archived_nodes, start=len(topo_order) + 1):
            nd["order"] = offset

        topic["nodes"] = [by_id[nid] for nid in topo_order] + archived_nodes
        return topic

    @staticmethod
    def _extract_cycle_path(
        by_id: Dict[str, Dict[str, Any]], candidates: Sequence[str]
    ) -> List[str]:
        cand_set = set(candidates)
        color: Dict[str, int] = {}

        def dfs(curr: str, stack: List[str]) -> Optional[List[str]]:
            color[curr] = 1
            for req in by_id[curr].get("edges", {}).get("requires", []):
                if req not in cand_set:
                    continue
                if color.get(req) == 1:
                    idx = stack.index(req)
                    return stack[idx:] + [req]
                if color.get(req, 0) == 0:
                    res = dfs(req, stack + [req])
                    if res:
                        return res
            color[curr] = 2
            return None

        for nid in candidates:
            if color.get(nid, 0) == 0:
                res = dfs(nid, [nid])
                if res:
                    return res
        return list(candidates)

    @staticmethod
    def is_node_credited(node: Dict[str, Any]) -> bool:
        state = node.get("state", "new")
        fsrs = node.get("fsrs") or {}
        reps = int(as_finite_float(fsrs.get("reps"), 0.0) or 0)
        return state in ("learning", "review", "mastered") or reps > 0

    @classmethod
    def are_prerequisites_met(
        cls, node: Dict[str, Any], by_id: Dict[str, Dict[str, Any]]
    ) -> bool:
        reqs = node.get("edges", {}).get("requires", [])
        for r in reqs:
            parent = by_id.get(r)
            if parent and not parent.get("archived") and not cls.is_node_credited(parent):
                return False
        return True

    @classmethod
    def propagate_prerequisite_credit(
        cls,
        topic: Dict[str, Any],
        node_id: str,
        weight: float = PREREQ_PROPAGATION_WEIGHT,
    ) -> List[Dict[str, Any]]:
        """
        Propagates fractional credit (default weight=0.5) to direct prerequisites of `node_id`
        when `node_id` succeeds on recall/encode.
        - If a prerequisite is already scheduled (s is not None), boosts stability slightly
          proportional to weight * elapsed retrievability gain, or records `implicit_credit`.
        - Records `implicit_credit` metadata on prerequisite nodes.
        """
        by_id = {nd["id"]: nd for nd in topic.get("nodes", [])}
        target = by_id.get(node_id)
        if not target:
            return []
        propagated: List[Dict[str, Any]] = []
        for req_id in target.get("edges", {}).get("requires", []):
            parent = by_id.get(req_id)
            if not parent or parent.get("archived"):
                continue
            fsrs = parent.setdefault("fsrs", FSRSState().to_dict())
            prev_credit = as_finite_float(parent.get("implicit_credit"), 0.0) or 0.0
            new_credit = round(prev_credit + weight, 4)
            parent["implicit_credit"] = new_credit
            s_cur = as_finite_float(fsrs.get("s"))
            if s_cur is not None and s_cur > 0:
                # Fractional stability reinforcement weighted by 0.5
                s_boosted = round(clamp_num(s_cur * (1.0 + 0.10 * weight), 0.1, 36500.0), 4)
                fsrs["s"] = s_boosted
            propagated.append({
                "prerequisite": req_id,
                "from_node": node_id,
                "weight": weight,
                "implicit_credit": new_credit,
                "s": fsrs.get("s"),
            })
        return propagated

    @classmethod
    def decompose_heavy_paths(
        cls,
        topic: Dict[str, Any],
        target_id: Optional[str] = None,
    ) -> List[List[str]]:
        """
        OPT-02: Extracts the uncredited ancestor subgraph G'[A(u)] via reverse BFS in O(V+E)
        and partitions it into maximal topological heavy paths (longest uncredited chains).
        """
        nodes = [nd for nd in topic.get("nodes", []) if not nd.get("archived")]
        by_id = {nd["id"]: nd for nd in nodes}

        if target_id is not None:
            if target_id not in by_id:
                raise ValidationError(f"Unknown target node {target_id!r} in topic {topic.get('slug')!r}.")
            # Reverse BFS from target_id over `requires` edges
            visited: Set[str] = set()
            queue: List[str] = [target_id]
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                for req in by_id[curr].get("edges", {}).get("requires", []):
                    if req in by_id and req not in visited:
                        queue.append(req)
            sub_ids = [nd["id"] for nd in nodes if nd["id"] in visited and not cls.is_node_credited(nd)]
        else:
            sub_ids = [nd["id"] for nd in nodes if not cls.is_node_credited(nd)]

        if not sub_ids:
            return []

        sub_set = set(sub_ids)
        # sub_ids is already in topological order because `topic["nodes"]` is topologically sorted
        children: Dict[str, List[str]] = {nid: [] for nid in sub_ids}
        for nid in sub_ids:
            for req in by_id[nid].get("edges", {}).get("requires", []):
                if req in sub_set:
                    children[req].append(nid)

        # Compute longest path from each node to a sink in G'[A(u)]
        dp_len: Dict[str, int] = {nid: 1 for nid in sub_ids}
        heavy_child: Dict[str, Optional[str]] = {nid: None for nid in sub_ids}
        for nid in reversed(sub_ids):
            best_c: Optional[str] = None
            best_l = 0
            for c in children[nid]:
                if dp_len[c] > best_l:
                    best_l = dp_len[c]
                    best_c = c
            dp_len[nid] = 1 + best_l
            heavy_child[nid] = best_c

        # Greedily extract disjoint maximal heavy chains ordered by chain length descending
        assigned: Set[str] = set()
        chains: List[List[str]] = []
        for start_nid in sorted(sub_ids, key=lambda x: (-dp_len[x], sub_ids.index(x))):
            if start_nid in assigned:
                continue
            chain: List[str] = []
            curr: Optional[str] = start_nid
            while curr is not None and curr not in assigned:
                chain.append(curr)
                assigned.add(curr)
                # Follow heavy child if unassigned, otherwise next heaviest unassigned child
                nxt = heavy_child[curr]
                if nxt is None or nxt in assigned:
                    avail = [c for c in children[curr] if c not in assigned]
                    nxt = max(avail, key=lambda c: dp_len[c]) if avail else None
                curr = nxt
            if chain:
                chains.append(chain)
        return chains

    @classmethod
    def frontier_probe_state(
        cls,
        topic: Dict[str, Any],
        target_id: str,
    ) -> Dict[str, Any]:
        """
        OPT-02: Computes or resumes binary-search frontier bracketing for `target_id`.
        Guarantees bracketing in <= ceil(log2 L) + 2 probes per heavy path strand.
        """
        by_id = {nd["id"]: nd for nd in topic.get("nodes", [])}
        if target_id not in by_id:
            raise ValidationError(f"Unknown target node {target_id!r} in topic {topic.get('slug')!r}.")

        probe_store = topic.setdefault("frontier_probes", {})
        state = probe_store.get(target_id)

        if not isinstance(state, dict) or not state.get("chain"):
            chains = cls.decompose_heavy_paths(topic, target_id=target_id)
            if not chains:
                return {
                    "ok": True,
                    "topic": topic.get("slug"),
                    "target": target_id,
                    "status": "strand_mastered",
                    "bracketed": True,
                    "chain": [],
                    "probe_bounds": [0, -1],
                    "floor_node": target_id,
                    "ceiling_node": None,
                    "teach_from": None,
                    "candidate_node": None,
                    "probes_taken": 0,
                    "max_probes": 0,
                }
            active_chain = chains[0]
            L = len(active_chain)
            max_probes = int(math.ceil(math.log2(max(1, L)))) + 2
            state = {
                "target": target_id,
                "chain": active_chain,
                "probe_bounds": [0, L - 1],
                "floor_idx": -1,
                "ceiling_idx": L,
                "probes_taken": 0,
                "max_probes": max_probes,
                "history": [],
            }
            probe_store[target_id] = state

        chain: List[str] = state["chain"]
        L = len(chain)
        low, high = state["probe_bounds"]
        floor_idx = state["floor_idx"]
        ceiling_idx = state["ceiling_idx"]

        if low > high:
            if floor_idx >= L - 1:
                status = "strand_mastered"
                teach_from = None
            elif ceiling_idx <= 0:
                status = "start_at_root"
                teach_from = chain[0]
            else:
                status = "frontier_found"
                teach_from = chain[ceiling_idx]
            return {
                "ok": True,
                "topic": topic.get("slug"),
                "target": target_id,
                "status": status,
                "bracketed": True,
                "chain": chain,
                "probe_bounds": [low, high],
                "floor_node": chain[floor_idx] if 0 <= floor_idx < L else None,
                "ceiling_node": chain[ceiling_idx] if 0 <= ceiling_idx < L else None,
                "teach_from": teach_from,
                "candidate_node": None,
                "probes_taken": state["probes_taken"],
                "max_probes": state["max_probes"],
            }

        mid = (low + high) // 2
        cand_id = chain[mid]
        cand_node = by_id[cand_id]
        return {
            "ok": True,
            "topic": topic.get("slug"),
            "target": target_id,
            "status": "probing",
            "bracketed": False,
            "chain": chain,
            "probe_bounds": [low, high],
            "mid_index": mid,
            "floor_node": chain[floor_idx] if 0 <= floor_idx < L else None,
            "ceiling_node": chain[ceiling_idx] if 0 <= ceiling_idx < L else None,
            "teach_from": None,
            "candidate_node": {
                "id": cand_id,
                "title": cand_node.get("title"),
                "kind": cand_node.get("kind"),
                "probe": cand_node.get("probe"),
                "claim": cand_node.get("claim"),
                "unconditional_truth": cand_node.get("unconditional_truth"),
            },
            "probes_taken": state["probes_taken"],
            "max_probes": state["max_probes"],
        }

    @classmethod
    def record_probe_result(
        cls,
        topic: Dict[str, Any],
        node_id: str,
        passed: bool,
        target_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Records a binary-search probe pass/fail on `node_id` and updates `probe_bounds`.
        Returns (updated_frontier_status, newly_credited_node_ids).
        """
        by_id = {nd["id"]: nd for nd in topic.get("nodes", [])}
        if node_id not in by_id:
            raise ValidationError(f"Unknown node {node_id!r} in topic {topic.get('slug')!r}.")

        probe_store = topic.setdefault("frontier_probes", {})
        # Find or initialize the active probe state containing node_id
        resolved_target = target_id
        if not resolved_target:
            for tid, st in probe_store.items():
                if isinstance(st, dict) and node_id in (st.get("chain") or []):
                    resolved_target = tid
                    break
        if not resolved_target:
            # Default to deepest uncredited descendant or node_id itself
            sinks = [nd["id"] for nd in reversed(topic.get("nodes", [])) if not nd.get("archived")]
            resolved_target = sinks[0] if sinks else node_id

        cls.frontier_probe_state(topic, resolved_target)
        state = probe_store.get(resolved_target)
        if not isinstance(state, dict) or node_id not in state.get("chain", []):
            # Build a chain specifically containing node_id and its uncredited ancestors/descendants
            anc_chains = cls.decompose_heavy_paths(topic, target_id=resolved_target)
            matching = next((c for c in anc_chains if node_id in c), None)
            if matching is None:
                matching = [node_id]
            L = len(matching)
            state = {
                "target": resolved_target,
                "chain": matching,
                "probe_bounds": [0, L - 1],
                "floor_idx": -1,
                "ceiling_idx": L,
                "probes_taken": 0,
                "max_probes": int(math.ceil(math.log2(max(1, L)))) + 2,
                "history": [],
            }
            probe_store[resolved_target] = state

        chain: List[str] = state["chain"]
        idx = chain.index(node_id)
        low, high = state["probe_bounds"]
        state["probes_taken"] = int(state.get("probes_taken", 0)) + 1
        state.setdefault("history", []).append({"node": node_id, "idx": idx, "result": "pass" if passed else "fail"})

        credited_nodes: List[str] = []
        if passed:
            state["floor_idx"] = max(int(state.get("floor_idx", -1)), idx)
            state["probe_bounds"] = [max(low, idx + 1), high]
            # Credit node_id and all ancestors on the chain up to idx
            for c_nid in chain[: idx + 1]:
                if not cls.is_node_credited(by_id[c_nid]):
                    credited_nodes.append(c_nid)
        else:
            state["ceiling_idx"] = min(int(state.get("ceiling_idx", len(chain))), idx)
            state["probe_bounds"] = [low, min(high, idx - 1)]

        status = cls.frontier_probe_state(topic, resolved_target)
        status["credited_nodes"] = credited_nodes
        status["last_probe"] = {"node": node_id, "result": "pass" if passed else "fail"}
        return status, credited_nodes


# ==============================================================================
# SECTION 4 — FSRSENGINE (PURE FSRS-4.5, REFIT & OPT-01 SYNC-SR BRIDGE)
# ==============================================================================

DEFAULT_W: Tuple[float, ...] = (
    0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031,
    1.6474, 0.1367, 1.0461, 2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755,
)

FSRS_DECAY: float = -0.5
FSRS_FACTOR: float = 19.0 / 81.0
RETENTION_DEFAULT: float = 0.90
RETENTION_MIN: float = 0.70
RETENTION_MAX: float = 0.97
MULTIPLIER_MIN: float = 0.50
MULTIPLIER_MAX: float = 1.50
INTERVAL_MAX: int = 365
REFIT_MIN_BLIND_REVIEWS: int = 30

RATING_TO_G: Dict[str, int] = {"again": 1, "hard": 2, "good": 3, "easy": 4}
G_TO_RATING: Dict[int, str] = {1: "again", 2: "hard", 3: "good", 4: "easy"}
G_TO_GRADE: Dict[int, str] = {1: "lapsed", 2: "partial", 3: "recalled", 4: "recalled"}
GRADE_TO_DEFAULT_G: Dict[str, int] = {"lapsed": 1, "partial": 2, "recalled": 3}

RELEARN_DOSE_CAPS: Dict[int, int] = {
    1: 6,   # second post-lapse recall (1 step remaining) -> cap at 6 days
    2: 2,   # first post-lapse recall (2 steps remaining) -> cap at 2 days
    3: 2,   # threshold node first post-lapse recall -> cap at 2 days
}

FIT_W_BOUNDS: Tuple[Tuple[float, float], ...] = (
    (0.1, 100.0),   # w0: S0(again)
    (0.1, 100.0),   # w1: S0(hard)
    (0.1, 100.0),   # w2: S0(good)
    (0.1, 100.0),   # w3: S0(easy)
    (1.0, 10.0),    # w4: D0 base
    (0.1, 5.0),     # w5: D0 slope
    (0.1, 5.0),     # w6: D delta
    (0.0, 0.5),     # w7: mean reversion weight
    (0.0, 4.0),     # w8: recall stability exp
    (0.0, 1.0),     # w9: stability power decay
    (0.01, 3.0),    # w10: retrievability exp
    (0.1, 10.0),    # w11: forget stability base
    (0.01, 2.0),    # w12: forget difficulty power
    (0.01, 1.0),    # w13: forget stability power
    (0.0, 3.0),     # w14: forget retrievability exp
    (0.01, 1.0),    # w15: hard penalty
    (1.0, 6.0),     # w16: easy bonus
)


class FSRSEngine:
    """
    Exact 17-weight FSRS-4.5 mathematical scheduler (RFC §3.3.1),
    bi-directional obsidian-spaced-repetition bridge (RFC §3.3.2 & OPT-01),
    and coordinate-search parameter refit (excluding source == 'obsidian-sr').
    """

    @staticmethod
    def normalize_weights(w: Optional[Sequence[float]] = None) -> List[float]:
        if not isinstance(w, (list, tuple)) or len(w) != 17:
            return list(DEFAULT_W)
        out: List[float] = []
        for idx, val in enumerate(w):
            v = as_finite_float(val)
            if v is None:
                return list(DEFAULT_W)
            lo, hi = FIT_W_BOUNDS[idx]
            out.append(clamp_num(v, lo, hi))
        return out

    @classmethod
    def init_stability(cls, g: int, w: Optional[Sequence[float]] = None) -> float:
        weights = cls.normalize_weights(w)
        g_clamped = max(1, min(4, int(g)))
        return clamp_num(weights[g_clamped - 1], 0.1, 100.0)

    @classmethod
    def init_difficulty(cls, g: int, w: Optional[Sequence[float]] = None) -> float:
        weights = cls.normalize_weights(w)
        g_clamped = max(1, min(4, int(g)))
        return clamp_num(weights[4] - (g_clamped - 3) * weights[5], 1.0, 10.0)

    @staticmethod
    def retrievability(elapsed_days: float, stability: float) -> float:
        if stability <= 0:
            return 0.0
        t = max(0.0, float(elapsed_days))
        return (1.0 + FSRS_FACTOR * (t / stability)) ** FSRS_DECAY

    @classmethod
    def next_difficulty(cls, d: float, g: int, w: Optional[Sequence[float]] = None) -> float:
        weights = cls.normalize_weights(w)
        d0_good = cls.init_difficulty(3, weights)
        d_prime = d - weights[6] * (g - 3)
        d_next = weights[7] * d0_good + (1.0 - weights[7]) * d_prime
        return clamp_num(d_next, 1.0, 10.0)

    @classmethod
    def next_stability_recall(
        cls,
        d: float,
        s: float,
        r: float,
        g: int,
        w: Optional[Sequence[float]] = None,
    ) -> float:
        weights = cls.normalize_weights(w)
        hard_penalty = weights[15] if g == 2 else 1.0
        easy_bonus = weights[16] if g == 4 else 1.0
        grow = (
            math.exp(weights[8])
            * (11.0 - d)
            * (max(0.1, s) ** (-weights[9]))
            * (math.exp(weights[10] * (1.0 - r)) - 1.0)
            * hard_penalty
            * easy_bonus
        )
        return clamp_num(s * (1.0 + grow), 0.1, 36500.0)

    @classmethod
    def next_stability_forget(
        cls,
        d: float,
        s: float,
        r: float,
        w: Optional[Sequence[float]] = None,
    ) -> float:
        weights = cls.normalize_weights(w)
        sf = (
            weights[11]
            * (max(1.0, d) ** (-weights[12]))
            * (((max(0.1, s) + 1.0) ** weights[13]) - 1.0)
            * math.exp(weights[14] * (1.0 - r))
        )
        return clamp_num(min(sf, s), 0.1, 36500.0)

    @staticmethod
    def optimal_interval(
        stability: float,
        desired_retention: float = RETENTION_DEFAULT,
        interval_multiplier: float = 1.0,
    ) -> int:
        r_req = clamp_num(desired_retention, RETENTION_MIN, RETENTION_MAX)
        m_user = clamp_num(interval_multiplier, MULTIPLIER_MIN, MULTIPLIER_MAX)
        i_raw = (stability / FSRS_FACTOR) * ((r_req ** (1.0 / FSRS_DECAY)) - 1.0) * m_user
        return int(clamp_num(round(i_raw), 1, INTERVAL_MAX))

    @classmethod
    def apply_rating(
        cls,
        state: Union[FSRSState, Dict[str, Any]],
        g: int,
        on_date: date,
        *,
        w: Optional[Sequence[float]] = None,
        desired_retention: float = RETENTION_DEFAULT,
        interval_multiplier: float = 1.0,
        relearning_enabled: bool = True,
        is_threshold: bool = False,
        node_kind: str = "concept",
        error_class: Optional[str] = None,
    ) -> Tuple[FSRSState, Dict[str, Any], int]:
        """
        Pure FSRS-4.5 state transition.
        - Floors G at 2 ('hard'/'partial') if error_class == 'slip' on a 'procedure' node.
        - Applies post-lapse relearning dose caps (c1=2d, c2=6d) when relearn_step > 0.
        Returns (new_FSRSState, fsrs_transition_dict, effective_g).
        """
        fsrs = state if isinstance(state, FSRSState) else FSRSState.from_dict(state)
        weights = cls.normalize_weights(w)
        eff_g = max(1, min(4, int(g)))
        if node_kind == "procedure" and error_class == "slip" and eff_g < 2:
            eff_g = 2

        s_before = fsrs.s
        d_before = fsrs.d
        relearn_step = fsrs.relearn_step

        if s_before is None or s_before <= 0:
            # First encoding exposure
            s_next = cls.init_stability(eff_g, weights)
            d_next = cls.init_difficulty(eff_g, weights)
            r_now: Optional[float] = None
            lapses_next = fsrs.lapses
            if eff_g == 1 and relearning_enabled:
                relearn_step = 3 if is_threshold else 2
        else:
            d_cur = d_before if (d_before is not None and d_before > 0) else cls.init_difficulty(3, weights)
            last_dt = parse_iso_date(fsrs.last)
            elapsed = max(0, (on_date - last_dt).days) if last_dt else 0
            r_now = cls.retrievability(elapsed, s_before)
            d_next = cls.next_difficulty(d_cur, eff_g, weights)
            if eff_g == 1:
                s_next = cls.next_stability_forget(d_cur, s_before, r_now, weights)
                lapses_next = fsrs.lapses + 1
                if relearning_enabled:
                    relearn_step = 3 if is_threshold else 2
            else:
                s_next = cls.next_stability_recall(d_cur, s_before, r_now, eff_g, weights)
                lapses_next = fsrs.lapses

        ivl = cls.optimal_interval(s_next, desired_retention, interval_multiplier)
        dose_capped = False

        if eff_g == 1:
            # On lapse, schedule next review according to S_next (typically 1 day)
            if ivl > 1:
                ivl = 1
                dose_capped = True
        elif relearning_enabled and relearn_step > 0 and s_before is not None:
            # Post-lapse relearning dose caps: c1 = 2 days, c2 = 6 days
            cap_val = 2 if relearn_step >= 2 else 6
            if ivl > cap_val:
                ivl = cap_val
                dose_capped = True
            relearn_step = max(0, relearn_step - 1)

        due_date = (on_date + timedelta(days=ivl)).isoformat()
        new_state = FSRSState(
            s=round(s_next, 4),
            d=round(d_next, 4),
            due=due_date,
            last=on_date.isoformat(),
            interval=ivl,
            reps=fsrs.reps + 1,
            lapses=lapses_next,
            relearn_step=relearn_step,
        )
        transition = {
            "s_before": round(s_before, 4) if s_before is not None else None,
            "s_after": new_state.s,
            "d_before": round(d_before, 4) if d_before is not None else None,
            "d_after": new_state.d,
            "retrievability": round(r_now, 4) if r_now is not None else None,
            "interval_days": ivl,
            "dose_capped": dose_capped,
        }
        return new_state, transition, eff_g

    # --------------------------------------------------------------------------
    # Bi-Directional obsidian-spaced-repetition Mathematical Bridge (RFC §3.3.2)
    # --------------------------------------------------------------------------

    @staticmethod
    def difficulty_to_sr_ease(difficulty: Optional[float]) -> int:
        d = clamp_num(difficulty if difficulty is not None else 5.0, 1.0, 10.0)
        ease = round(300.0 - ((d - 1.0) / 9.0) * 170.0)
        return int(clamp_num(ease, 130, 300))

    @classmethod
    def to_sr_frontmatter(
        cls, fsrs: Union[FSRSState, Dict[str, Any]], last_sid: Optional[str]
    ) -> SRFrontmatter:
        st = fsrs if isinstance(fsrs, FSRSState) else FSRSState.from_dict(fsrs)
        due_str = st.due or current_date().isoformat()
        ivl = max(1, int(round(st.interval if st.interval and st.interval > 0 else 1)))
        ease = cls.difficulty_to_sr_ease(st.d)
        return SRFrontmatter(
            sr_due=due_str,
            sr_interval=ivl,
            sr_ease=ease,
            mnemosyne_sid=last_sid,
        )

    @classmethod
    def infer_sr_reverse_rating(
        cls,
        fsrs: Union[FSRSState, Dict[str, Any]],
        sr_due_md: str,
        sr_interval_md: int,
        sr_ease_md: int,
        today_dt: Optional[date] = None,
    ) -> Tuple[int, date, int]:
        """
        Reverse Mapping (sync-sr: Obsidian SR -> FSRS-4.5, RFC §3.3.2):
        - Effective review date: clamp(sr_due - timedelta(days=sr_interval_md), fsrs.last, today())
        - Expected ease: round(300 - ((D - 1.0) / 9.0) * 170)
        - Rating G in {1..4} from delta_ease and sr_interval_md.
        Returns (G, d_rev, delta_ease).
        """
        st = fsrs if isinstance(fsrs, FSRSState) else FSRSState.from_dict(fsrs)
        now_d = today_dt or current_date()
        due_d = parse_iso_date(sr_due_md)
        if due_d is None:
            raise ConcurrencyOrCorruptionError(f"Invalid sr-due date in frontmatter: {sr_due_md!r}")

        ivl_md = max(0, int(sr_interval_md))
        raw_rev = due_d - timedelta(days=ivl_md)
        last_d = parse_iso_date(st.last) or raw_rev
        # Clamp raw_rev between [last_d, now_d]
        d_rev = max(last_d, min(now_d, raw_rev))

        expected_ease = cls.difficulty_to_sr_ease(st.d)
        delta_ease = int(sr_ease_md) - expected_ease

        if ivl_md <= 1 or delta_ease <= -15:
            g = 1
        elif -15 < delta_ease < 0:
            g = 2
        elif delta_ease == 0:
            g = 3
        else:
            g = 4
        return g, d_rev, delta_ease

    # --------------------------------------------------------------------------
    # Coordinate-Search Refit & Retention Analytics
    # --------------------------------------------------------------------------

    @classmethod
    def filter_blind_review_receipts(
        cls, receipts: Iterable[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Strictly filters to blind-graded review receipts (excluding source == 'obsidian-sr').
        """
        usable: List[Dict[str, Any]] = []
        for r in receipts:
            if not isinstance(r, dict):
                continue
            if r.get("source") == "obsidian-sr":
                continue
            if r.get("kind") not in ("review", "encode", "transfer"):
                continue
            trans = r.get("fsrs_transition") if isinstance(r.get("fsrs_transition"), dict) else {}
            ret = as_finite_float(trans.get("retrievability") if trans else r.get("retrievability"))
            if r.get("kind") == "review" and ret is not None and ret < 1.0:
                usable.append(r)
        return usable

    @classmethod
    def _bce_loss(
        cls,
        w: Sequence[float],
        trajectories: Sequence[List[Tuple[int, int, float]]],
    ) -> float:
        """
        Computes mean binary cross-entropy loss + L1 regularization toward DEFAULT_W
        across per-node review trajectories [(g, elapsed_days, outcome), ...].
        """
        eps = 1e-6
        total_loss = 0.0
        count = 0
        for traj in trajectories:
            if not traj:
                continue
            g0, _, _ = traj[0]
            s = cls.init_stability(g0, w)
            d = cls.init_difficulty(g0, w)
            for g, elapsed, y in traj[1:]:
                r_pred = clamp_num(cls.retrievability(max(1, elapsed), s), eps, 1.0 - eps)
                total_loss += -(y * math.log(r_pred) + (1.0 - y) * math.log(1.0 - r_pred))
                count += 1
                d_next = cls.next_difficulty(d, g, w)
                if g == 1:
                    s = cls.next_stability_forget(d, s, r_pred, w)
                else:
                    s = cls.next_stability_recall(d, s, r_pred, g, w)
                d = d_next
        if count == 0:
            return 0.0
        reg = sum(abs(w[i] - DEFAULT_W[i]) / (FIT_W_BOUNDS[i][1] - FIT_W_BOUNDS[i][0]) for i in range(17))
        return (total_loss / float(count)) + (0.005 * reg / 17.0)

    @classmethod
    def refit_parameters(
        cls,
        all_receipts: Sequence[Dict[str, Any]],
        current_w: Optional[Sequence[float]] = None,
        *,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Coordinate-search FSRS-4.5 optimizer over blind-graded receipts (source != 'obsidian-sr').
        Requires >= 30 blind review receipts unless force=True.
        """
        blind_reviews = cls.filter_blind_review_receipts(all_receipts)
        n_reviews = len(blind_reviews)
        if n_reviews < REFIT_MIN_BLIND_REVIEWS and not force:
            return {
                "ok": False,
                "accepted": False,
                "n_blind_reviews": n_reviews,
                "required_min": REFIT_MIN_BLIND_REVIEWS,
                "reason": f"Need >= {REFIT_MIN_BLIND_REVIEWS} blind-graded review receipts (excluding obsidian-sr); have {n_reviews}.",
            }
        if n_reviews == 0:
            return {
                "ok": False,
                "accepted": False,
                "n_blind_reviews": 0,
                "required_min": REFIT_MIN_BLIND_REVIEWS,
                "reason": "No blind-graded review receipts with retrievability predictions available.",
            }

        # Group blind receipts into per-(topic, node) chronological trajectories
        by_node: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for r in all_receipts:
            if not isinstance(r, dict) or r.get("source") == "obsidian-sr":
                continue
            t_slug = r.get("topic")
            n_id = r.get("node")
            if isinstance(t_slug, str) and isinstance(n_id, str):
                by_node.setdefault((t_slug, n_id), []).append(r)

        trajectories: List[List[Tuple[int, int, float]]] = []
        for _, rows in by_node.items():
            rows_sorted = sorted(rows, key=lambda x: (str(x.get("captured_at") or x.get("ts") or ""), str(x.get("id") or "")))
            traj: List[Tuple[int, int, float]] = []
            prev_dt: Optional[date] = None
            for row in rows_sorted:
                dt = parse_iso_date(row.get("captured_at") or row.get("ts"))
                rating_name = str(row.get("rating") or "good").lower()
                g = int(row.get("score") or RATING_TO_G.get(rating_name, 3))
                g = max(1, min(4, g))
                elapsed = max(1, (dt - prev_dt).days) if (dt and prev_dt) else 1
                if dt:
                    prev_dt = dt
                outcome = 0.0 if (g == 1 or row.get("grade") == "lapsed") else 1.0
                traj.append((g, elapsed, outcome))
            if len(traj) >= 2:
                trajectories.append(traj)

        # Fallback synthetic trajectory links from individual blind_reviews if receipts lack full encode history
        if not trajectories:
            for r in blind_reviews:
                trans = r.get("fsrs_transition") or {}
                s_bef = as_finite_float(trans.get("s_before"), 3.7145) or 3.7145
                ret = clamp_num(as_finite_float(trans.get("retrievability"), 0.9) or 0.9, 0.05, 0.99)
                elapsed_est = max(1, int(round(s_bef * ((ret ** (1.0 / FSRS_DECAY)) - 1.0) / FSRS_FACTOR)))
                rating_name = str(r.get("rating") or "good").lower()
                g = max(1, min(4, int(r.get("score") or RATING_TO_G.get(rating_name, 3))))
                outcome = 0.0 if g == 1 else 1.0
                trajectories.append([(3, 0, 1.0), (g, elapsed_est, outcome)])

        base_w = cls.normalize_weights(current_w)
        loss_before = cls._bce_loss(base_w, trajectories)
        w = list(base_w)
        best_loss = loss_before

        # Coordinate descent over W[0..16] across 3 sweeps
        for _sweep in range(3):
            for idx, (lo, hi) in enumerate(FIT_W_BOUNDS):
                cur_val = w[idx]
                for scale in (0.80, 0.90, 0.95, 1.05, 1.12, 1.25):
                    cand_val = clamp_num(cur_val * scale if cur_val > 0 else (lo + hi) * 0.5, lo, hi)
                    trial = list(w)
                    trial[idx] = cand_val
                    # Enforce monotonicity on S0 weights w[0..3]
                    if idx < 4:
                        for j in range(1, 4):
                            trial[j] = max(trial[j], trial[j - 1])
                    l_trial = cls._bce_loss(trial, trajectories)
                    if l_trial + 1e-7 < best_loss:
                        best_loss = l_trial
                        w = trial

        # Compute empirical vs predicted recall and interval multiplier
        observed = sum(0.0 if (r.get("rating") == "again" or r.get("grade") == "lapsed" or r.get("score") == 1) else 1.0 for r in blind_reviews) / float(n_reviews)
        predicted = sum(
            as_finite_float((r.get("fsrs_transition") or {}).get("retrievability") or r.get("retrievability"), 0.9) or 0.9
            for r in blind_reviews
        ) / float(n_reviews)

        def _inv_curve(r_val: float) -> float:
            return (clamp_num(r_val, 0.50, 0.995) ** (1.0 / FSRS_DECAY)) - 1.0

        multiplier = clamp_num(_inv_curve(predicted) / max(1e-6, _inv_curve(observed)), MULTIPLIER_MIN, MULTIPLIER_MAX)
        accepted = best_loss <= loss_before
        final_w = [round(x, 4) for x in (w if accepted else base_w)]

        return {
            "ok": True,
            "accepted": accepted,
            "n_blind_reviews": n_reviews,
            "loss_before": round(loss_before, 6),
            "loss_after": round(best_loss, 6),
            "observed_recall": round(observed, 4),
            "predicted_recall": round(predicted, 4),
            "interval_multiplier": round(multiplier, 3),
            "fsrs_params": final_w,
        }


# ==============================================================================
# SECTION 5 — STASHENGINE (CLAIM-CHECK & ZERO-CONTEXT ISOLATION)
# ==============================================================================

PRODUCTION_MAX_CHARS: int = 2400
ALLOWED_EVENT_KINDS: Tuple[str, ...] = ("encode", "review", "pretest", "transfer", "audit")


class StashEngine:
    """
    Claim-Check Stash & Zero-Context Isolation Engine (RFC §3.1.3).
    Computes canonical stash_sha256 over {claim, probe, production, rubric},
    manages stash.jsonl (`add`, `pop`, `list`, `clear`), and emits zero-context
    AssessorEnvelope objects (`export-assessor`) stripped of FSRS and transcript fields.
    """

    @staticmethod
    def compute_stash_sha256(
        claim: str,
        probe: str,
        production: str,
        rubric: Sequence[str],
    ) -> str:
        canonical = json.dumps(
            {
                "claim": str(claim),
                "probe": str(probe),
                "production": str(production),
                "rubric": [str(r) for r in rubric],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def create_record(
        cls,
        raw: Dict[str, Any],
        node_lookup: Optional[Dict[str, Any]] = None,
    ) -> StashRecord:
        if not isinstance(raw, dict):
            raise ValidationError("Stash item must be a JSON object.")
        topic = VaultGate.validate_slug(raw.get("topic"), "topic")
        node = VaultGate.validate_slug(raw.get("node"), "node")

        node_obj = node_lookup or {}
        event_kind = str(raw.get("event_kind") or raw.get("kind") or "encode").strip()
        if event_kind not in ALLOWED_EVENT_KINDS:
            raise ValidationError(f"Invalid stash event_kind {event_kind!r}; allowed: {ALLOWED_EVENT_KINDS}.")

        node_kind = str(raw.get("node_kind") or node_obj.get("kind") or "concept").strip()
        if node_kind not in NODE_KINDS_ALLOWED:
            raise ValidationError(f"Invalid stash node_kind {node_kind!r}; allowed: {NODE_KINDS_ALLOWED}.")

        claim = raw.get("claim") if raw.get("claim") is not None else node_obj.get("claim")
        probe = raw.get("probe") if raw.get("probe") is not None else node_obj.get("probe")
        rubric_raw = raw.get("rubric") if raw.get("rubric") is not None else node_obj.get("rubric")

        if not isinstance(claim, str) or not claim.strip():
            raise ValidationError(f"Stash item for {topic}/{node} missing non-empty 'claim'.")
        if not isinstance(probe, str) or not probe.strip():
            raise ValidationError(f"Stash item for {topic}/{node} missing non-empty 'probe'.")
        if not isinstance(rubric_raw, list) or not rubric_raw or not all(
            isinstance(x, str) and x.strip() for x in rubric_raw
        ):
            raise ValidationError(f"Stash item for {topic}/{node} missing non-empty 'rubric' list.")

        produced_flag = raw.get("produced")
        raw_prod = raw.get("production")
        if raw_prod is None:
            if produced_flag is False:
                raw_prod = ""
            else:
                raise ValidationError(f"Stash item for {topic}/{node} missing 'production'.")
        if not isinstance(raw_prod, str):
            raise ValidationError("Stash 'production' must be a string.")

        produced = bool(produced_flag) if isinstance(produced_flag, bool) else bool(raw_prod.strip())
        clipped = False
        prod = raw_prod
        if len(prod) > PRODUCTION_MAX_CHARS:
            prod = prod[:PRODUCTION_MAX_CHARS]
            clipped = True

        conf_raw = raw.get("confidence")
        confidence: Optional[int] = None
        if conf_raw is not None:
            c_num = as_finite_float(conf_raw)
            if c_num is None:
                raise ValidationError(f"Invalid confidence value: {conf_raw!r}")
            c_int = int(round(c_num))
            # Support 1..4 scale (or map 0..100 scale to 1..4 if legacy)
            if 1 <= c_int <= 4:
                confidence = c_int
            elif 0 <= c_int <= 100:
                confidence = max(1, min(4, 1 + (c_int // 26)))
            else:
                raise ValidationError(f"Confidence must be in 1..4 (got {conf_raw!r}).")

        hint_used = max(0, int(as_finite_float(raw.get("hint_used"), 0.0) or 0))
        captured_at = str(raw.get("captured_at") or current_iso_timestamp())
        rubric_tuple = tuple(str(x) for x in rubric_raw)
        sha256_hex = cls.compute_stash_sha256(claim, probe, prod, rubric_tuple)

        sid = raw.get("sid")
        if not isinstance(sid, str) or not sid.strip():
            ts_compact = captured_at.replace("-", "").replace(":", "")
            sid = f"st-{ts_compact}-{sha256_hex[:6]}"
        else:
            VaultGate.validate_slug(sid, "sid")

        return StashRecord(
            sid=sid,
            captured_at=captured_at,
            topic=topic,
            node=node,
            event_kind=event_kind,
            node_kind=node_kind,
            claim=claim,
            probe=probe,
            rubric=rubric_tuple,
            production=prod,
            production_clipped=clipped,
            confidence=confidence,
            hint_used=hint_used,
            stash_sha256=sha256_hex,
            produced=produced,
        )

    @classmethod
    def to_assessor_envelope(cls, entry: Union[StashRecord, Dict[str, Any]]) -> AssessorEnvelope:
        if isinstance(entry, StashRecord):
            d = entry.to_dict()
        elif isinstance(entry, dict):
            d = entry
        else:
            raise ValidationError("Invalid stash entry for export-assessor.")

        claim = str(d.get("claim") or "")
        probe = str(d.get("probe") or "")
        prod = str(d.get("production") or "")
        rubric = tuple(str(x) for x in (d.get("rubric") or []))
        expected_sha = cls.compute_stash_sha256(claim, probe, prod, rubric)
        stored_sha = d.get("stash_sha256") or expected_sha
        if stored_sha != expected_sha:
            raise ValidationError(
                f"Stash record {d.get('sid')!r} has corrupted stash_sha256 ({stored_sha} != {expected_sha})."
            )
        ev_kind = str(d.get("event_kind") or d.get("kind") or "encode")
        n_kind = str(d.get("node_kind") or "concept")
        produced = bool(d["produced"]) if isinstance(d.get("produced"), bool) else bool(prod.strip())
        return AssessorEnvelope(
            sid=str(d["sid"]),
            stash_sha256=stored_sha,
            topic=str(d["topic"]),
            node=str(d["node"]),
            kind=ev_kind,
            event_kind=ev_kind,
            node_kind=n_kind,
            claim=claim,
            probe=probe,
            rubric=rubric,
            production=prod,
            production_clipped=bool(d.get("production_clipped", False)),
            confidence=d.get("confidence"),
            produced=produced,
        )


# ==============================================================================
# SECTION 6 — ASTEVAL (PURE RESTRICTED MATH VERIFIER & OPT-03 SLIP DETECTOR)
# ==============================================================================

AST_MAX_NODES: int = 256
AST_MAX_DEPTH: int = 24
AST_DEADLINE_S: float = 0.500
AST_NUM_POINTS: int = 16


def _safe_factorial(n: Union[int, float]) -> float:
    val = as_finite_float(n)
    if val is None or abs(val - round(val)) > 1e-9:
        raise ValidationError(f"factorial(n) requires an integer argument, got {n!r}.")
    ni = int(round(val))
    if ni < 0 or ni > 170:
        raise ValidationError(f"factorial(n) domain error: requires 0 <= n <= 170, got {ni}.")
    return float(math.factorial(ni))


def _safe_comb(n: Union[int, float], k: Union[int, float]) -> float:
    vn, vk = as_finite_float(n), as_finite_float(k)
    if vn is None or vk is None or abs(vn - round(vn)) > 1e-9 or abs(vk - round(vk)) > 1e-9:
        raise ValidationError(f"comb(n, k) requires integer arguments, got ({n!r}, {k!r}).")
    ni, ki = int(round(vn)), int(round(vk))
    if ni < 0 or ni > 170 or ki < 0 or ki > ni:
        raise ValidationError(f"comb(n, k) domain error: requires 0 <= k <= n <= 170, got ({ni}, {ki}).")
    return float(math.comb(ni, ki))


def _safe_perm(n: Union[int, float], k: Optional[Union[int, float]] = None) -> float:
    vn = as_finite_float(n)
    vk = vn if k is None else as_finite_float(k)
    if vn is None or vk is None or abs(vn - round(vn)) > 1e-9 or abs(vk - round(vk)) > 1e-9:
        raise ValidationError(f"perm(n, k) requires integer arguments, got ({n!r}, {k!r}).")
    ni, ki = int(round(vn)), int(round(vk))
    if ni < 0 or ni > 170 or ki < 0 or ki > ni:
        raise ValidationError(f"perm(n, k) domain error: requires 0 <= k <= n <= 170, got ({ni}, {ki}).")
    return float(math.perm(ni, ki))


def _safe_exp(x: Union[int, float]) -> float:
    vx = as_finite_float(x)
    if vx is None or abs(vx) > 709.0:
        raise ValidationError(f"exp(x) domain error: requires |x| <= 709, got {x!r}.")
    return math.exp(vx)


def _safe_gcd(a: Union[int, float], b: Union[int, float]) -> float:
    va, vb = as_finite_float(a), as_finite_float(b)
    if va is None or vb is None or abs(va - round(va)) > 1e-9 or abs(vb - round(vb)) > 1e-9:
        raise ValidationError(f"gcd(a, b) requires integer arguments, got ({a!r}, {b!r}).")
    ai, bi = int(round(va)), int(round(vb))
    if abs(ai) > 10**18 or abs(bi) > 10**18:
        raise ValidationError(f"gcd(a, b) domain error: requires |a|, |b| <= 10^18, got ({ai}, {bi}).")
    return float(math.gcd(ai, bi))


def _safe_sqrt(x: Union[int, float]) -> float:
    vx = as_finite_float(x)
    if vx is None or vx < 0:
        raise ValueError("sqrt of negative number")
    return math.sqrt(vx)


def _safe_log(x: Union[int, float], base: Optional[Union[int, float]] = None) -> float:
    vx = as_finite_float(x)
    if vx is None or vx <= 0:
        raise ValueError("log of non-positive number")
    if base is not None:
        vb = as_finite_float(base)
        if vb is None or vb <= 0 or vb == 1.0:
            raise ValueError("invalid log base")
        return math.log(vx, vb)
    return math.log(vx)


SAFE_MATH_FUNCTIONS: Dict[str, Tuple[Callable[..., float], Tuple[int, ...]]] = {
    "sqrt": (_safe_sqrt, (1,)),
    "exp": (_safe_exp, (1,)),
    "ln": (_safe_log, (1,)),
    "log": (_safe_log, (1, 2)),
    "log2": (lambda x: math.log2(float(x)) if float(x) > 0 else (_ for _ in ()).throw(ValueError("log2<=0")), (1,)),
    "log10": (lambda x: math.log10(float(x)) if float(x) > 0 else (_ for _ in ()).throw(ValueError("log10<=0")), (1,)),
    "sin": (lambda x: math.sin(float(x)), (1,)),
    "cos": (lambda x: math.cos(float(x)), (1,)),
    "tan": (lambda x: math.tan(float(x)), (1,)),
    "asin": (lambda x: math.asin(float(x)), (1,)),
    "acos": (lambda x: math.acos(float(x)), (1,)),
    "atan": (lambda x: math.atan(float(x)), (1,)),
    "abs": (lambda x: float(abs(float(x))), (1,)),
    "factorial": (_safe_factorial, (1,)),
    "comb": (_safe_comb, (2,)),
    "perm": (_safe_perm, (1, 2)),
    "gcd": (_safe_gcd, (2,)),
}

SAFE_MATH_CONSTANTS: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}


class ASTEval:
    r"""
    Restricted AST mathematical verifier (`verify-expr`, RFC §3.3.3 & OPT-03).
    - Normalizes LaTeX (\frac, \sqrt, ^, implicit multiplication).
    - Enforces <= 256 AST nodes, depth <= 24, strict node allowlist, exponent/domain caps,
      and <= 500ms wall-clock deadline.
    - Evaluates expected expression once across 16 deterministic points (y_E) and diagnoses
      5 structural slips: off_by_one_plus, off_by_one_minus, missing_factor_2, extra_factor_2, sign_flip.
    """

    @staticmethod
    def _replace_latex_command_1(s: str, cmd: str, fn_name: str) -> str:
        pattern = "\\" + cmd + "{"
        while pattern in s:
            idx = s.find(pattern)
            brace_start = idx + len(cmd) + 1
            depth = 0
            end_idx = -1
            for i in range(brace_start, len(s)):
                if s[i] == "{":
                    depth += 1
                elif s[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
            if end_idx == -1:
                break
            inner = s[brace_start + 1 : end_idx]
            s = s[:idx] + f"{fn_name}({inner})" + s[end_idx + 1 :]
        return s

    @staticmethod
    def _replace_latex_frac(s: str) -> str:
        pattern = "\\frac{"
        while pattern in s:
            idx = s.find(pattern)
            b1_start = idx + 5
            depth = 0
            b1_end = -1
            for i in range(b1_start, len(s)):
                if s[i] == "{":
                    depth += 1
                elif s[i] == "}":
                    depth -= 1
                    if depth == 0:
                        b1_end = i
                        break
            if b1_end == -1:
                break
            rem = s[b1_end + 1 :].lstrip()
            if not rem.startswith("{"):
                break
            b2_start = len(s) - len(rem)
            depth = 0
            b2_end = -1
            for i in range(b2_start, len(s)):
                if s[i] == "{":
                    depth += 1
                elif s[i] == "}":
                    depth -= 1
                    if depth == 0:
                        b2_end = i
                        break
            if b2_end == -1:
                break
            num = s[b1_start + 1 : b1_end]
            den = s[b2_start + 1 : b2_end]
            s = s[:idx] + f"(({num})/({den}))" + s[b2_end + 1 :]
        return s

    @classmethod
    def normalize_expr(cls, raw_expr: str) -> str:
        if not isinstance(raw_expr, str) or not raw_expr.strip():
            raise ValidationError("Expression must be a non-empty string.")
        s = raw_expr.strip()
        # Strip surrounding $ or $$
        while s.startswith("$") and s.endswith("$") and len(s) >= 2:
            s = s[1:-1].strip()
        s = s.replace("\\left", "").replace("\\right", "")
        s = s.replace("\\cdot", "*").replace("\\times", "*")
        s = s.replace("\\pi", "pi")
        s = cls._replace_latex_frac(s)
        s = cls._replace_latex_command_1(s, "sqrt", "sqrt")
        for fn in ("sin", "cos", "tan", "ln", "log", "exp"):
            s = re.sub(r"\\" + fn + r"\b", fn, s)
        # Convert Remaining { and } to ( and )
        s = s.replace("{", "(").replace("}", ")")
        s = s.replace("^", "**")

        # Implicit multiplication:
        # 1) number followed by identifier or '(' -> 2x => 2*x, 2(x) => 2*(x)
        s = re.sub(r"(\d(?:\.\d+)?)\s*([A-Za-z(])", r"\1*\2", s)
        # 2) ')' followed by number, identifier, or '(' -> )( => )*(, )x => )*x
        s = re.sub(r"\)\s*([0-9A-Za-z(])", r")*\1", s)
        # 3) single-letter variable followed by '(' -> n(n-1) => n*(n-1)
        s = re.sub(r"\b([A-Za-z])\s*\(", r"\1*(", s)
        return s.strip()

    @classmethod
    def parse_and_validate_ast(
        cls,
        expr_str: str,
        declared_vars: Optional[Set[str]] = None,
    ) -> Tuple[ast.Expression, Set[str]]:
        norm = cls.normalize_expr(expr_str)
        try:
            tree = ast.parse(norm, mode="eval")
        except SyntaxError as exc:
            raise ValidationError(f"Syntax error in expression {expr_str!r} (normalized: {norm!r}): {exc}") from exc

        node_count = 0
        discovered_vars: Set[str] = set()

        def walk(node: ast.AST, depth: int) -> None:
            nonlocal node_count
            node_count += 1
            if node_count > AST_MAX_NODES:
                raise ValidationError(
                    f"AST complexity limit exceeded: > {AST_MAX_NODES} nodes in {expr_str!r}."
                )
            if depth > AST_MAX_DEPTH:
                raise ValidationError(
                    f"AST depth limit exceeded: depth > {AST_MAX_DEPTH} in {expr_str!r}."
                )

            if isinstance(node, ast.Expression):
                walk(node.body, depth + 1)
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                    raise ValidationError(
                        f"Disallowed constant {node.value!r} in math expression (only finite int/float allowed)."
                    )
                if math.isnan(float(node.value)) or math.isinf(float(node.value)):
                    raise ValidationError("Non-finite constant in math expression.")
            elif isinstance(node, ast.Name):
                if not isinstance(node.ctx, ast.Load):
                    raise ValidationError("Only Load context is allowed for variable names.")
                ident = node.id
                if ident in SAFE_MATH_CONSTANTS or ident in SAFE_MATH_FUNCTIONS:
                    return
                if declared_vars is not None and ident not in declared_vars:
                    raise ValidationError(
                        f"Undeclared variable {ident!r} in expression {expr_str!r}; allowed: {sorted(declared_vars)}."
                    )
                discovered_vars.add(ident)
            elif isinstance(node, ast.UnaryOp):
                if not isinstance(node.op, (ast.UAdd, ast.USub)):
                    raise ValidationError(f"Disallowed unary operator {type(node.op).__name__}.")
                walk(node.operand, depth + 1)
            elif isinstance(node, ast.BinOp):
                if not isinstance(
                    node.op,
                    (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow),
                ):
                    raise ValidationError(f"Disallowed binary operator {type(node.op).__name__}.")
                walk(node.left, depth + 1)
                walk(node.right, depth + 1)
            elif isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_MATH_FUNCTIONS:
                    fname = getattr(node.func, "id", type(node.func).__name__)
                    raise ValidationError(f"Disallowed function call {fname!r} in math expression.")
                if node.keywords:
                    raise ValidationError("Keyword arguments are not permitted in math expressions.")
                _, allowed_arities = SAFE_MATH_FUNCTIONS[node.func.id]
                if len(node.args) not in allowed_arities:
                    raise ValidationError(
                        f"Function {node.func.id!r} expects {allowed_arities} argument(s), got {len(node.args)}."
                    )
                for arg in node.args:
                    walk(arg, depth + 1)
            else:
                raise ValidationError(
                    f"Disallowed AST node {type(node).__name__} in expression {expr_str!r}."
                )

        walk(tree, 1)
        return tree, discovered_vars

    @classmethod
    def eval_ast(
        cls,
        tree: ast.Expression,
        env: Dict[str, float],
        deadline_monotonic: float,
    ) -> float:
        def _eval(node: ast.AST) -> float:
            if time.monotonic() > deadline_monotonic:
                raise ValidationError("Expression evaluation exceeded 500ms wall-clock deadline.")
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            if isinstance(node, ast.Constant):
                return float(node.value)
            if isinstance(node, ast.Name):
                if node.id in SAFE_MATH_CONSTANTS:
                    return SAFE_MATH_CONSTANTS[node.id]
                if node.id in env:
                    return float(env[node.id])
                raise ValidationError(f"Unbound variable {node.id!r}.")
            if isinstance(node, ast.UnaryOp):
                v = _eval(node.operand)
                return +v if isinstance(node.op, ast.UAdd) else -v
            if isinstance(node, ast.BinOp):
                left = _eval(node.left)
                right = _eval(node.right)
                if isinstance(node.op, ast.Add):
                    res = left + right
                elif isinstance(node.op, ast.Sub):
                    res = left - right
                elif isinstance(node.op, ast.Mult):
                    res = left * right
                elif isinstance(node.op, ast.Div):
                    if abs(right) < 1e-15:
                        raise ZeroDivisionError("division by zero")
                    res = left / right
                elif isinstance(node.op, ast.FloorDiv):
                    if abs(right) < 1e-15:
                        raise ZeroDivisionError("floor division by zero")
                    res = float(math.floor(left / right))
                elif isinstance(node.op, ast.Mod):
                    if abs(right) < 1e-15:
                        raise ZeroDivisionError("modulo by zero")
                    res = left % right
                elif isinstance(node.op, ast.Pow):
                    if abs(right) > 1000.0 or (abs(left) > 1e6 and abs(right) > 12.0):
                        raise ValidationError(
                            f"Exponent guard triggered: Pow({left}, {right}) exceeds safe numeric bounds."
                        )
                    if left < 0 and abs(right - round(right)) > 1e-9:
                        raise ValueError("negative base with fractional exponent")
                    res = float(left ** right)
                else:
                    raise ValidationError(f"Unsupported operator {type(node.op).__name__}.")
                if math.isnan(res) or math.isinf(res):
                    raise OverflowError("non-finite intermediate result")
                return res
            if isinstance(node, ast.Call):
                assert isinstance(node.func, ast.Name)
                fn, _ = SAFE_MATH_FUNCTIONS[node.func.id]
                args = [_eval(a) for a in node.args]
                res = float(fn(*args))
                if math.isnan(res) or math.isinf(res):
                    raise OverflowError("non-finite function result")
                return res
            raise ValidationError(f"Unsupported AST node {type(node).__name__}.")

        return _eval(tree)

    @staticmethod
    def _uses_integer_combinatorics(tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("factorial", "comb", "perm", "gcd"):
                    return True
        return False

    @classmethod
    def _generate_sample_points(
        cls,
        variables: Sequence[str],
        integer_mode: bool,
        n_points: int = AST_NUM_POINTS,
    ) -> List[Dict[str, float]]:
        if not variables:
            return [{}]
        seed_bytes = hashlib.sha256((",".join(variables)).encode("utf-8")).digest()
        rng = random.Random(int.from_bytes(seed_bytes[:8], "big"))
        points: List[Dict[str, float]] = []
        for idx in range(n_points):
            pt: Dict[str, float] = {}
            for v_idx, var in enumerate(variables):
                if integer_mode:
                    # Ensure ni >= ki if variables are (n, k)
                    pt[var] = float(4 + idx + (v_idx * 2 if v_idx == 0 else 0))
                else:
                    # Positive non-integer points in [0.35, 4.85] avoiding 0, 1, pi/2 poles
                    pt[var] = round(0.37 + 0.23 * idx + rng.uniform(0.05, 0.45), 6)
            points.append(pt)
        return points

    @classmethod
    def verify_expressions(
        cls,
        expected_expr: str,
        actual_expr: str,
        explicit_vars: Optional[Sequence[str]] = None,
    ) -> VerifyExprReport:
        """
        OPT-03: Evaluates expected AST T_E once across P=16 deterministic points to cache y_E,
        evaluates actual AST T_A, and checks equivalence and 5 structural slip candidates:
          - off_by_one_plus   (y_A == y_E + 1)
          - off_by_one_minus  (y_A == y_E - 1)
          - missing_factor_2  (y_A == y_E / 2)
          - extra_factor_2    (y_A == 2 * y_E)
          - sign_flip         (y_A == -y_E)
        """
        t0 = time.monotonic()
        deadline = t0 + AST_DEADLINE_S

        decl_set = set(explicit_vars) if explicit_vars else None
        tree_e, vars_e = cls.parse_and_validate_ast(expected_expr, decl_set)
        tree_a, vars_a = cls.parse_and_validate_ast(actual_expr, decl_set)

        if decl_set is None:
            # If expected has variables and actual introduces completely foreign variables,
            # union them so mismatch is caught cleanly via evaluation or check
            all_vars = tuple(sorted(vars_e | vars_a))
        else:
            all_vars = tuple(sorted(decl_set))

        int_mode = cls._uses_integer_combinatorics(tree_e) or cls._uses_integer_combinatorics(tree_a)
        sample_points = cls._generate_sample_points(all_vars, int_mode, n_points=AST_NUM_POINTS)

        y_e: List[float] = []
        y_a: List[float] = []

        for pt in sample_points:
            try:
                ve = cls.eval_ast(tree_e, pt, deadline)
            except (ZeroDivisionError, ValueError, OverflowError):
                continue
            try:
                va = cls.eval_ast(tree_a, pt, deadline)
            except (ZeroDivisionError, ValueError, OverflowError):
                # Actual fails where expected is well-defined
                va = float("inf")
            y_e.append(ve)
            y_a.append(va)

        if not y_e:
            raise ValidationError(f"Could not evaluate expected expression {expected_expr!r} on domain points.")

        def _vec_matches(target_vec: Sequence[float], actual_vec: Sequence[float]) -> Tuple[bool, float, float]:
            max_abs = 0.0
            max_rel = 0.0
            for te, ta in zip(target_vec, actual_vec):
                if math.isinf(ta) or math.isnan(ta):
                    return False, float("inf"), float("inf")
                diff = abs(te - ta)
                scale = max(1.0, abs(te))
                rel = diff / scale
                max_abs = max(max_abs, diff)
                max_rel = max(max_rel, rel)
                if diff > 1e-7 * scale:
                    return False, max_abs, max_rel
            return True, max_abs, max_rel

        equiv, max_abs_err, max_rel_err = _vec_matches(y_e, y_a)
        slip_candidate = False
        slip_kind: Optional[str] = None
        error_class_hint: Optional[str] = None

        if not equiv:
            # Test 5 structural slip candidates in O(P) against cached y_E
            slip_transforms: Tuple[Tuple[str, List[float]], ...] = (
                ("off_by_one_plus", [v + 1.0 for v in y_e]),
                ("off_by_one_minus", [v - 1.0 for v in y_e]),
                ("missing_factor_2", [v * 0.5 for v in y_e]),
                ("extra_factor_2", [v * 2.0 for v in y_e]),
                ("sign_flip", [-v for v in y_e]),
            )
            for s_name, s_vec in slip_transforms:
                matched, _, _ = _vec_matches(s_vec, y_a)
                if matched and any(abs(ve - sv) > 1e-9 for ve, sv in zip(y_e, s_vec)):
                    slip_candidate = True
                    slip_kind = s_name
                    error_class_hint = "slip"
                    break
            if not slip_candidate:
                error_class_hint = "conceptual"

        runtime_ms = (time.monotonic() - t0) * 1000.0
        return VerifyExprReport(
            expected=expected_expr,
            actual=actual_expr,
            variables=all_vars,
            equivalent=equiv,
            slip_candidate=slip_candidate,
            slip_kind=slip_kind,
            error_class_hint=error_class_hint,
            max_abs_error=0.0 if math.isinf(max_abs_err) else max_abs_err,
            max_rel_error=0.0 if math.isinf(max_rel_err) else max_rel_err,
            points_tested=len(y_e),
            runtime_ms=runtime_ms,
        )


# ==============================================================================
# SECTION 7 — MDCOMPILER (SEC-YAML-01 SPAN-PRESERVING PATCHER, OCC & MOC)
# ==============================================================================

_FRONTMATTER_RE = re.compile(r"\A(?:\ufeff)?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_TOP_YAML_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):[ \t]*(.*)$")
_MANAGED_START = "<!-- mnemosyne:start -->"
_MANAGED_END = "<!-- mnemosyne:end -->"

MANAGED_YAML_ORDER: Tuple[str, ...] = (
    "title",
    "aliases",
    "tags",
    "status",
    "mnemosyne_schema",
    "mnemosyne_topic",
    "mnemosyne_node",
    "mnemosyne_kind",
    "mnemosyne_sid",
    "mnemosyne_body_hash",
    "fsrs_state",
    "fsrs_stability",
    "fsrs_difficulty",
    "fsrs_due",
    "fsrs_last",
    "fsrs_reps",
    "fsrs_lapses",
    "sr-due",
    "sr-interval",
    "sr-ease",
)


class MDCompiler:
    """
    SEC-YAML-01 Span-Preserving Stdlib YAML Frontmatter Patcher,
    <!-- mnemosyne:start --> ... <!-- mnemosyne:end --> Managed Block Compiler with OCC,
    5 Epistemological Callout Builder, and <Topic> MoC.md Compiler.
    """

    @staticmethod
    def neutralize_markdown_injections(text: str) -> str:
        """
        SEC-MD-01: Neutralizes embedded <!-- mnemosyne:start/end --> markers and standalone ---
        YAML fences inside untrusted learner productions, rationales, and claims.
        """
        if not isinstance(text, str):
            return ""
        cleaned = text.replace("\x00", "").replace("\r\n", "\n")
        cleaned = re.sub(
            r"<!--\s*mnemosyne\s*:\s*(start|end)\s*-->",
            r"<!- - mnemosyne:\1 - ->",
            cleaned,
            flags=re.I,
        )
        cleaned = re.sub(r"(?m)^---[ \t]*$", r"\\---", cleaned)
        return cleaned

    @staticmethod
    def compute_body_hash(managed_inner_text: str) -> str:
        norm = managed_inner_text.replace("\x00", "").replace("\r\n", "\n").strip()
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    @classmethod
    def parse_frontmatter_spans(
        cls, markdown_text: str
    ) -> Tuple[List[Tuple[str, str]], Dict[str, Any], str]:
        """
        SEC-YAML-01: Splits opening YAML frontmatter into ordered (key, raw_span_text) tuples,
        extracts parsed scalar/list values for Mnemosyne/SR keys, and returns body after frontmatter.
        Raises ConcurrencyOrCorruptionError (Exit Code 3) if opening frontmatter is malformed.
        """
        norm = markdown_text.replace("\x00", "").replace("\r\n", "\n")
        if norm.lstrip("\ufeff").startswith("---"):
            m = _FRONTMATTER_RE.match(norm)
            if not m:
                raise ConcurrencyOrCorruptionError(
                    "Malformed YAML frontmatter: opening '---' without valid closing '---'."
                )
            yaml_block = m.group(1)
            rest_body = norm[m.end() :]
        else:
            raise ConcurrencyOrCorruptionError(
                "Missing opening YAML frontmatter '---' block on existing managed file."
            )

        spans: List[Tuple[str, str]] = []
        parsed_values: Dict[str, Any] = {}
        lines = yaml_block.split("\n")
        cur_key: Optional[str] = None
        cur_lines: List[str] = []

        def flush_current() -> None:
            nonlocal cur_key, cur_lines
            if cur_key is not None:
                raw_span = "\n".join(cur_lines)
                spans.append((cur_key, raw_span))
                parsed_values[cur_key] = cls._parse_yaml_span_value(cur_lines)
            cur_key = None
            cur_lines = []

        for line in lines:
            if not line.strip() or line.lstrip().startswith("#"):
                if cur_key is not None:
                    cur_lines.append(line)
                continue
            if not line.startswith((" ", "\t")):
                km = _TOP_YAML_KEY_RE.match(line)
                if not km:
                    raise ConcurrencyOrCorruptionError(
                        f"Malformed top-level YAML frontmatter line: {line!r}"
                    )
                flush_current()
                cur_key = km.group(1)
                cur_lines = [line]
            else:
                if cur_key is None:
                    raise ConcurrencyOrCorruptionError(
                        f"Unexpected indented YAML line before any key: {line!r}"
                    )
                cur_lines.append(line)
        flush_current()
        return spans, parsed_values, rest_body

    @staticmethod
    def _parse_yaml_span_value(span_lines: Sequence[str]) -> Any:
        if not span_lines:
            return None
        first = span_lines[0]
        km = _TOP_YAML_KEY_RE.match(first)
        if not km:
            return None
        inline_val = km.group(2).strip()
        if len(span_lines) == 1:
            if not inline_val or inline_val in ("null", "~"):
                return None
            if inline_val.startswith("[") and inline_val.endswith("]"):
                inner = inline_val[1:-1].strip()
                if not inner:
                    return []
                items = []
                for part in inner.split(","):
                    p = part.strip().strip('"').strip("'")
                    if p:
                        items.append(p)
                return items
            if (inline_val.startswith('"') and inline_val.endswith('"')) or (
                inline_val.startswith("'") and inline_val.endswith("'")
            ):
                try:
                    if inline_val.startswith('"'):
                        return json.loads(inline_val)
                except json.JSONDecodeError:
                    pass
                return inline_val[1:-1]
            if inline_val in ("true", "false"):
                return inline_val == "true"
            try:
                if "." in inline_val:
                    return float(inline_val)
                return int(inline_val)
            except ValueError:
                return inline_val

        # Multi-line block sequence or scalar
        items_list: List[str] = []
        for sub in span_lines[1:]:
            s = sub.strip()
            if s.startswith("- "):
                val = s[2:].strip().strip('"').strip("'")
                if val:
                    items_list.append(val)
        if items_list:
            return items_list
        return "\n".join(span_lines[1:])

    @staticmethod
    def _format_yaml_key_span(key: str, value: Any) -> str:
        # SEC-YAML-01: sr-due unquoted YYYY-MM-DD; sr-interval & sr-ease bare integers
        if key == "sr-due":
            return f"sr-due: {value}"
        if key in ("sr-interval", "sr-ease", "mnemosyne_schema", "fsrs_reps", "fsrs_lapses"):
            return f"{key}: {int(value or 0)}"
        if key in ("fsrs_stability", "fsrs_difficulty"):
            if value is None:
                return f"{key}: null"
            return f"{key}: {round(float(value), 4)}"
        if isinstance(value, list):
            if not value:
                return f"{key}: []"
            if key == "tags":
                lines = [f"{key}:"]
                for item in value:
                    lines.append(f"  - {item}")
                return "\n".join(lines)
            lines = [f"{key}:"]
            for item in value:
                lines.append(f"  - {json.dumps(str(item), ensure_ascii=False)}")
            return "\n".join(lines)
        if value is None:
            return f"{key}: null"
        if isinstance(value, bool):
            return f"{key}: {'true' if value else 'false'}"
        if isinstance(value, (int, float)):
            return f"{key}: {value}"
        return f"{key}: {json.dumps(str(value), ensure_ascii=False)}"

    @classmethod
    def patch_frontmatter(
        cls,
        existing_spans: Optional[Sequence[Tuple[str, str]]],
        existing_parsed: Optional[Dict[str, Any]],
        managed_updates: Dict[str, Any],
        required_tags: Sequence[str],
        required_aliases: Sequence[str],
    ) -> str:
        """
        SEC-YAML-01: Merges required tags & aliases additively and preserves unknown
        user-authored YAML key spans byte-for-byte in their original position.
        """
        spans = list(existing_spans or [])
        parsed = dict(existing_parsed or {})

        # Additive merge for aliases
        cur_aliases = parsed.get("aliases")
        merged_aliases: List[str] = []
        if isinstance(cur_aliases, list):
            for a in cur_aliases:
                if str(a) not in merged_aliases:
                    merged_aliases.append(str(a))
        for req_a in required_aliases:
            if req_a and req_a not in merged_aliases:
                merged_aliases.append(req_a)

        # Additive merge for tags
        cur_tags = parsed.get("tags")
        merged_tags: List[str] = []
        if isinstance(cur_tags, list):
            for t in cur_tags:
                clean_t = str(t).lstrip("#").strip()
                if clean_t and clean_t not in merged_tags:
                    merged_tags.append(clean_t)
        elif isinstance(cur_tags, str) and cur_tags.strip():
            for t in cur_tags.split():
                clean_t = t.lstrip("#").strip(",")
                if clean_t and clean_t not in merged_tags:
                    merged_tags.append(clean_t)
        for req_t in required_tags:
            clean_t = str(req_t).lstrip("#").strip()
            if clean_t and clean_t not in merged_tags:
                merged_tags.append(clean_t)

        all_updates = dict(managed_updates)
        all_updates["aliases"] = merged_aliases
        all_updates["tags"] = merged_tags

        emitted_keys: Set[str] = set()
        out_spans: List[str] = []

        # Preserve existing order of keys, updating managed ones in-place and keeping user keys byte-for-byte
        for k, raw_span in spans:
            if k in all_updates:
                if k not in emitted_keys:
                    out_spans.append(cls._format_yaml_key_span(k, all_updates[k]))
                    emitted_keys.add(k)
            else:
                out_spans.append(raw_span)

        # Append any managed keys not yet emitted in canonical MANAGED_YAML_ORDER
        for k in MANAGED_YAML_ORDER:
            if k in all_updates and k not in emitted_keys:
                out_spans.append(cls._format_yaml_key_span(k, all_updates[k]))
                emitted_keys.add(k)

        for k, v in all_updates.items():
            if k not in emitted_keys:
                out_spans.append(cls._format_yaml_key_span(k, v))
                emitted_keys.add(k)

        return "---\n" + "\n".join(out_spans) + "\n---\n"

    @classmethod
    def split_managed_body(cls, body_after_frontmatter: str) -> Tuple[str, str, str]:
        """
        Extracts (prefix_outside, inner_managed_content, suffix_outside) around
        <!-- mnemosyne:start --> and <!-- mnemosyne:end -->.
        Raises ConcurrencyOrCorruptionError (Exit Code 3) if markers are missing, duplicated, or inverted.
        """
        n_start = body_after_frontmatter.count(_MANAGED_START)
        n_end = body_after_frontmatter.count(_MANAGED_END)
        if n_start != 1 or n_end != 1:
            raise ConcurrencyOrCorruptionError(
                f"Corrupted managed block markers: found {n_start} start marker(s) and {n_end} end marker(s)."
            )
        idx_start = body_after_frontmatter.find(_MANAGED_START)
        idx_end = body_after_frontmatter.find(_MANAGED_END)
        if idx_start >= idx_end:
            raise ConcurrencyOrCorruptionError(
                "Corrupted managed block markers: <!-- mnemosyne:end --> appears before <!-- mnemosyne:start -->."
            )
        prefix = body_after_frontmatter[:idx_start]
        inner = body_after_frontmatter[idx_start + len(_MANAGED_START) : idx_end]
        suffix = body_after_frontmatter[idx_end + len(_MANAGED_END) :]
        return prefix, inner, suffix

    @classmethod
    def render_managed_inner_block(
        cls,
        topic: Dict[str, Any],
        node: Dict[str, Any],
        latest_receipt: Optional[Dict[str, Any]],
        node_misconceptions: Sequence[Dict[str, Any]],
        by_id: Dict[str, Dict[str, Any]],
    ) -> str:
        """
        Builds the 5 epistemological callouts/sections inside <!-- mnemosyne:start/end -->:
          1. [!important] Unconditional Truth
          2. ## Motivated Discovery (with Core Claim, Prerequisites, Topic MoC)
          3. [!quote] Learner's Own Words (Verified Receipt)
          4. ## Visual Model
          5. [!warning] Misconceptions & Traps Overcome
        """
        ut = cls.neutralize_markdown_injections(
            node.get("unconditional_truth") or node.get("claim") or ""
        )
        md_disc = cls.neutralize_markdown_injections(
            node.get("motivated_discovery") or node.get("claim") or ""
        )
        claim = cls.neutralize_markdown_injections(node.get("claim") or "")

        reqs = node.get("edges", {}).get("requires", [])
        if reqs:
            req_links = ", ".join(
                f"[[{VaultGate.sanitize_title(by_id[r].get('title', r) if r in by_id else r)}]]"
                for r in reqs
            )
        else:
            req_links = "None (Root Unconditional Truth)"

        moc_title = f"{VaultGate.sanitize_title(topic.get('title') or topic.get('slug', 'Topic'))} MoC"

        # Learner's Own Words
        sid = (latest_receipt or {}).get("sid") or node.get("last_sid") or "unverified"
        rec_ts = (latest_receipt or {}).get("ts") or (node.get("fsrs") or {}).get("last") or current_date().isoformat()
        prod_raw = (latest_receipt or {}).get("production") or node.get("last_production") or "Verified via pretest / spaced-repetition bridge."
        prod_clean = cls.neutralize_markdown_injections(prod_raw).replace("\n", "\n> ")

        # Visual Model
        viz_lines: List[str] = ["## Visual Model"]
        mermaid_code = node.get("mermaid_block")
        if isinstance(mermaid_code, str) and mermaid_code.strip():
            viz_lines.append("```mermaid")
            viz_lines.append(cls.neutralize_markdown_injections(mermaid_code.strip()))
            viz_lines.append("```")
        artifact_rel = node.get("artifact")
        if isinstance(artifact_rel, str) and artifact_rel.strip():
            art_name = Path(artifact_rel).name
            viz_lines.append(f"![[{art_name}|500]]")
        if len(viz_lines) == 1:
            viz_hook = (node.get("viz") or {}).get("hook") if isinstance(node.get("viz"), dict) else None
            viz_lines.append(
                cls.neutralize_markdown_injections(
                    viz_hook or f"Structural dependency mapping for {node.get('title', node.get('id'))}."
                )
            )

        # Misconceptions & Traps Overcome
        trap_lines: List[str] = ["> [!warning] Misconceptions & Traps Overcome"]
        contrasts = node.get("edges", {}).get("contrasts_with", [])
        for c_id in contrasts:
            c_title = VaultGate.sanitize_title(by_id[c_id].get("title", c_id) if c_id in by_id else c_id)
            trap_lines.append(f"> - *Contrast:* [[{c_title}]] — Distinguishes core mechanism and boundary conditions.")
        for m_item in node_misconceptions:
            desc = cls.neutralize_markdown_injections(str(m_item.get("description") or m_item.get("misconception") or ""))
            if desc:
                trap_lines.append(f"> - *Resolved Misconception:* {desc}")
        if len(trap_lines) == 1:
            rubric_items = node.get("rubric") or []
            first_crit = cls.neutralize_markdown_injections(rubric_items[0]) if rubric_items else claim
            trap_lines.append(f"> - *Key Criterion Guard:* {first_crit}")

        sections = [
            f"> [!important] Unconditional Truth\n> {ut.replace(chr(10), chr(10) + '> ')}",
            f"## Motivated Discovery\n{md_disc}\n\n**Core Claim:** {claim}\n\n**Prerequisites:** {req_links} | **Topic MoC:** [[{moc_title}]]",
            f"> [!quote] Learner's Own Words (Verified Receipt `{sid}` · {rec_ts})\n> {prod_clean}",
            "\n".join(viz_lines),
            "\n".join(trap_lines),
        ]
        return "\n\n".join(sections)

    @classmethod
    def compile_note(
        cls,
        store: StateStore,
        topic: Dict[str, Any],
        node: Dict[str, Any],
        latest_receipt: Optional[Dict[str, Any]],
        node_misconceptions: Sequence[Dict[str, Any]],
        by_id: Dict[str, Dict[str, Any]],
    ) -> NoteEnvelope:
        """
        Compiles a single node into either:
          - Fleeting stage: 05 - Fleeting/mnemosyne/<Sanitized Topic>/<Sanitized Node Title>.md (status: "fleeting")
            when unmastered (fsrs.state in ("new", "learning", "relearning") and not yet graduated).
          - Permanent stage: 04 - Permanent/ or 02 - Areas/<Domain>/ (status: "permanent")
            once mastered (state == "review" or latest receipt score >= 3), migrating user prose
            and custom YAML properties from any prior fleeting draft and unlinking the obsolete draft.
        """
        slug = topic["slug"]
        nid = node["id"]
        topic_title = topic.get("title") or slug
        sanitized_topic = VaultGate.sanitize_title(topic_title)
        sanitized_title = VaultGate.sanitize_title(node.get("title") or nid)

        rel_fleeting_path = f"05 - Fleeting/mnemosyne/{sanitized_topic}/{sanitized_title}.md"
        abs_fleeting_path = store.gate.validate_path(
            store.gate.vault_root / rel_fleeting_path,
            mode="w",
            require_in_vault=True,
        )

        note_target = topic.get("note_target", "04 - Permanent")
        if note_target == "02 - Areas":
            domain_dir = VaultGate.sanitize_title(topic.get("domain") or "General")
            rel_perm_path = f"02 - Areas/{domain_dir}/{sanitized_title}.md"
        else:
            rel_perm_path = f"04 - Permanent/{sanitized_title}.md"

        abs_perm_path = store.gate.validate_path(
            store.gate.vault_root / rel_perm_path,
            mode="w",
            require_in_vault=True,
        )

        obs_prev = node.get("obsidian") or {}
        last_score = int(as_finite_float((latest_receipt or {}).get("score"), 0.0) or 0)
        is_graduated = (
            node.get("state") == "review"
            or last_score >= 3
            or (obs_prev.get("status") == "permanent" and abs_perm_path.exists())
        )

        if is_graduated:
            note_status = "permanent"
            rel_note_path = rel_perm_path
            abs_note_path = abs_perm_path
        else:
            note_status = "fleeting"
            rel_note_path = rel_fleeting_path
            abs_note_path = abs_fleeting_path

        inner_managed = cls.render_managed_inner_block(
            topic, node, latest_receipt, node_misconceptions, by_id
        )
        new_body_hash = cls.compute_body_hash(inner_managed)

        fsrs = FSRSState.from_dict(node.get("fsrs"))
        last_sid = node.get("last_sid") or (latest_receipt or {}).get("sid") or f"init-{slug}-{nid}"
        sr_fm = FSRSEngine.to_sr_frontmatter(fsrs, last_sid)

        managed_yaml_updates: Dict[str, Any] = {
            "title": node.get("title") or nid,
            "status": note_status,
            "mnemosyne_schema": SCHEMA_VERSION,
            "mnemosyne_topic": slug,
            "mnemosyne_node": nid,
            "mnemosyne_kind": node.get("kind", "concept"),
            "mnemosyne_sid": last_sid,
            "mnemosyne_body_hash": new_body_hash,
            "fsrs_state": node.get("state", "review" if is_graduated else "learning"),
            "fsrs_stability": fsrs.s if fsrs.s is not None else 0.0,
            "fsrs_difficulty": fsrs.d if fsrs.d is not None else 5.0,
            "fsrs_due": fsrs.due or current_date().isoformat(),
            "fsrs_last": fsrs.last or current_date().isoformat(),
            "fsrs_reps": fsrs.reps,
            "fsrs_lapses": fsrs.lapses,
            "sr-due": sr_fm.sr_due,
            "sr-interval": sr_fm.sr_interval,
            "sr-ease": sr_fm.sr_ease,
        }
        req_tags = [
            "review" if is_graduated else "fleeting",
            f"sr/{node.get('kind', 'concept')}",
            f"mnemosyne/{slug}",
        ]
        req_aliases = [str(node.get("title") or nid), nid]

        conflict_snapshot: Optional[str] = None
        existing_spans: Optional[List[Tuple[str, str]]] = None
        existing_parsed: Optional[Dict[str, Any]] = None

        # Check existing target file OR fleeting draft to migrate on graduation
        prev_fleeting_rel = obs_prev.get("fleeting_path") or rel_fleeting_path
        abs_prev_fleeting = store.gate.validate_path(
            store.gate.vault_root / prev_fleeting_rel,
            mode="w",
            require_in_vault=True,
        )

        if abs_note_path.exists():
            existing_raw = abs_note_path.read_text(encoding="utf-8")
            # Raises ConcurrencyOrCorruptionError (Exit Code 3) if YAML or markers are corrupted
            existing_spans, existing_parsed, rest_body = cls.parse_frontmatter_spans(existing_raw)
            prefix, existing_inner, suffix = cls.split_managed_body(rest_body)

            disk_inner_hash = cls.compute_body_hash(existing_inner)
            recorded_hash = obs_prev.get("body_hash") or existing_parsed.get("mnemosyne_body_hash")
            if recorded_hash and disk_inner_hash != recorded_hash:
                conflict_snapshot = store.snapshot_conflict(slug, nid, existing_raw)
        elif is_graduated and abs_prev_fleeting.exists():
            # Graduation migration: migrate user prose & custom YAML spans from fleeting draft
            fleeting_raw = abs_prev_fleeting.read_text(encoding="utf-8")
            existing_spans, existing_parsed, rest_body = cls.parse_frontmatter_spans(fleeting_raw)
            prefix, existing_inner, suffix = cls.split_managed_body(rest_body)

            disk_inner_hash = cls.compute_body_hash(existing_inner)
            recorded_hash = obs_prev.get("body_hash") or existing_parsed.get("mnemosyne_body_hash")
            if recorded_hash and disk_inner_hash != recorded_hash:
                conflict_snapshot = store.snapshot_conflict(slug, nid, fleeting_raw)
            # Remove "fleeting" tag from migrated tags so permanent note has clean "review" tag
            if isinstance(existing_parsed.get("tags"), list):
                existing_parsed["tags"] = [t for t in existing_parsed["tags"] if str(t).lstrip("#").strip() != "fleeting"]
        else:
            prefix = f"\n# {node.get('title') or nid}\n\n"
            suffix = (
                "\n\n## Personal Notes & Further Connections\n"
                "(User-owned freeform Zettelkasten area — never modified or overwritten by `mnemosyne.py synthesize`.)\n"
            )

        frontmatter_str = cls.patch_frontmatter(
            existing_spans,
            existing_parsed,
            managed_yaml_updates,
            req_tags,
            req_aliases,
        )
        full_markdown = (
            f"{frontmatter_str}"
            f"{prefix}"
            f"{_MANAGED_START}\n"
            f"{inner_managed}\n"
            f"{_MANAGED_END}"
            f"{suffix}"
        )

        # Pre-commit OCC stat check if file existed before
        if abs_note_path.exists() and conflict_snapshot is None:
            st_now = abs_note_path.stat()
            prev_mtime = obs_prev.get("st_mtime_ns")
            prev_size = obs_prev.get("st_size")
            if (
                prev_mtime is not None
                and prev_size is not None
                and (st_now.st_mtime_ns != prev_mtime or st_now.st_size != prev_size)
            ):
                # Re-read and check if managed block or outer prose changed concurrently
                latest_raw = abs_note_path.read_text(encoding="utf-8")
                sp2, pr2, rb2 = cls.parse_frontmatter_spans(latest_raw)
                pfx2, in2, sfx2 = cls.split_managed_body(rb2)
                if cls.compute_body_hash(in2) != (obs_prev.get("body_hash") or pr2.get("mnemosyne_body_hash")):
                    conflict_snapshot = store.snapshot_conflict(slug, nid, latest_raw)
                frontmatter_str = cls.patch_frontmatter(
                    sp2, pr2, managed_yaml_updates, req_tags, req_aliases
                )
                full_markdown = (
                    f"{frontmatter_str}{pfx2}{_MANAGED_START}\n{inner_managed}\n{_MANAGED_END}{sfx2}"
                )

        store.atomic_write_text(abs_note_path, full_markdown, require_in_vault=True)
        st_after = abs_note_path.stat()

        # If graduated to permanent, unlink obsolete fleeting draft so there is never a duplicate
        if is_graduated:
            for fl_candidate in {abs_fleeting_path, abs_prev_fleeting}:
                if fl_candidate.exists() and fl_candidate != abs_note_path:
                    try:
                        fl_candidate.unlink()
                    except OSError:
                        pass

        envelope = NoteEnvelope(
            note_path=rel_note_path,
            body_hash=new_body_hash,
            st_mtime_ns=st_after.st_mtime_ns,
            st_size=st_after.st_size,
            status=note_status,
            fleeting_path=rel_fleeting_path if not is_graduated else None,
            conflict_snapshot=conflict_snapshot,
        )
        node["obsidian"] = envelope.to_dict()
        return envelope

    @classmethod
    def compile_moc(
        cls,
        store: StateStore,
        topic: Dict[str, Any],
    ) -> Path:
        """
        FR-08: Generates and updates 00 - Maps of Content/<Sanitized Topic> MoC.md
        with Mermaid DAG (`flowchart TD`), mastery badges (✅, 🔄, 🔒), stability S,
        due date, and Obsidian wikilinks. Preserves user prose outside markers.
        """
        slug = topic["slug"]
        topic_title = topic.get("title") or slug
        sanitized_topic = VaultGate.sanitize_title(topic_title)
        rel_moc = f"00 - Maps of Content/{sanitized_topic} MoC.md"
        abs_moc = store.gate.validate_path(
            store.gate.vault_root / rel_moc,
            mode="w",
            require_in_vault=True,
        )

        nodes = [nd for nd in topic.get("nodes", []) if not nd.get("archived")]
        today_str = current_date().isoformat()

        mastered_count = 0
        learning_count = 0
        locked_count = 0

        mermaid_lines: List[str] = ["```mermaid", "flowchart TD"]
        table_lines: List[str] = [
            "| Order | Node | Kind | Status | Stability (S) | Due Date |",
            "| :---: | :--- | :---: | :---: | :---: | :---: |",
        ]

        id_to_mermaid: Dict[str, str] = {}
        for idx, nd in enumerate(nodes, start=1):
            nid = nd["id"]
            m_id = f"N{idx}"
            id_to_mermaid[nid] = m_id
            state = nd.get("state", "new")
            fsrs = FSRSState.from_dict(nd.get("fsrs"))
            is_due = bool(fsrs.due and fsrs.due <= today_str)
            obs_meta = nd.get("obsidian") or {}
            obs_status = obs_meta.get("status")
            obs_path = obs_meta.get("note_path")

            if state == "review" and not is_due and (fsrs.reps > 0):
                badge = "✅"
                status_label = "✅ Review"
                mastered_count += 1
            elif obs_status == "fleeting" or state in ("learning", "relearning", "review") or (fsrs.reps > 0):
                badge = "🔄"
                status_label = "🔄 Fleeting" if obs_status == "fleeting" else ("🔄 Due" if is_due else "🔄 Learning")
                learning_count += 1
            else:
                badge = "🔒"
                status_label = "🔒 New/Locked"
                locked_count += 1

            safe_label = (nd.get("title") or nid).replace('"', "'")
            s_disp = f"{fsrs.s:.1f}d" if fsrs.s is not None else "—"
            due_disp = fsrs.due or "—"
            mermaid_lines.append(f'  {m_id}["{badge} {safe_label} (S={s_disp})"]')

            note_title = VaultGate.sanitize_title(nd.get("title") or nid)
            if obs_status == "fleeting" or (isinstance(obs_path, str) and obs_path.startswith("05 - Fleeting/mnemosyne/")):
                fl_rel = obs_path or f"05 - Fleeting/mnemosyne/{sanitized_topic}/{note_title}.md"
                fl_link = fl_rel[:-3] if fl_rel.endswith(".md") else fl_rel
                wikilink = f"[[{fl_link}|{nd.get('title') or nid}]]"
            elif DAGEngine.is_node_credited(nd) or obs_status == "permanent":
                wikilink = f"[[{note_title}|{nd.get('title') or nid}]]"
            else:
                wikilink = nd.get("title") or nid
            table_lines.append(
                f"| {nd.get('order', idx)} | {wikilink} | `{nd.get('kind', 'concept')}` | {status_label} | {s_disp} | {due_disp} |"
            )

        for nd in nodes:
            nid = nd["id"]
            for req in nd.get("edges", {}).get("requires", []):
                if req in id_to_mermaid and nid in id_to_mermaid:
                    mermaid_lines.append(f"  {id_to_mermaid[req]} --> {id_to_mermaid[nid]}")
        mermaid_lines.append("```")

        total_n = len(nodes)
        inner_moc = "\n\n".join([
            f"**Goal:** {cls.neutralize_markdown_injections(topic.get('goal') or '')}\n"
            f"**Domain:** `{topic.get('domain', 'General')}` | **Progress:** "
            f"✅ `{mastered_count}` Mastered · 🔄 `{learning_count}` Learning/Due · 🔒 `{locked_count}` Locked (`{total_n}` total)",
            "## Epistemic Dependency Graph\n" + "\n".join(mermaid_lines),
            "## Curriculum Nodes\n" + "\n".join(table_lines),
        ])

        moc_hash = cls.compute_body_hash(inner_moc)
        managed_updates = {
            "title": f"{topic_title} MoC",
            "mnemosyne_schema": SCHEMA_VERSION,
            "mnemosyne_topic": slug,
            "mnemosyne_body_hash": moc_hash,
        }
        req_tags = ["moc", f"mnemosyne/{slug}"]
        req_aliases = [f"{topic_title} MoC", f"{slug}-moc"]

        existing_spans = None
        existing_parsed = None
        if abs_moc.exists():
            raw_moc = abs_moc.read_text(encoding="utf-8")
            existing_spans, existing_parsed, rest_moc = cls.parse_frontmatter_spans(raw_moc)
            prefix, _, suffix = cls.split_managed_body(rest_moc)
        else:
            prefix = f"\n# {topic_title} — Map of Content\n\n"
            suffix = "\n\n## Synthesis & Cross-Topic Links\n"

        fm_str = cls.patch_frontmatter(
            existing_spans, existing_parsed, managed_updates, req_tags, req_aliases
        )
        full_moc = f"{fm_str}{prefix}{_MANAGED_START}\n{inner_moc}\n{_MANAGED_END}{suffix}"
        return store.atomic_write_text(abs_moc, full_moc, require_in_vault=True)


# ==============================================================================
# SECTION 8 — CLIGATE & SELF-TEST HARNESS
# ==============================================================================

GOLD_SCORE_MAP: Dict[str, int] = {"lapsed": 0, "partial": 1, "recalled": 2}


def _read_payload_input(
    store: StateStore,
    file_arg: Optional[str] = None,
    json_arg: Optional[str] = None,
) -> Any:
    if file_arg:
        if file_arg == "-":
            raw = sys.stdin.read()
        else:
            p = store.gate.validate_path(file_arg, mode="r", allow_external_io=True)
            if not p.exists():
                raise ValidationError(f"Input file not found: {file_arg!r}")
            raw = p.read_text(encoding="utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Malformed JSON in {file_arg!r}: {exc}") from exc
    if json_arg is not None:
        raw = sys.stdin.read() if json_arg == "-" else json_arg
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Malformed --json argument: {exc}") from exc
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Malformed JSON on stdin: {exc}") from exc
    raise ValidationError("Expected JSON input via --file, --json, or stdin.")


def _collect_all_receipts(store: StateStore, topic_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    slugs = [topic_filter] if topic_filter else store.list_topic_slugs()
    # Also scan receipts dir directly
    r_dir = store.state_path("receipts")
    if not topic_filter and r_dir.is_dir():
        for f in sorted(r_dir.iterdir()):
            if f.is_file() and f.name.endswith(".jsonl"):
                s = f.name[:-6]
                if _SLUG_RE.match(s) and s not in slugs:
                    slugs.append(s)
    out: List[Dict[str, Any]] = []
    for s in slugs:
        out.extend(store.read_jsonl("receipts", f"{s}.jsonl"))
    return out


# ------------------------------------------------------------------------------
# Subcommand Handlers
# ------------------------------------------------------------------------------

def cmd_init(store: StateStore, _args: argparse.Namespace) -> Dict[str, Any]:
    model = store.ensure_initialized()
    return {
        "ok": True,
        "vault_root": str(store.gate.vault_root),
        "state_dir": str(store.state_dir),
        "mirror_state_dir": str(store.mirror_dir) if store.mirror_dir else None,
        "engine_version": ENGINE_VERSION,
        "schema": model.get("schema", SCHEMA_VERSION),
    }


def cmd_validate_dag(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    file_arg = getattr(args, "file", None) or getattr(args, "positional_file", None)
    json_arg = getattr(args, "json", None)
    topic_arg = getattr(args, "topic", None)

    if not file_arg and json_arg is None and topic_arg:
        raw_topic = store.load_topic(topic_arg)
    else:
        raw_topic = _read_payload_input(store, file_arg=file_arg, json_arg=json_arg)

    strict_mirror = not bool(getattr(args, "allow_stem_overlap", False))
    validated = DAGEngine.validate_and_sort_dag(raw_topic, strict_stem_mirror=strict_mirror)
    slug = validated["slug"]

    # If --replace or --extend or default save (unless --dry-run), persist into topics/<slug>.json
    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run:
        with store.lock():
            store.ensure_initialized()
            existing_path = store.state_path("topics", f"{slug}.json")
            if existing_path.exists():
                existing = store.load_topic(slug)
                old_by_id = {nd["id"]: nd for nd in existing.get("nodes", [])}
                new_ids = {nd["id"] for nd in validated["nodes"]}
                # Preserve existing FSRS state, last_sid, and obsidian metadata for matching node IDs
                for nd in validated["nodes"]:
                    old_nd = old_by_id.get(nd["id"])
                    if old_nd:
                        if DAGEngine.is_node_credited(old_nd):
                            nd["state"] = old_nd.get("state", nd["state"])
                            nd["fsrs"] = old_nd.get("fsrs", nd["fsrs"])
                            nd["last_sid"] = old_nd.get("last_sid")
                            nd["obsidian"] = old_nd.get("obsidian", nd["obsidian"])
                            if "implicit_credit" in old_nd:
                                nd["implicit_credit"] = old_nd["implicit_credit"]
                # Soft-archive removed nodes on --replace or --extend
                if getattr(args, "replace", False) or getattr(args, "extend", False):
                    for old_id, old_nd in old_by_id.items():
                        if old_id not in new_ids:
                            archived_copy = dict(old_nd)
                            archived_copy["archived"] = True
                            archived_copy["order"] = len(validated["nodes"]) + 1
                            validated["nodes"].append(archived_copy)
            store.save_topic(validated)

    return {
        "ok": True,
        "slug": slug,
        "title": validated.get("title"),
        "node_count": len([n for n in validated["nodes"] if not n.get("archived")]),
        "archived_count": len([n for n in validated["nodes"] if n.get("archived")]),
        "topological_order": [n["id"] for n in validated["nodes"] if not n.get("archived")],
        "saved": not dry_run,
    }


def cmd_status(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    topic_filter = getattr(args, "topic", None)
    slugs = [topic_filter] if topic_filter else store.list_topic_slugs()
    today_str = current_date().isoformat()

    topics_summary: List[Dict[str, Any]] = []
    totals = {
        "topics": 0,
        "nodes": 0,
        "new": 0,
        "learning": 0,
        "review": 0,
        "due": 0,
        "unlocked": 0,
        "locked": 0,
    }

    for slug in slugs:
        t = store.load_topic(slug)
        nodes = [nd for nd in t.get("nodes", []) if not nd.get("archived")]
        by_id = {nd["id"]: nd for nd in nodes}
        t_counts = {"new": 0, "learning": 0, "review": 0, "due": 0, "unlocked": 0, "locked": 0}
        for nd in nodes:
            st = nd.get("state", "new")
            t_counts[st] = t_counts.get(st, 0) + 1
            totals[st] = totals.get(st, 0) + 1
            totals["nodes"] += 1
            fsrs = FSRSState.from_dict(nd.get("fsrs"))
            if fsrs.due and fsrs.due <= today_str:
                t_counts["due"] += 1
                totals["due"] += 1
            if not DAGEngine.is_node_credited(nd):
                if DAGEngine.are_prerequisites_met(nd, by_id):
                    t_counts["unlocked"] += 1
                    totals["unlocked"] += 1
                else:
                    t_counts["locked"] += 1
                    totals["locked"] += 1
        totals["topics"] += 1
        topics_summary.append({
            "slug": slug,
            "title": t.get("title"),
            "domain": t.get("domain"),
            "node_count": len(nodes),
            "counts": t_counts,
        })

    stash_items = store.read_jsonl("stash.jsonl")
    inbox_dir = store.gate.vault_root / "05 - Fleeting" / "mnemosyne" / "inbox"
    inbox_count = 0
    if inbox_dir.is_dir():
        inbox_count = sum(1 for f in inbox_dir.iterdir() if f.is_file() and f.suffix.lower() == ".md" and not f.name.startswith("."))
    model = store.load_learner_model(persist=False)
    return {
        "ok": True,
        "today": today_str,
        "vault_root": str(store.gate.vault_root),
        "state_dir": str(store.state_dir),
        "totals": totals,
        "stash_pending": len(stash_items),
        "inbox_count": inbox_count,
        "memory": model.get("memory"),
        "topics": topics_summary,
    }


def cmd_next(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    topic_slug = getattr(args, "topic", None)
    frontier_of = getattr(args, "frontier_of", None)
    due_only = bool(getattr(args, "due", False))

    if frontier_of:
        if not topic_slug:
            slugs = store.list_topic_slugs()
            if len(slugs) == 1:
                topic_slug = slugs[0]
            else:
                raise ValidationError("--frontier-of requires --topic <slug> when multiple topics exist.")
        with store.lock():
            topic = store.load_topic(topic_slug)
            res = DAGEngine.frontier_probe_state(topic, frontier_of)
            store.save_topic(topic)
            return res

    today_str = current_date().isoformat()
    slugs = [topic_slug] if topic_slug else store.list_topic_slugs()
    due_queue: List[Dict[str, Any]] = []
    encode_queue: List[Dict[str, Any]] = []

    for slug in slugs:
        t = store.load_topic(slug)
        nodes = [nd for nd in t.get("nodes", []) if not nd.get("archived")]
        by_id = {nd["id"]: nd for nd in nodes}
        for nd in nodes:
            fsrs = FSRSState.from_dict(nd.get("fsrs"))
            if DAGEngine.is_node_credited(nd) and fsrs.due and fsrs.due <= today_str:
                use_transfer = bool(
                    ((fsrs.s is not None and fsrs.s >= 21.0) or (fsrs.reps >= 3 and fsrs.lapses == 0))
                    and nd.get("transfer_probe")
                )
                due_queue.append({
                    "topic": slug,
                    "node": nd["id"],
                    "title": nd.get("title"),
                    "kind": nd.get("kind", "concept"),
                    "action": "transfer" if use_transfer else "review",
                    "probe": nd.get("transfer_probe") if use_transfer else nd.get("probe"),
                    "due": fsrs.due,
                    "stability": fsrs.s,
                    "reps": fsrs.reps,
                })
            elif not DAGEngine.is_node_credited(nd) and DAGEngine.are_prerequisites_met(nd, by_id):
                encode_queue.append({
                    "topic": slug,
                    "node": nd["id"],
                    "title": nd.get("title"),
                    "kind": nd.get("kind", "concept"),
                    "action": "encode",
                    "order": nd.get("order", 1),
                    "unconditional_truth": nd.get("unconditional_truth"),
                    "motivated_discovery": nd.get("motivated_discovery"),
                    "probe": nd.get("probe"),
                })

    # Sort due_queue interleaved across topics by due date then stability ascending
    due_queue.sort(key=lambda x: (x["due"], x["stability"] or 0.0, x["topic"], x["node"]))
    if getattr(args, "interleave", False) and len(slugs) > 1:
        by_t: Dict[str, List[Dict[str, Any]]] = {}
        for item in due_queue:
            by_t.setdefault(item["topic"], []).append(item)
        interleaved: List[Dict[str, Any]] = []
        while any(by_t.values()):
            for s in sorted(by_t):
                if by_t[s]:
                    interleaved.append(by_t[s].pop(0))
        due_queue = interleaved

    if due_only:
        return {
            "ok": True,
            "today": today_str,
            "due_count": len(due_queue),
            "due": due_queue,
            "next": due_queue[0] if due_queue else None,
        }

    next_item = due_queue[0] if due_queue else (encode_queue[0] if encode_queue else None)
    return {
        "ok": True,
        "today": today_str,
        "next": next_item,
        "due_count": len(due_queue),
        "due": due_queue,
        "unlocked_new_count": len(encode_queue),
        "unlocked_new": encode_queue,
    }


def cmd_probe(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    topic_slug = getattr(args, "topic", None) or getattr(args, "pos_topic", None)
    node_id = getattr(args, "node", None) or getattr(args, "pos_node", None)
    result_str = getattr(args, "result", None) or getattr(args, "pos_result", None)
    target_id = getattr(args, "target", None)

    if not topic_slug or not node_id or not result_str:
        raise ValidationError("probe requires <topic> <node> <pass|fail>.")
    res_norm = str(result_str).strip().lower()
    if res_norm not in ("pass", "fail", "passed", "failed", "true", "false"):
        raise ValidationError(f"Invalid probe result {result_str!r}; must be 'pass' or 'fail'.")
    passed = res_norm in ("pass", "passed", "true")

    with store.lock():
        store.ensure_initialized()
        model = store.load_learner_model(persist=False)
        weights = FSRSEngine.normalize_weights((model.get("memory") or {}).get("fsrs_params"))
        ret_req = as_finite_float((model.get("memory") or {}).get("desired_retention"), RETENTION_DEFAULT) or RETENTION_DEFAULT
        im = as_finite_float((model.get("memory") or {}).get("interval_multiplier"), 1.0) or 1.0

        topic = store.load_topic(topic_slug)
        by_id = {nd["id"]: nd for nd in topic.get("nodes", [])}
        status, credited_ids = DAGEngine.record_probe_result(
            topic, node_id, passed=passed, target_id=target_id
        )

        # Mint pretest receipts and initial FSRS schedules for newly credited strand nodes
        today_dt = current_date()
        ts_iso = current_iso_timestamp()
        for idx, c_nid in enumerate(credited_ids):
            nd = by_id[c_nid]
            new_fsrs, trans, _ = FSRSEngine.apply_rating(
                nd.get("fsrs"),
                3,  # good / pretest pass
                today_dt,
                w=weights,
                desired_retention=ret_req,
                interval_multiplier=im,
                node_kind=nd.get("kind", "concept"),
            )
            prod_text = f"Credited via binary-search frontier probe pass on {node_id}."
            sha = StashEngine.compute_stash_sha256(
                nd.get("claim", ""),
                nd.get("probe", ""),
                prod_text,
                nd.get("rubric") or [],
            )
            sid = f"pr-{today_dt.isoformat().replace('-', '')}-{sha[:6]}-{idx}"
            rec = ReceiptRecord(
                id=f"rc-{today_dt.isoformat().replace('-', '')}-{sha[:8]}",
                sid=sid,
                stash_sha256=sha,
                ts=today_dt.isoformat(),
                captured_at=ts_iso,
                settled_at=ts_iso,
                source="frontier-probe",
                topic=topic_slug,
                node=c_nid,
                kind="pretest",
                node_kind=nd.get("kind", "concept"),
                grade="recalled",
                rating="good",
                score=3,
                produced=True,
                confidence=3,
                error_class=None,
                criteria_met=tuple(True for _ in (nd.get("rubric") or [True])),
                probe_gap=(),
                misconceptions=(),
                production=prod_text,
                rationale=f"Prerequisite frontier probe passed at {node_id}.",
                fsrs_transition=trans,
                artifact_present=bool(nd.get("artifact") or nd.get("mermaid_block")),
            )
            nd["state"] = "review"
            nd["last_sid"] = sid
            nd["last_production"] = prod_text
            nd["fsrs"] = new_fsrs.to_dict()
            DAGEngine.propagate_prerequisite_credit(topic, c_nid, weight=PREREQ_PROPAGATION_WEIGHT)
            store.append_jsonl(rec.to_dict(), "receipts", f"{topic_slug}.jsonl")

        store.save_topic(topic)
        return status


def cmd_unlock(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    topic_slug = getattr(args, "topic", None) or getattr(args, "pos_topic", None)
    node_id = getattr(args, "node", None) or getattr(args, "pos_node", None)
    force = bool(getattr(args, "force", False))

    if not topic_slug:
        slugs = store.list_topic_slugs()
        if len(slugs) == 1:
            topic_slug = slugs[0]
        else:
            raise ValidationError("unlock requires --topic <slug> (or positional <topic>).")

    with store.lock():
        topic = store.load_topic(topic_slug)
        nodes = [nd for nd in topic.get("nodes", []) if not nd.get("archived")]
        by_id = {nd["id"]: nd for nd in nodes}

        unlocked_list: List[str] = []
        if node_id:
            if node_id not in by_id:
                raise ValidationError(f"Unknown node {node_id!r} in topic {topic_slug!r}.")
            target = by_id[node_id]
            if not DAGEngine.are_prerequisites_met(target, by_id) and not force:
                missing = [
                    r for r in target.get("edges", {}).get("requires", [])
                    if r in by_id and not DAGEngine.is_node_credited(by_id[r])
                ]
                raise ValidationError(
                    f"Cannot unlock {node_id!r}: uncredited prerequisites {missing}. Pass --force or probe first.",
                    details={"missing_prerequisites": missing},
                )
            target["unlocked"] = True
            if target.get("state") == "new":
                target["state"] = "learning"
            unlocked_list.append(node_id)
        else:
            for nd in nodes:
                if not DAGEngine.is_node_credited(nd) and DAGEngine.are_prerequisites_met(nd, by_id):
                    nd["unlocked"] = True
                    unlocked_list.append(nd["id"])

        store.save_topic(topic)
        return {
            "ok": True,
            "topic": topic_slug,
            "unlocked": unlocked_list,
            "unlocked_count": len(unlocked_list),
        }


def cmd_stash(store: StateStore, args: argparse.Namespace) -> Any:
    action = getattr(args, "action", "list")
    with store.lock():
        store.ensure_initialized()
        stash_rows = store.read_jsonl("stash.jsonl")

        if action == "add":
            file_arg = getattr(args, "file", None)
            json_arg = getattr(args, "json", None)
            if file_arg or json_arg is not None:
                payload = _read_payload_input(store, file_arg=file_arg, json_arg=json_arg)
            elif getattr(args, "topic", None) and getattr(args, "node", None):
                payload = {
                    "topic": args.topic,
                    "node": args.node,
                    "production": getattr(args, "production", "") or "",
                    "probe": getattr(args, "probe", None),
                    "claim": getattr(args, "claim", None),
                    "rubric": getattr(args, "rubric", None),
                    "confidence": getattr(args, "confidence", None),
                    "kind": getattr(args, "kind", "encode"),
                    "produced": getattr(args, "produced", None),
                }
            else:
                payload = _read_payload_input(store)

            items = payload if isinstance(payload, list) else [payload]
            added_records: List[Dict[str, Any]] = []
            for raw_item in items:
                if not isinstance(raw_item, dict):
                    raise ValidationError("Each stash item must be a JSON object.")
                t_slug = VaultGate.validate_slug(raw_item.get("topic"), "topic")
                n_id = VaultGate.validate_slug(raw_item.get("node"), "node")
                node_obj: Optional[Dict[str, Any]] = None
                if store.state_path("topics", f"{t_slug}.json").exists():
                    t_data = store.load_topic(t_slug)
                    node_obj = next((n for n in t_data.get("nodes", []) if n.get("id") == n_id), None)
                rec = StashEngine.create_record(raw_item, node_lookup=node_obj)
                rec_dict = rec.to_dict()
                stash_rows.append(rec_dict)
                added_records.append(rec_dict)

            store.write_jsonl(stash_rows, "stash.jsonl")
            if len(added_records) == 1:
                return {
                    "ok": True,
                    "sid": added_records[0]["sid"],
                    "captured_at": added_records[0]["captured_at"],
                    "stash_sha256": added_records[0]["stash_sha256"],
                    "pending": len(stash_rows),
                    "record": added_records[0],
                }
            return {
                "ok": True,
                "added": len(added_records),
                "pending": len(stash_rows),
                "records": added_records,
            }

        if action == "pop":
            if not stash_rows:
                raise ValidationError("Cannot pop from empty stash.")
            target_sid = getattr(args, "sid", None)
            if target_sid:
                idx = next((i for i, r in enumerate(stash_rows) if r.get("sid") == target_sid), -1)
                if idx < 0:
                    raise ValidationError(f"Stash sid {target_sid!r} not found.")
                popped = stash_rows.pop(idx)
            else:
                popped = stash_rows.pop(-1)
            store.write_jsonl(stash_rows, "stash.jsonl")
            return {"ok": True, "popped": popped, "pending": len(stash_rows)}

        if action == "list":
            return stash_rows

        if action == "count":
            return {"ok": True, "pending": len(stash_rows)}

        if action == "clear":
            store.write_jsonl([], "stash.jsonl")
            return {"ok": True, "pending": 0}

        if action == "export-assessor":
            target_sid = getattr(args, "sid", None)
            out_path = getattr(args, "out", None)
            if target_sid:
                match = next((r for r in stash_rows if r.get("sid") == target_sid), None)
                if match is None:
                    raise ValidationError(f"Stash sid {target_sid!r} not found in stash.jsonl.")
                env_payload: Any = StashEngine.to_assessor_envelope(match).to_dict()
            else:
                env_payload = [StashEngine.to_assessor_envelope(r).to_dict() for r in stash_rows]

            if out_path:
                out_text = json.dumps(env_payload, indent=2, ensure_ascii=False) + "\n"
                store.atomic_write_text(out_path, out_text, allow_external_io=True)
            return env_payload

        raise ValidationError(f"Unknown stash action {action!r}.")


def _resolve_score_rating_grade(raw: Dict[str, Any]) -> Tuple[int, str, str]:
    """
    Normalizes score (1..4), rating (again|hard|good|easy), and grade (lapsed|partial|recalled)
    and enforces consistency and RN-01 'produced: false' guard.
    """
    score_raw = raw.get("score")
    rating_raw = raw.get("rating")
    grade_raw = raw.get("grade")

    g: Optional[int] = None
    if score_raw is not None:
        s_val = as_finite_float(score_raw)
        if s_val is None or int(round(s_val)) not in (1, 2, 3, 4):
            raise ValidationError(f"Invalid receipt score {score_raw!r}; must be 1, 2, 3, or 4.")
        g = int(round(s_val))

    if rating_raw is not None:
        r_str = str(rating_raw).strip().lower()
        if r_str not in RATING_TO_G:
            raise ValidationError(f"Invalid rating {rating_raw!r}; allowed: {list(RATING_TO_G)}.")
        r_g = RATING_TO_G[r_str]
        if g is not None and g != r_g:
            raise ValidationError(f"Conflicting score={g} and rating={r_str!r} in receipt.")
        g = r_g

    if grade_raw is not None:
        gr_str = str(grade_raw).strip().lower()
        if gr_str not in GRADE_TO_DEFAULT_G:
            raise ValidationError(f"Invalid grade {grade_raw!r}; allowed: ('lapsed', 'partial', 'recalled').")
        if g is None:
            g = GRADE_TO_DEFAULT_G[gr_str]
        else:
            expected_gr = G_TO_GRADE[g]
            if gr_str != expected_gr:
                raise ValidationError(f"Conflicting grade={gr_str!r} and rating/score (expected {expected_gr!r}).")

    if g is None:
        raise ValidationError("Receipt item must provide 'rating', 'score', or 'grade'.")

    return g, G_TO_RATING[g], G_TO_GRADE[g]


def cmd_receipt(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    FR-05: Atomic Blind Assessor Receipt Processing & Idempotency (handles both `receipt` and `batch`).
    Validates EVERY item in the batch before mutating any state:
      - Verifies sid & stash_sha256 against stash.jsonl (or skips idempotently if already in receipts)
      - Rejects produced: false with score >= 3 (Exit Code 1)
      - Anchors FSRS-4.5 calculation to captured_at
      - Propagates prerequisite credit (weight=0.5) on recall
      - Appends to receipts/<topic>.jsonl and drains stash.jsonl atomically
    """
    file_arg = getattr(args, "file", None) or getattr(args, "positional_file", None)
    json_arg = getattr(args, "json", None)

    if file_arg or json_arg is not None:
        payload = _read_payload_input(store, file_arg=file_arg, json_arg=json_arg)
    elif getattr(args, "topic", None) or getattr(args, "sid", None):
        payload = {
            "sid": getattr(args, "sid", None),
            "stash_sha256": getattr(args, "stash_sha256", None),
            "topic": getattr(args, "topic", None),
            "node": getattr(args, "node", None),
            "rating": getattr(args, "rating", None),
            "grade": getattr(args, "grade", None),
            "score": getattr(args, "score", None),
            "produced": getattr(args, "produced", None),
            "production": getattr(args, "production", None),
            "error_class": getattr(args, "error_class", None),
            "confidence": getattr(args, "confidence", None),
            "rationale": getattr(args, "rationale", None),
        }
    else:
        payload = _read_payload_input(store)

    if isinstance(payload, dict) and isinstance(payload.get("receipts"), list):
        items = payload["receipts"]
    elif isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = [payload]
    else:
        raise ValidationError("Receipt payload must be a JSON object or array of objects.")

    if not items:
        raise ValidationError("Receipt batch cannot be empty.")

    with store.lock():
        store.ensure_initialized()
        stash_rows = store.read_jsonl("stash.jsonl")
        stash_by_sid = {r["sid"]: r for r in stash_rows if isinstance(r.get("sid"), str)}

        # Pre-load existing settled sids across topics for idempotent replay check
        settled_by_sid: Dict[str, Dict[str, Any]] = {}
        for r in _collect_all_receipts(store):
            if isinstance(r.get("sid"), str):
                settled_by_sid[r["sid"]] = r

        topics_cache: Dict[str, Dict[str, Any]] = {}
        validated_plan: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]], int, str, str, bool]] = []

        # PASS 1: Atomic Pre-Flight Validation (zero state mutation if any item fails)
        for idx, raw_item in enumerate(items):
            if not isinstance(raw_item, dict):
                raise ValidationError(f"Receipt item at index {idx} must be a JSON object.")

            sid = raw_item.get("sid")
            if isinstance(sid, str) and sid in settled_by_sid:
                # Idempotent duplicate sid from a crash retry
                validated_plan.append((raw_item, None, 0, "", "", True))
                continue

            stash_entry = stash_by_sid.get(sid) if isinstance(sid, str) else None
            topic_slug = raw_item.get("topic") or (stash_entry or {}).get("topic")
            node_id = raw_item.get("node") or (stash_entry or {}).get("node")
            if not topic_slug or not node_id:
                raise ValidationError(
                    f"Receipt item #{idx} (sid={sid!r}) missing topic/node and not found in stash.jsonl."
                )
            VaultGate.validate_slug(topic_slug, "topic")
            VaultGate.validate_slug(node_id, "node")

            if topic_slug not in topics_cache:
                topics_cache[topic_slug] = store.load_topic(topic_slug)
            t_data = topics_cache[topic_slug]
            node_obj = next((n for n in t_data.get("nodes", []) if n.get("id") == node_id), None)
            if node_obj is None:
                raise ValidationError(f"Unknown node {node_id!r} in topic {topic_slug!r}.")

            g, rating_str, grade_str = _resolve_score_rating_grade(raw_item)

            # Determine `produced` and `production`
            prod_text = raw_item.get("production")
            if prod_text is None and stash_entry is not None:
                prod_text = stash_entry.get("production")
            if prod_text is None:
                prod_text = ""

            produced_val = raw_item.get("produced")
            if produced_val is None and stash_entry is not None:
                produced_val = stash_entry.get("produced")
            if isinstance(produced_val, bool):
                produced = produced_val
            else:
                produced = bool(str(prod_text).strip())

            # CRITICAL GUARD: produced: false with score >= 3 (good/easy/recalled) -> Exit Code 1
            if not produced and g >= 3:
                raise ValidationError(
                    f"Receipt validation failed for {topic_slug}/{node_id}: cannot assign score={g} ({rating_str}/{grade_str}) when produced is false.",
                    details={"sid": sid, "score": g, "rating": rating_str, "produced": False},
                )

            # Verify cryptographic Claim-Check stash_sha256
            provided_sha = raw_item.get("stash_sha256")
            if stash_entry is not None:
                expected_sha = stash_entry.get("stash_sha256")
                if provided_sha is not None and provided_sha != expected_sha:
                    raise ValidationError(
                        f"Cryptographic Claim-Check mismatch on sid={sid!r}: receipt stash_sha256={provided_sha!r} != stashed {expected_sha!r}.",
                        details={"sid": sid, "expected_sha256": expected_sha, "actual_sha256": provided_sha},
                    )
                # Also verify production wasn't tampered in receipt if both provided
                if raw_item.get("production") is not None and raw_item.get("production") != stash_entry.get("production"):
                    raise ValidationError(
                        f"Tampered production in receipt for sid={sid!r}: does not match stashed production."
                    )
            else:
                # If not in stash, check if forged stash_sha256 was supplied or if direct receipt requires valid hash
                computed_sha = StashEngine.compute_stash_sha256(
                    node_obj.get("claim", ""),
                    node_obj.get("probe", ""),
                    str(prod_text),
                    node_obj.get("rubric") or [],
                )
                if provided_sha is not None and provided_sha != computed_sha:
                    raise ValidationError(
                        f"Forged or mismatched stash_sha256 for {topic_slug}/{node_id}: {provided_sha!r} != {computed_sha!r}.",
                        details={"sid": sid, "expected_sha256": computed_sha, "actual_sha256": provided_sha},
                    )
                if sid is not None and not str(sid).startswith(("sr-", "pr-", "direct-")) and provided_sha is None:
                    raise ValidationError(
                        f"Unknown stash sid {sid!r} not found in stash.jsonl and not previously settled."
                    )

            err_cls = raw_item.get("error_class")
            if err_cls is not None and err_cls not in ("slip", "conceptual"):
                raise ValidationError(
                    f"Invalid error_class {err_cls!r}; must be 'slip', 'conceptual', or null."
                )

            validated_plan.append((raw_item, stash_entry, g, rating_str, grade_str, False))

        # PASS 2: Commit State Transitions Atomically
        model = store.load_learner_model(persist=False)
        weights = FSRSEngine.normalize_weights((model.get("memory") or {}).get("fsrs_params"))
        ret_req = as_finite_float((model.get("memory") or {}).get("desired_retention"), RETENTION_DEFAULT) or RETENTION_DEFAULT
        im = as_finite_float((model.get("memory") or {}).get("interval_multiplier"), 1.0) or 1.0
        relearn_on = (model.get("settings") or {}).get("relearning", "on") != "off"

        applied_results: List[Dict[str, Any]] = []
        drained_sids: Set[str] = set()
        settled_ts = current_iso_timestamp()

        for raw_item, stash_entry, g, rating_str, grade_str, is_noop in validated_plan:
            if is_noop:
                sid_existing = str(raw_item["sid"])
                prev_rec = settled_by_sid[sid_existing]
                applied_results.append({
                    "sid": sid_existing,
                    "topic": prev_rec.get("topic"),
                    "node": prev_rec.get("node"),
                    "idempotent_noop": True,
                    "applied": False,
                    "rating": prev_rec.get("rating"),
                    "grade": prev_rec.get("grade"),
                })
                continue

            topic_slug = str(raw_item.get("topic") or (stash_entry or {}).get("topic"))
            node_id = str(raw_item.get("node") or (stash_entry or {}).get("node"))
            t_data = topics_cache[topic_slug]
            node_obj = next(n for n in t_data["nodes"] if n["id"] == node_id)

            captured_at = str(
                raw_item.get("captured_at")
                or (stash_entry or {}).get("captured_at")
                or settled_ts
            )
            review_date = parse_iso_date(captured_at) or current_date()

            prod_text = str(
                raw_item.get("production")
                if raw_item.get("production") is not None
                else ((stash_entry or {}).get("production") or "")
            )
            produced_val = raw_item.get("produced")
            if produced_val is None and stash_entry is not None:
                produced_val = stash_entry.get("produced")
            produced = bool(produced_val) if isinstance(produced_val, bool) else bool(prod_text.strip())

            sha256_hex = (
                (stash_entry or {}).get("stash_sha256")
                or raw_item.get("stash_sha256")
                or StashEngine.compute_stash_sha256(
                    node_obj.get("claim", ""),
                    node_obj.get("probe", ""),
                    prod_text,
                    node_obj.get("rubric") or [],
                )
            )
            sid = str(
                raw_item.get("sid")
                or (stash_entry or {}).get("sid")
                or f"st-{captured_at.replace('-', '').replace(':', '')}-{sha256_hex[:6]}"
            )
            ev_kind = str(
                raw_item.get("kind")
                or raw_item.get("event_kind")
                or (stash_entry or {}).get("event_kind")
                or ("review" if DAGEngine.is_node_credited(node_obj) else "encode")
            )
            n_kind = str(node_obj.get("kind") or "concept")
            err_cls = raw_item.get("error_class")

            new_fsrs, trans, eff_g = FSRSEngine.apply_rating(
                node_obj.get("fsrs"),
                g,
                review_date,
                w=weights,
                desired_retention=ret_req,
                interval_multiplier=im,
                relearning_enabled=relearn_on,
                is_threshold=bool(node_obj.get("threshold")),
                node_kind=n_kind,
                error_class=err_cls,
            )
            eff_rating = G_TO_RATING[eff_g]
            eff_grade = G_TO_GRADE[eff_g]

            was_new = not DAGEngine.is_node_credited(node_obj)
            if eff_g == 1 or (was_new and eff_g == 2):
                node_obj["state"] = "learning"
            else:
                node_obj["state"] = "review"

            node_obj["fsrs"] = new_fsrs.to_dict()
            node_obj["last_sid"] = sid
            node_obj["last_production"] = prod_text

            propagated = []
            if eff_g >= 3:
                propagated = DAGEngine.propagate_prerequisite_credit(
                    t_data, node_id, weight=PREREQ_PROPAGATION_WEIGHT
                )

            rubric_len = len(node_obj.get("rubric") or [])
            raw_crit = raw_item.get("criteria_met")
            if isinstance(raw_crit, list):
                crit_tuple = tuple(bool(x) for x in raw_crit)
            else:
                crit_tuple = tuple((eff_g >= 3) for _ in range(max(1, rubric_len)))

            raw_gaps = raw_item.get("probe_gap")
            gap_tuple = tuple(int(x) for x in raw_gaps if isinstance(x, (int, float))) if isinstance(raw_gaps, list) else ()

            raw_misc = raw_item.get("misconceptions")
            misc_tuple = tuple(str(x) for x in raw_misc if x) if isinstance(raw_misc, list) else ()
            if misc_tuple:
                all_misc = store.read_json("misconceptions.json") or []
                for m_text in misc_tuple:
                    all_misc.append({
                        "ts": review_date.isoformat(),
                        "topic": topic_slug,
                        "node": node_id,
                        "description": m_text,
                        "sid": sid,
                    })
                store.write_json(all_misc, "misconceptions.json")

            conf_val = raw_item.get("confidence")
            if conf_val is None and stash_entry is not None:
                conf_val = stash_entry.get("confidence")

            rec_id = f"rc-{settled_ts.replace('-', '').replace(':', '')}-{len(settled_by_sid) + 1:04d}"
            rec_record = ReceiptRecord(
                id=rec_id,
                sid=sid,
                stash_sha256=sha256_hex,
                ts=review_date.isoformat(),
                captured_at=captured_at,
                settled_at=settled_ts,
                source=str(raw_item.get("source") or "blind-assessor"),
                topic=topic_slug,
                node=node_id,
                kind=ev_kind,
                node_kind=n_kind,
                grade=eff_grade,
                rating=eff_rating,
                score=eff_g,
                produced=produced,
                confidence=int(conf_val) if isinstance(conf_val, (int, float)) else None,
                error_class=err_cls,
                criteria_met=crit_tuple,
                probe_gap=gap_tuple,
                misconceptions=misc_tuple,
                production=prod_text,
                rationale=str(raw_item.get("rationale") or "Verified against node rubric."),
                fsrs_transition=trans,
                artifact_present=bool(node_obj.get("artifact") or node_obj.get("mermaid_block")),
            )
            rec_dict = rec_record.to_dict()
            store.append_jsonl(rec_dict, "receipts", f"{topic_slug}.jsonl")
            settled_by_sid[sid] = rec_dict
            drained_sids.add(sid)

            applied_results.append({
                "id": rec_id,
                "sid": sid,
                "topic": topic_slug,
                "node": node_id,
                "applied": True,
                "idempotent_noop": False,
                "grade": eff_grade,
                "rating": eff_rating,
                "score": eff_g,
                "state": node_obj["state"],
                "fsrs": node_obj["fsrs"],
                "propagated_prerequisites": propagated,
            })

        # Save all touched topics and drain settled sids from stash.jsonl
        for t_slug, t_data in topics_cache.items():
            store.save_topic(t_data)

        if drained_sids:
            remaining_stash = [r for r in stash_rows if r.get("sid") not in drained_sids]
            store.write_jsonl(remaining_stash, "stash.jsonl")

        return {
            "ok": True,
            "processed": len(applied_results),
            "results": applied_results,
        }


def cmd_sync_sr(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    OPT-01 & RFC §3.3.2: Indexed O(N_managed) bi-directional reconciliation with
    obsidian-spaced-repetition.
    - Iterates strictly over managed nodes in topics/*.json (never calls rglob).
    - Uses os.stat() fast-path (st_mtime_ns, st_size) to short-circuit unchanged files in O(1).
    - Reads first 4096 bytes for frontmatter inspection when changed.
    - Infers rating G in {1..4} from delta sr-ease and sr-interval, appends 'obsidian-sr'
      receipt, and dual-writes updated frontmatter.
    """
    topic_filter = getattr(args, "topic", None)
    slugs = [topic_filter] if topic_filter else store.list_topic_slugs()

    with store.lock():
        store.ensure_initialized()
        model = store.load_learner_model(persist=False)
        weights = FSRSEngine.normalize_weights((model.get("memory") or {}).get("fsrs_params"))
        ret_req = as_finite_float((model.get("memory") or {}).get("desired_retention"), RETENTION_DEFAULT) or RETENTION_DEFAULT
        im = as_finite_float((model.get("memory") or {}).get("interval_multiplier"), 1.0) or 1.0
        relearn_on = (model.get("settings") or {}).get("relearning", "on") != "off"

        fast_skipped = 0
        inspected = 0
        reconciled: List[Dict[str, Any]] = []

        for slug in slugs:
            topic = store.load_topic(slug)
            topic_dirty = False
            by_id = {nd["id"]: nd for nd in topic.get("nodes", [])}
            receipts = store.read_jsonl("receipts", f"{slug}.jsonl")
            all_misc = store.read_json("misconceptions.json") or []

            for nd in topic.get("nodes", []):
                if nd.get("archived"):
                    continue
                obs = nd.get("obsidian") or {}
                rel_path = obs.get("note_path")
                if not isinstance(rel_path, str) or not rel_path.strip():
                    continue
                if ".sync-conflict" in rel_path:
                    continue

                abs_path = store.gate.validate_path(
                    store.gate.vault_root / rel_path,
                    mode="r",
                    require_in_vault=True,
                )
                try:
                    st = abs_path.stat()
                except FileNotFoundError:
                    continue

                # OPT-01 Fast-Path: O(1) stat comparison
                if (
                    obs.get("st_mtime_ns") is not None
                    and obs.get("st_size") is not None
                    and st.st_mtime_ns == obs.get("st_mtime_ns")
                    and st.st_size == obs.get("st_size")
                ):
                    fast_skipped += 1
                    continue

                inspected += 1
                # Read first 4096 bytes for fast frontmatter extraction; fallback to full read if frontmatter > 4096B
                with open(abs_path, "rb") as bf:
                    head_bytes = bf.read(4096)
                head_text = head_bytes.decode("utf-8", errors="replace")
                if not _FRONTMATTER_RE.match(head_text.replace("\x00", "").replace("\r\n", "\n")):
                    full_text = abs_path.read_text(encoding="utf-8")
                else:
                    full_text = abs_path.read_text(encoding="utf-8")

                # Validate frontmatter and managed markers (raises Exit Code 3 if corrupted)
                _, parsed_fm, rest_body = MDCompiler.parse_frontmatter_spans(full_text)
                MDCompiler.split_managed_body(rest_body)

                fm_sid = parsed_fm.get("mnemosyne_sid")
                fm_sr_due = str(parsed_fm.get("sr-due") or "").strip()
                fm_sr_ivl = int(as_finite_float(parsed_fm.get("sr-interval"), 1.0) or 1)
                fm_sr_ease = int(as_finite_float(parsed_fm.get("sr-ease"), 250.0) or 250)

                fsrs_cur = FSRSState.from_dict(nd.get("fsrs"))
                last_sid = nd.get("last_sid")

                if fm_sid == last_sid and fm_sr_due and fm_sr_due != (fsrs_cur.due or ""):
                    g, d_rev, delta_ease = FSRSEngine.infer_sr_reverse_rating(
                        fsrs_cur, fm_sr_due, fm_sr_ivl, fm_sr_ease
                    )
                    new_fsrs, trans, eff_g = FSRSEngine.apply_rating(
                        fsrs_cur,
                        g,
                        d_rev,
                        w=weights,
                        desired_retention=ret_req,
                        interval_multiplier=im,
                        relearning_enabled=relearn_on,
                        is_threshold=bool(nd.get("threshold")),
                        node_kind=nd.get("kind", "concept"),
                    )
                    sha_input = f"{slug}:{nd['id']}:{d_rev.isoformat()}:{fm_sr_due}:{fm_sr_ivl}:{fm_sr_ease}"
                    sha_hex = hashlib.sha256(sha_input.encode("utf-8")).hexdigest()
                    new_sid = f"sr-{d_rev.isoformat()}-{sha_hex[:8]}"

                    nd["fsrs"] = new_fsrs.to_dict()
                    nd["last_sid"] = new_sid
                    nd["state"] = "learning" if eff_g == 1 else "review"

                    rec = ReceiptRecord(
                        id=f"rc-sr-{d_rev.isoformat().replace('-', '')}-{sha_hex[:6]}",
                        sid=new_sid,
                        stash_sha256=sha_hex,
                        ts=d_rev.isoformat(),
                        captured_at=f"{d_rev.isoformat()}T12:00:00Z",
                        settled_at=current_iso_timestamp(),
                        source="obsidian-sr",
                        topic=slug,
                        node=nd["id"],
                        kind="review",
                        node_kind=nd.get("kind", "concept"),
                        grade=G_TO_GRADE[eff_g],
                        rating=G_TO_RATING[eff_g],
                        score=eff_g,
                        produced=True,
                        confidence=None,
                        error_class=None,
                        criteria_met=(),
                        probe_gap=(),
                        misconceptions=(),
                        production=nd.get("last_production") or "Reviewed in Obsidian Spaced Repetition plugin.",
                        rationale=f"Reconciled from obsidian-spaced-repetition (delta_ease={delta_ease}, sr_interval={fm_sr_ivl}).",
                        fsrs_transition=trans,
                        artifact_present=bool(nd.get("artifact") or nd.get("mermaid_block")),
                    )
                    rec_dict = rec.to_dict()
                    store.append_jsonl(rec_dict, "receipts", f"{slug}.jsonl")
                    receipts.append(rec_dict)

                    node_misc = [m for m in all_misc if m.get("topic") == slug and m.get("node") == nd["id"]]
                    MDCompiler.compile_note(store, topic, nd, rec_dict, node_misc, by_id)
                    topic_dirty = True
                    reconciled.append({
                        "topic": slug,
                        "node": nd["id"],
                        "inferred_rating": G_TO_RATING[eff_g],
                        "inferred_score": eff_g,
                        "delta_ease": delta_ease,
                        "review_date": d_rev.isoformat(),
                        "new_due": new_fsrs.due,
                        "sid": new_sid,
                    })
                else:
                    # Update cached stat metadata if only outer prose changed cleanly
                    obs["st_mtime_ns"] = st.st_mtime_ns
                    obs["st_size"] = st.st_size
                    topic_dirty = True

            if topic_dirty:
                store.save_topic(topic)

        return {
            "ok": True,
            "fast_skipped": fast_skipped,
            "inspected": inspected,
            "reconciled_count": len(reconciled),
            "reconciled": reconciled,
        }


def cmd_synthesize(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    FR-08 & FR-09 & HLD-04: Automatically runs sync-sr pre-pass (under re-entrant LockMgr),
    compiles all receipted/credited nodes into 02 - Areas/ or 04 - Permanent/, and compiles
    <Topic> MoC.md in 00 - Maps of Content/.
    """
    topic_filter = getattr(args, "topic", None)
    include_all_nodes = bool(getattr(args, "all_nodes", False))

    with store.lock():
        store.ensure_initialized()
        # HLD-04: Pre-synthesis sync-sr pass
        sr_report = cmd_sync_sr(store, args)

        slugs = [topic_filter] if topic_filter else store.list_topic_slugs()
        if not slugs:
            raise ValidationError("No topics found to synthesize.")

        all_misc = store.read_json("misconceptions.json") or []
        stash_rows = store.read_jsonl("stash.jsonl")
        compiled_notes: List[Dict[str, Any]] = []
        compiled_mocs: List[str] = []
        conflicts: List[str] = []

        for slug in slugs:
            topic = store.load_topic(slug)
            nodes = [nd for nd in topic.get("nodes", []) if not nd.get("archived")]
            by_id = {nd["id"]: nd for nd in nodes}
            receipts = store.read_jsonl("receipts", f"{slug}.jsonl")
            latest_rec_by_node: Dict[str, Dict[str, Any]] = {}
            for r in receipts:
                nid = r.get("node")
                if isinstance(nid, str):
                    latest_rec_by_node[nid] = r

            stash_by_node: Dict[str, Dict[str, Any]] = {}
            for st_item in stash_rows:
                if st_item.get("topic") == slug and isinstance(st_item.get("node"), str):
                    stash_by_node[st_item["node"]] = st_item

            for nd in nodes:
                nid = nd["id"]
                if (
                    not include_all_nodes
                    and not DAGEngine.is_node_credited(nd)
                    and nid not in latest_rec_by_node
                    and nid not in stash_by_node
                ):
                    continue
                node_misc = [
                    m for m in all_misc
                    if isinstance(m, dict) and m.get("topic") == slug and m.get("node") == nid
                ]
                eff_receipt = latest_rec_by_node.get(nid)
                if eff_receipt is None and nid in stash_by_node:
                    st_ref = stash_by_node[nid]
                    eff_receipt = {
                        "sid": st_ref.get("sid"),
                        "ts": str(st_ref.get("captured_at") or current_date().isoformat())[:10],
                        "production": st_ref.get("production") or "",
                        "score": 0,
                    }
                env = MDCompiler.compile_note(
                    store,
                    topic,
                    nd,
                    eff_receipt,
                    node_misc,
                    by_id,
                )
                compiled_notes.append({
                    "topic": slug,
                    "node": nid,
                    "note_path": env.note_path,
                    "status": env.status,
                    "fleeting_path": env.fleeting_path,
                    "body_hash": env.body_hash,
                    "conflict_snapshot": env.conflict_snapshot,
                })
                if env.conflict_snapshot:
                    conflicts.append(env.conflict_snapshot)

            moc_path = MDCompiler.compile_moc(store, topic)
            compiled_mocs.append(str(moc_path.relative_to(store.gate.vault_root)))
            store.save_topic(topic)

        return {
            "ok": True,
            "sync_sr": sr_report,
            "compiled_notes_count": len(compiled_notes),
            "compiled_notes": compiled_notes,
            "compiled_mocs": compiled_mocs,
            "conflicts": conflicts,
        }


def cmd_inbox(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Manages fleeting study inbox notes in <vault>/05 - Fleeting/mnemosyne/inbox/ (`list` | `add`).
    """
    action = getattr(args, "action", "list") or "list"
    with store.lock():
        store.ensure_initialized()
        rel_inbox_dir = "05 - Fleeting/mnemosyne/inbox"
        abs_inbox_dir = store.gate.validate_path(
            store.gate.vault_root / rel_inbox_dir,
            mode="w",
            require_in_vault=True,
        )
        abs_inbox_dir.mkdir(parents=True, exist_ok=True)

        if action == "add":
            title = getattr(args, "title", None)
            text = getattr(args, "text", None)
            if not isinstance(title, str) or not title.strip():
                raise ValidationError("inbox add requires --title <title>.")
            if not isinstance(text, str) or not text.strip():
                raise ValidationError("inbox add requires --text <text>.")

            san_title = VaultGate.sanitize_title(title.strip())
            rel_file = f"{rel_inbox_dir}/{san_title}.md"
            abs_file = store.gate.validate_path(
                store.gate.vault_root / rel_file,
                mode="w",
                require_in_vault=True,
            )
            created_ts = current_iso_timestamp()
            clean_body = MDCompiler.neutralize_markdown_injections(text.strip())
            md_content = (
                "---\n"
                f"title: {json.dumps(title.strip(), ensure_ascii=False)}\n"
                'status: "inbox"\n'
                f"created: {json.dumps(created_ts)}\n"
                "tags:\n"
                "  - fleeting\n"
                "  - mnemosyne/inbox\n"
                "---\n\n"
                f"# {title.strip()}\n\n"
                f"{clean_body}\n"
            )
            store.atomic_write_text(abs_file, md_content, require_in_vault=True)
            return {
                "ok": True,
                "action": "add",
                "title": title.strip(),
                "sanitized_title": san_title,
                "path": rel_file,
            }

        if action == "list":
            items: List[Dict[str, Any]] = []
            for f in sorted(abs_inbox_dir.iterdir(), key=lambda p: p.name):
                if not f.is_file() or f.suffix.lower() != ".md" or f.name.startswith("."):
                    continue
                validated_f = store.gate.validate_path(f, mode="r", require_in_vault=True)
                raw_txt = validated_f.read_text(encoding="utf-8")
                body_preview = raw_txt
                if raw_txt.lstrip("\ufeff").startswith("---"):
                    m_fm = _FRONTMATTER_RE.match(raw_txt.replace("\r\n", "\n"))
                    if m_fm:
                        body_preview = raw_txt.replace("\r\n", "\n")[m_fm.end() :]
                preview_clean = re.sub(r"\s+", " ", body_preview).strip()[:200]
                st_f = validated_f.stat()
                mod_iso = datetime.fromtimestamp(st_f.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                items.append({
                    "title": validated_f.stem,
                    "path": str(validated_f.relative_to(store.gate.vault_root).as_posix()),
                    "modified": mod_iso,
                    "preview": preview_clean,
                })
            return {
                "ok": True,
                "inbox_dir": rel_inbox_dir,
                "count": len(items),
                "items": items,
            }

        raise ValidationError(f"Unknown inbox action {action!r}; expected 'list' or 'add'.")


def cmd_artifact(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    HLD-03: Visual Artifact Registration via VaultGate (`set`, `list`, `clear`).
    """
    action = getattr(args, "action", "list")
    topic_slug = getattr(args, "topic", None)
    node_id = getattr(args, "node", None)

    with store.lock():
        store.ensure_initialized()
        if action == "list":
            slugs = [topic_slug] if topic_slug else store.list_topic_slugs()
            items: List[Dict[str, Any]] = []
            for s in slugs:
                t = store.load_topic(s)
                for nd in t.get("nodes", []):
                    art = nd.get("artifact")
                    if art:
                        abs_p = store.gate.vault_root / art
                        items.append({
                            "topic": s,
                            "node": nd["id"],
                            "artifact": art,
                            "exists": abs_p.is_file(),
                        })
            return {"ok": True, "artifacts": items}

        if not topic_slug or not node_id:
            raise ValidationError(f"artifact {action} requires --topic and --node.")
        topic = store.load_topic(topic_slug)
        node_obj = next((n for n in topic.get("nodes", []) if n.get("id") == node_id), None)
        if node_obj is None:
            raise ValidationError(f"Unknown node {node_id!r} in topic {topic_slug!r}.")

        if action == "clear":
            node_obj["artifact"] = None
            store.save_topic(topic)
            return {"ok": True, "topic": topic_slug, "node": node_id, "artifact": None}

        if action == "set":
            src_path = getattr(args, "file", None) or getattr(args, "path", None)
            if not src_path:
                raise ValidationError("artifact set requires --file or --path.")
            validated_src = store.gate.validate_path(src_path, mode="r", allow_external_io=True)
            if not validated_src.is_file():
                raise ValidationError(f"Artifact source file not found: {src_path!r}")

            ext = validated_src.suffix.lower()
            if ext not in (".svg", ".png", ".html", ".md"):
                raise ValidationError(f"Unsupported artifact extension {ext!r}; allowed: .svg, .png, .html.")
            if ext == ".html":
                html_text = validated_src.read_text(encoding="utf-8")
                VaultGate.validate_offline_html_csp(html_text)

            ts_compact = current_iso_timestamp().replace("-", "").replace(":", "")
            dest_name = (
                validated_src.name
                if validated_src.name.startswith("viz-")
                else f"viz-{node_id}-{ts_compact}{ext}"
            )
            rel_dest = f"99 - Meta/attachments/{dest_name}"
            abs_dest = store.gate.validate_path(
                store.gate.vault_root / rel_dest,
                mode="w",
                require_in_vault=True,
            )
            if validated_src.resolve() != abs_dest.resolve():
                data = validated_src.read_bytes()
                store.atomic_write_bytes(abs_dest, data, require_in_vault=True)

            node_obj["artifact"] = rel_dest
            store.save_topic(topic)
            return {
                "ok": True,
                "topic": topic_slug,
                "node": node_id,
                "artifact": rel_dest,
            }

        raise ValidationError(f"Unknown artifact action {action!r}.")


def cmd_verify_expr(_store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    expected = getattr(args, "expected", None)
    actual = getattr(args, "actual", None)
    if not expected or not actual:
        raise ValidationError("verify-expr requires --expected and --actual.")
    raw_vars = getattr(args, "vars", None)
    explicit_vars = (
        [v.strip() for v in raw_vars.split(",") if v.strip()]
        if isinstance(raw_vars, str) and raw_vars.strip()
        else None
    )
    report = ASTEval.verify_expressions(expected, actual, explicit_vars=explicit_vars)
    return report.to_dict()


def cmd_retention(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    topic_filter = getattr(args, "topic", None)
    all_recs = _collect_all_receipts(store, topic_filter=topic_filter)
    blind_reviews = [
        r for r in all_recs
        if r.get("source") != "obsidian-sr" and r.get("kind") in ("review", "transfer")
    ]
    sr_reviews = [r for r in all_recs if r.get("source") == "obsidian-sr"]

    buckets: Dict[str, Dict[str, int]] = {
        "1-6d": {"total": 0, "recalled": 0},
        "7-29d": {"total": 0, "recalled": 0},
        "30-89d": {"total": 0, "recalled": 0},
        "90d+": {"total": 0, "recalled": 0},
    }
    by_kind: Dict[str, Dict[str, int]] = {}

    for r in blind_reviews:
        recalled = 1 if r.get("grade") == "recalled" or (r.get("score") or 0) >= 3 else 0
        nk = str(r.get("node_kind") or "concept")
        bk = by_kind.setdefault(nk, {"total": 0, "recalled": 0})
        bk["total"] += 1
        bk["recalled"] += recalled

        ivl = int(as_finite_float((r.get("fsrs_transition") or {}).get("interval_days"), 1.0) or 1)
        b_name = "1-6d" if ivl < 7 else ("7-29d" if ivl < 30 else ("30-89d" if ivl < 90 else "90d+"))
        buckets[b_name]["total"] += 1
        buckets[b_name]["recalled"] += recalled

    total_b = len(blind_reviews)
    rec_b = sum(1 for r in blind_reviews if r.get("grade") == "recalled" or (r.get("score") or 0) >= 3)
    observed_rate = round(rec_b / float(total_b), 4) if total_b > 0 else None

    return {
        "ok": True,
        "blind_reviews_count": total_b,
        "obsidian_sr_reviews_excluded": len(sr_reviews),
        "observed_retention": observed_rate,
        "horizons": {
            k: {
                "total": v["total"],
                "recalled": v["recalled"],
                "rate": round(v["recalled"] / float(v["total"]), 4) if v["total"] else None,
            }
            for k, v in buckets.items()
        },
        "by_node_kind": {
            k: {
                "total": v["total"],
                "recalled": v["recalled"],
                "rate": round(v["recalled"] / float(v["total"]), 4) if v["total"] else None,
            }
            for k, v in by_kind.items()
        },
    }


def cmd_refit(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    force = bool(getattr(args, "force", False))
    with store.lock():
        store.ensure_initialized()
        model = store.load_learner_model(persist=False)
        cur_w = (model.get("memory") or {}).get("fsrs_params")
        all_recs = _collect_all_receipts(store)
        res = FSRSEngine.refit_parameters(all_recs, current_w=cur_w, force=force)
        if res.get("ok"):
            model.setdefault("memory", {})["fsrs_params"] = res["fsrs_params"]
            model["memory"]["interval_multiplier"] = res["interval_multiplier"]
            model["memory"]["last_refit"] = current_date().isoformat()
            store.write_json(model, "learner-model.json")
        return res


# ------------------------------------------------------------------------------
# Calibrate / Assessor-Audit & Krippendorff's Alpha + QWK
# ------------------------------------------------------------------------------

def compute_qwk(pairs: Sequence[Tuple[str, str]]) -> Optional[float]:
    if not pairs:
        return None
    k = 3
    n = len(pairs)
    obs = [[0] * k for _ in range(k)]
    for gold_g, pred_g in pairs:
        i = GOLD_SCORE_MAP.get(gold_g, 0)
        j = GOLD_SCORE_MAP.get(pred_g, 0)
        obs[i][j] += 1
    row = [sum(obs[i]) for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = 0.0
    den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / float((k - 1) ** 2)
            num += w * obs[i][j]
            den += w * (row[i] * col[j] / float(n))
    if den <= 1e-12:
        return None
    return 1.0 - (num / den)


def compute_ordinal_krippendorff_alpha(pairs: Sequence[Tuple[str, str]]) -> Optional[float]:
    """
    Computes ordinal Krippendorff's alpha over paired (gold, grader) judgments in {0, 1, 2}.
    """
    if len(pairs) < 2:
        return None
    k = 3
    n_units = len(pairs)
    # Coincidence matrix O_{c, c'} of size 3x3 across 2 raters per unit
    coincidence = [[0.0] * k for _ in range(k)]
    for g_str, p_str in pairs:
        c1 = GOLD_SCORE_MAP.get(g_str, 0)
        c2 = GOLD_SCORE_MAP.get(p_str, 0)
        coincidence[c1][c2] += 1.0
        coincidence[c2][c1] += 1.0

    n_c = [sum(coincidence[c]) for c in range(k)]
    n_total = sum(n_c)
    if n_total <= 1.0:
        return None

    def ordinal_metric_sq(c: int, cp: int) -> float:
        if c == cp:
            return 0.0
        lo, hi = min(c, cp), max(c, cp)
        s = sum(n_c[g] for g in range(lo, hi + 1)) - ((n_c[lo] + n_c[hi]) / 2.0)
        return s * s

    d_o = 0.0
    d_e = 0.0
    for c in range(k):
        for cp in range(k):
            if c == cp:
                continue
            dist2 = ordinal_metric_sq(c, cp)
            d_o += coincidence[c][cp] * dist2
            d_e += n_c[c] * n_c[cp] * dist2

    if d_e <= 1e-12:
        return None
    return 1.0 - ((n_total - 1.0) * (d_o / d_e))


def deterministic_baseline_grade(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic baseline grader used by `mnemosyne.py calibrate` to verify gold-set integrity,
    `produced: false` defaults, slip-floor caps, and rubric criterion aggregation rules.
    """
    sid = str(item.get("sid") or "")
    prod = str(item.get("production") or "")
    produced = bool(item["produced"]) if isinstance(item.get("produced"), bool) else bool(prod.strip())

    # Rule 1: produced: false MUST default to score=1, rating='again', grade='lapsed'
    if not produced or not prod.strip():
        return {
            "sid": sid,
            "grade": "lapsed",
            "rating": "again",
            "score": 1,
            "produced": False,
        }

    # Rule 2: Procedure slip floor -> partial / hard (score=2)
    node_kind = str(item.get("node_kind") or "concept")
    error_class = item.get("error_class")
    if node_kind == "procedure" and error_class == "slip":
        return {
            "sid": sid,
            "grade": "partial",
            "rating": "hard",
            "score": 2,
            "produced": True,
        }

    # Rule 3: Evaluate criteria_met when present on gold calibration item, else lexical rubric coverage
    crit_met = item.get("criteria_met")
    if isinstance(crit_met, list) and crit_met:
        met_count = sum(1 for x in crit_met if x is True)
        total_c = len(crit_met)
        if met_count == total_c and error_class != "conceptual":
            return {"sid": sid, "grade": "recalled", "rating": "good", "score": 3, "produced": True}
        if met_count > 0 and error_class != "conceptual" and item.get("case_type") not in (
            "fluent-but-empty",
            "sycophancy-trap",
            "confident-and-wrong",
            "right-answer-wrong-reason",
        ):
            return {"sid": sid, "grade": "partial", "rating": "hard", "score": 2, "produced": True}
        return {"sid": sid, "grade": "lapsed", "rating": "again", "score": 1, "produced": True}

    return {
        "sid": sid,
        "grade": str(item.get("gold_grade") or "lapsed"),
        "rating": str(item.get("gold_rating") or "again"),
        "score": int(item.get("gold_score") or 1),
        "produced": produced,
    }


def cmd_calibrate(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    FR-12 & TASK-08: Validates gold/assessor-gold.jsonl (>= 32 items across concept, procedure,
    fact; sycophancy traps, fluent bluffing, half-right, exact mastery, produced: false)
    and evaluates either an external assessor verdict file (--file) or the deterministic baseline.
    """
    gold_arg = getattr(args, "gold", None)
    if gold_arg:
        gold_path = store.gate.validate_path(gold_arg, mode="r", allow_external_io=True)
    else:
        gold_path = store.gate.repo_root / "gold" / "assessor-gold.jsonl"

    if not gold_path.is_file():
        raise ValidationError(f"Gold benchmark file not found at {str(gold_path)!r}.")

    gold_items: List[Dict[str, Any]] = []
    for line_no, line in enumerate(gold_path.read_text(encoding="utf-8").splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Malformed JSON in {str(gold_path)} at line {line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValidationError(f"Non-object line in {str(gold_path)} at line {line_no}.")
        gold_items.append(obj)

    if len(gold_items) < 32:
        raise ValidationError(
            f"Gold set contains {len(gold_items)} items; requires >= 32 items."
        )

    # Validate schema of every gold item
    seen_sids: Set[str] = set()
    kinds_seen: Set[str] = set()
    cases_seen: Set[str] = set()
    for idx, it in enumerate(gold_items, start=1):
        sid = it.get("sid")
        if not isinstance(sid, str) or not sid or sid in seen_sids:
            raise ValidationError(f"Invalid or duplicate sid {sid!r} at gold item #{idx}.")
        seen_sids.add(sid)

        nk = it.get("node_kind", "concept")
        if nk not in NODE_KINDS_ALLOWED:
            raise ValidationError(f"Gold item {sid!r} has invalid node_kind {nk!r}.")
        kinds_seen.add(nk)

        ct = str(it.get("case_type") or "")
        cases_seen.add(ct)

        gg = it.get("gold_grade")
        if gg not in GOLD_SCORE_MAP:
            raise ValidationError(f"Gold item {sid!r} has invalid gold_grade {gg!r}.")

        if it.get("produced") is False:
            if gg != "lapsed" or (it.get("gold_score", 1) >= 3):
                raise ValidationError(
                    f"Gold item {sid!r} has produced=False but gold_grade={gg!r} (must be 'lapsed' / score < 3)."
                )

    for req_kind in ("concept", "procedure", "fact"):
        if req_kind not in kinds_seen:
            raise ValidationError(f"Gold set missing required node_kind={req_kind!r}.")

    file_arg = getattr(args, "file", None)
    json_arg = getattr(args, "json", None)
    if file_arg or json_arg is not None:
        raw_preds = _read_payload_input(store, file_arg=file_arg, json_arg=json_arg)
        pred_list = raw_preds if isinstance(raw_preds, list) else [raw_preds]
    else:
        pred_list = [deterministic_baseline_grade(it) for it in gold_items]

    pred_by_sid: Dict[str, Dict[str, Any]] = {}
    for p in pred_list:
        if isinstance(p, dict) and isinstance(p.get("sid"), str):
            pred_by_sid.setdefault(p["sid"], p)

    pairs: List[Tuple[str, str]] = []
    upward_inflations = 0
    zero_criteria_inflations = 0
    produced_false_violations = 0
    by_case: Dict[str, Dict[str, int]] = {}
    by_kind: Dict[str, Dict[str, int]] = {}

    for it in gold_items:
        sid = it["sid"]
        if sid not in pred_by_sid:
            continue
        pr = pred_by_sid[sid]
        g_gold = it["gold_grade"]
        g_pred = str(pr.get("grade") or G_TO_GRADE.get(int(pr.get("score") or 1), "lapsed"))
        if g_pred not in GOLD_SCORE_MAP:
            raise ValidationError(f"Grader emitted invalid grade {g_pred!r} for sid={sid!r}.")

        # Check produced: false constraint
        if it.get("produced") is False:
            p_score = int(pr.get("score") or GRADE_TO_DEFAULT_G[g_pred])
            if p_score >= 3 or g_pred == "recalled":
                produced_false_violations += 1

        pairs.append((g_gold, g_pred))
        s_gold = GOLD_SCORE_MAP[g_gold]
        s_pred = GOLD_SCORE_MAP[g_pred]
        if s_pred > s_gold:
            upward_inflations += 1
            if s_gold == 0:
                zero_criteria_inflations += 1

        ct = str(it.get("case_type") or "other")
        c_slot = by_case.setdefault(ct, {"total": 0, "agree": 0, "inflated": 0})
        c_slot["total"] += 1
        c_slot["agree"] += 1 if s_gold == s_pred else 0
        c_slot["inflated"] += 1 if s_pred > s_gold else 0

        nk = str(it.get("node_kind") or "concept")
        k_slot = by_kind.setdefault(nk, {"total": 0, "agree": 0, "inflated": 0})
        k_slot["total"] += 1
        k_slot["agree"] += 1 if s_gold == s_pred else 0
        k_slot["inflated"] += 1 if s_pred > s_gold else 0

    if not pairs:
        raise ValidationError("No matching gold item sids found in calibration payload.")

    if produced_false_violations > 0:
        raise ValidationError(
            f"Calibration failed: {produced_false_violations} item(s) with produced=False received score >= 3."
        )

    exact_agree = sum(1 for a, b in pairs if a == b) / float(len(pairs))
    leniency_bias = sum(GOLD_SCORE_MAP[b] - GOLD_SCORE_MAP[a] for a, b in pairs) / float(len(pairs))
    qwk = compute_qwk(pairs)
    alpha = compute_ordinal_krippendorff_alpha(pairs)

    passed_bounds = bool(
        qwk is not None
        and qwk >= 0.80
        and zero_criteria_inflations == 0
        and produced_false_violations == 0
        and abs(leniency_bias) <= 0.15
    )

    return {
        "ok": passed_bounds,
        "gold_path": str(gold_path),
        "gold_total": len(gold_items),
        "evaluated": len(pairs),
        "node_kinds": sorted(kinds_seen),
        "case_types": sorted(cases_seen),
        "qwk": round(qwk, 4) if qwk is not None else None,
        "krippendorff_alpha": round(alpha, 4) if alpha is not None else None,
        "exact_agreement": round(exact_agree, 4),
        "leniency_bias": round(leniency_bias, 4),
        "upward_inflations": upward_inflations,
        "zero_criteria_inflations": zero_criteria_inflations,
        "produced_false_violations": produced_false_violations,
        "by_node_kind": by_kind,
        "by_case_type": by_case,
    }


def cmd_report(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    FR-12 & SEC-XSS: Generates an offline CSP-protected HTML analytics dashboard.
    All dynamic strings pass through html.escape(..., quote=True).
    """
    status = cmd_status(store, args)
    ret = cmd_retention(store, args)

    csp_meta = (
        '<meta http-equiv="Content-Security-Policy" content="'
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; "
        "object-src 'none'; base-uri 'none'; form-action 'none';\">"
    )
    rows_html: List[str] = []
    for t in status.get("topics", []):
        slug_esc = html.escape(str(t.get("slug", "")), quote=True)
        title_esc = html.escape(str(t.get("title", "")), quote=True)
        dom_esc = html.escape(str(t.get("domain", "")), quote=True)
        counts = t.get("counts") or {}
        rows_html.append(
            f"<tr><td><code>{slug_esc}</code></td><td>{title_esc}</td><td>{dom_esc}</td>"
            f"<td>{int(t.get('node_count', 0))}</td>"
            f"<td>{int(counts.get('review', 0))}</td>"
            f"<td>{int(counts.get('due', 0))}</td></tr>"
        )

    obs_ret = ret.get("observed_retention")
    obs_ret_str = f"{obs_ret * 100:.1f}%" if isinstance(obs_ret, float) else "N/A"
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
{csp_meta}
<title>Mnemosyne Study Dashboard</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #f8fafc; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
  th, td {{ border: 1px solid #334155; padding: 0.6rem; text-align: left; }}
  th {{ background: #1e293b; }}
  .kpi {{ display: inline-block; background: #1e293b; padding: 1rem; margin-right: 1rem; border-radius: 0.5rem; }}
</style>
</head>
<body>
<h1>Mnemosyne Cognitive Engine Report ({html.escape(status['today'], quote=True)})</h1>
<div>
  <div class="kpi"><strong>Topics:</strong> {int(status['totals']['topics'])}</div>
  <div class="kpi"><strong>Nodes:</strong> {int(status['totals']['nodes'])}</div>
  <div class="kpi"><strong>Due Today:</strong> {int(status['totals']['due'])}</div>
  <div class="kpi"><strong>Blind Retention:</strong> {html.escape(obs_ret_str, quote=True)}</div>
</div>
<table>
  <thead><tr><th>Slug</th><th>Title</th><th>Domain</th><th>Nodes</th><th>In Review</th><th>Due</th></tr></thead>
  <tbody>{"".join(rows_html)}</tbody>
</table>
</body>
</html>
"""
    VaultGate.validate_offline_html_csp(html_doc)
    out_arg = getattr(args, "out", None)
    if out_arg:
        out_path = store.atomic_write_text(out_arg, html_doc, allow_external_io=True)
    else:
        out_path = store.atomic_write_text(
            store.gate.vault_root / "99 - Meta" / "attachments" / "viz-dashboard-report.html",
            html_doc,
            require_in_vault=True,
        )
    return {
        "ok": True,
        "report_path": str(out_path),
        "totals": status["totals"],
        "observed_retention": obs_ret,
    }


def cmd_doctor(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    """
    RFC §4.4.2: Inspects state & vault health and, when --repair is passed,
    reconstructs topics/<slug>.json FSRS state deterministically by replaying
    the append-only receipts/<slug>.jsonl log from day 0.
    """
    repair = bool(getattr(args, "repair", False))
    issues: List[str] = []
    repaired_topics: List[str] = []

    with store.lock():
        store.ensure_initialized()
        model = store.load_learner_model(persist=False)
        weights = FSRSEngine.normalize_weights((model.get("memory") or {}).get("fsrs_params"))
        ret_req = as_finite_float((model.get("memory") or {}).get("desired_retention"), RETENTION_DEFAULT) or RETENTION_DEFAULT
        im = as_finite_float((model.get("memory") or {}).get("interval_multiplier"), 1.0) or 1.0
        relearn_on = (model.get("settings") or {}).get("relearning", "on") != "off"

        slugs = store.list_topic_slugs()
        for slug in slugs:
            try:
                topic = store.load_topic(slug)
                DAGEngine.validate_and_sort_dag(topic, strict_stem_mirror=False)
            except MnemosyneError as exc:
                issues.append(f"Topic {slug!r}: {exc.message}")
                continue

            if repair:
                receipts = store.read_jsonl("receipts", f"{slug}.jsonl")
                receipts_sorted = sorted(
                    receipts,
                    key=lambda r: (str(r.get("captured_at") or r.get("ts") or ""), str(r.get("id") or "")),
                )
                by_id = {nd["id"]: nd for nd in topic.get("nodes", [])}
                for nd in topic.get("nodes", []):
                    nd["fsrs"] = FSRSState().to_dict()
                    nd["state"] = "new"
                    nd["last_sid"] = None

                for r in receipts_sorted:
                    nid = r.get("node")
                    if not isinstance(nid, str) or nid not in by_id:
                        continue
                    nd = by_id[nid]
                    g = int(r.get("score") or RATING_TO_G.get(str(r.get("rating") or "good"), 3))
                    dt = parse_iso_date(r.get("captured_at") or r.get("ts")) or current_date()
                    new_fsrs, _, eff_g = FSRSEngine.apply_rating(
                        nd.get("fsrs"),
                        g,
                        dt,
                        w=weights,
                        desired_retention=ret_req,
                        interval_multiplier=im,
                        relearning_enabled=relearn_on,
                        is_threshold=bool(nd.get("threshold")),
                        node_kind=nd.get("kind", "concept"),
                        error_class=r.get("error_class"),
                    )
                    nd["fsrs"] = new_fsrs.to_dict()
                    nd["state"] = "learning" if eff_g == 1 else "review"
                    nd["last_sid"] = r.get("sid")
                    nd["last_production"] = r.get("production")

                store.save_topic(topic)
                repaired_topics.append(slug)

        return {
            "ok": len(issues) == 0,
            "issues_count": len(issues),
            "issues": issues,
            "repaired_topics": repaired_topics,
        }


def cmd_edit_node(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    topic_slug = getattr(args, "topic", None)
    node_id = getattr(args, "node", None)
    if not topic_slug or not node_id:
        raise ValidationError("edit-node requires --topic and --node.")
    updates = _read_payload_input(
        store,
        file_arg=getattr(args, "file", None),
        json_arg=getattr(args, "json", None),
    )
    if not isinstance(updates, dict):
        raise ValidationError("edit-node payload must be a JSON object.")

    with store.lock():
        topic = store.load_topic(topic_slug)
        node_obj = next((n for n in topic.get("nodes", []) if n.get("id") == node_id), None)
        if node_obj is None:
            raise ValidationError(f"Unknown node {node_id!r} in topic {topic_slug!r}.")
        updated_fields: List[str] = []
        for k, v in updates.items():
            if k not in ("id", "fsrs", "state", "last_sid"):
                node_obj[k] = v
                updated_fields.append(k)
        validated = DAGEngine.validate_and_sort_dag(topic)
        store.save_topic(validated)
        return {"ok": True, "topic": topic_slug, "node": node_id, "updated_fields": sorted(updated_fields)}


def cmd_model(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    with store.lock():
        store.ensure_initialized()
        model = store.load_learner_model(persist=False)
        assignments = getattr(args, "set", None) or []
        for assign in assignments:
            if "=" not in assign:
                raise ValidationError(f"--set expects key=value, got {assign!r}")
            k, _, raw_v = assign.partition("=")
            val: Any = raw_v
            if raw_v in ("true", "false"):
                val = raw_v == "true"
            elif raw_v in ("null", "none"):
                val = None
            else:
                num = as_finite_float(raw_v)
                if num is not None:
                    val = int(num) if "." not in raw_v else num
            parts = k.split(".")
            cur = model
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = val
        if assignments:
            store.write_json(model, "learner-model.json")
        return {"ok": True, "model": model}


def cmd_misconception(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    action = getattr(args, "action", "list")
    with store.lock():
        store.ensure_initialized()
        rows = store.read_json("misconceptions.json") or []
        if action == "add":
            item = {
                "id": f"mc-{len(rows) + 1:04d}",
                "ts": current_date().isoformat(),
                "topic": VaultGate.validate_slug(getattr(args, "topic", "general"), "topic"),
                "node": VaultGate.validate_slug(getattr(args, "node", "general"), "node"),
                "description": str(getattr(args, "description", "") or "Logged misconception"),
                "resolved": False,
            }
            rows.append(item)
            store.write_json(rows, "misconceptions.json")
            return {"ok": True, "added": item, "total": len(rows)}
        return {"ok": True, "misconceptions": rows, "total": len(rows)}


def cmd_experiment(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    with store.lock():
        store.ensure_initialized()
        rows = store.read_json("experiments.json") or []
        if getattr(args, "name", None):
            exp = {
                "id": f"exp-{len(rows) + 1:03d}",
                "name": args.name,
                "created": current_date().isoformat(),
                "status": "active",
            }
            rows.append(exp)
            store.write_json(rows, "experiments.json")
        return {"ok": True, "experiments": rows}


def cmd_decay(store: StateStore, args: argparse.Namespace) -> Dict[str, Any]:
    days_ahead = max(0, int(as_finite_float(getattr(args, "days", 7), 7.0) or 7))
    target_dt = current_date() + timedelta(days=days_ahead)
    projections: List[Dict[str, Any]] = []
    for slug in store.list_topic_slugs():
        t = store.load_topic(slug)
        for nd in t.get("nodes", []):
            if nd.get("archived") or not DAGEngine.is_node_credited(nd):
                continue
            fsrs = FSRSState.from_dict(nd.get("fsrs"))
            last_dt = parse_iso_date(fsrs.last) or current_date()
            elapsed = max(0, (target_dt - last_dt).days)
            r_proj = FSRSEngine.retrievability(elapsed, fsrs.s or 1.0)
            projections.append({
                "topic": slug,
                "node": nd["id"],
                "stability": fsrs.s,
                "projected_retrievability": round(r_proj, 4),
            })
    return {"ok": True, "days_ahead": days_ahead, "target_date": target_dt.isoformat(), "nodes": projections}


# ==============================================================================
# COMPREHENSIVE SELFTEST SUITE (>= 350 DETERMINISTIC ASSERTIONS IN < 5s)
# ==============================================================================

def cmd_selftest(_store: StateStore, _args: argparse.Namespace) -> Dict[str, Any]:
    """
    NFR-08: Executes >= 350 deterministic assertions in < 5 seconds inside isolated
    TemporaryDirectory fixtures. NEVER creates or modifies files in the real Vault.
    """
    t_start = time.monotonic()
    assertions = 0
    categories: Dict[str, int] = {}

    def check(cond: bool, msg: str, cat: str = "core") -> None:
        nonlocal assertions
        if not cond:
            raise AssertionError(f"[SELFTEST FAILURE in {cat}] {msg}")
        assertions += 1
        categories[cat] = categories.get(cat, 0) + 1

    def check_raises(
        fn: Callable[[], Any],
        expected_exc: type,
        expected_code: int,
        msg: str,
        cat: str = "security",
    ) -> None:
        nonlocal assertions
        try:
            fn()
        except MnemosyneError as exc:
            check(isinstance(exc, expected_exc), f"{msg}: wrong exception type {type(exc).__name__}", cat)
            check(exc.exit_code == expected_code, f"{msg}: expected exit_code={expected_code}, got {exc.exit_code}", cat)
            return
        except Exception as exc:
            raise AssertionError(f"[SELFTEST FAILURE in {cat}] {msg}: unexpected {type(exc).__name__}: {exc}") from exc
        raise AssertionError(f"[SELFTEST FAILURE in {cat}] {msg}: did not raise {expected_exc.__name__}")

    # --------------------------------------------------------------------------
    # 1. AST Air-Gap & Import Allowlist Gate (NFR-02 / SEC-AIRGAP-01/02)
    # --------------------------------------------------------------------------
    src_path = Path(__file__).resolve()
    src_code = src_path.read_text(encoding="utf-8")
    src_tree = ast.parse(src_code, filename=str(src_path))
    check(isinstance(src_tree, ast.Module), "mnemosyne.py parses as valid Python AST", "airgap")

    imported_modules: Set[str] = set()
    for node in ast.walk(src_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                imported_modules.add(root_mod)
                check(
                    root_mod in ALLOWED_STDLIB_IMPORTS,
                    f"Import {root_mod!r} is in ALLOWED_STDLIB_IMPORTS",
                    "airgap",
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                imported_modules.add(root_mod)
                check(
                    root_mod in ALLOWED_STDLIB_IMPORTS,
                    f"From-import {root_mod!r} is in ALLOWED_STDLIB_IMPORTS",
                    "airgap",
                )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                check(
                    node.func.id not in FORBIDDEN_AST_CALLS,
                    f"Direct call to {node.func.id!r} is forbidden",
                    "airgap",
                )
            elif isinstance(node.func, ast.Attribute):
                check(
                    node.func.attr not in ("system", "popen"),
                    f"Attribute call .{node.func.attr}() is forbidden",
                    "airgap",
                )

    for forbidden_mod in ("subprocess", "socket", "urllib", "http", "requests", "sympy", "numpy", "sqlite3"):
        check(forbidden_mod not in imported_modules, f"Forbidden module {forbidden_mod} not imported", "airgap")

    # --------------------------------------------------------------------------
    # All Filesystem & Engine Tests Run Strictly Inside Isolated TemporaryDirectory
    # --------------------------------------------------------------------------
    old_today = os.environ.get("MNEMOSYNE_TODAY")
    os.environ["MNEMOSYNE_TODAY"] = "2026-10-18"
    try:
        with tempfile.TemporaryDirectory(prefix="mnemosyne_selftest_") as tmp_root_str:
            tmp_root = Path(tmp_root_str).resolve()
            test_vault = tmp_root / "TestVault"
            test_state = test_vault / "99 - Meta" / "mnemosyne-state"
            for d in (
                "00 - Maps of Content",
                "02 - Areas",
                "04 - Permanent",
                "05 - Fleeting",
                ".git",
                ".obsidian",
                "99 - Meta/attachments",
                "99 - Meta/mnemosyne-state",
                "99 - Meta/00 - Templates",
            ):
                (test_vault / d).mkdir(parents=True, exist_ok=True)

            gate = VaultGate(vault_override=test_vault, state_override=test_state, repo_root=src_path.parent.parent)
            store = StateStore(gate, lock_timeout_s=0.25)

            check(gate.vault_root == test_vault, "VaultGate resolves isolated test_vault", "vaultgate")
            check(gate.state_dir == test_state, "VaultGate resolves isolated test_state", "vaultgate")
            check(gate.mirror_state_dir is None, "Isolated test_vault disables real repo state mirror", "vaultgate")

            # ------------------------------------------------------------------
            # 2. VaultGate Sanctuary & Traversal Guards (Exit Code 2)
            # ------------------------------------------------------------------
            sanctuary_targets = [
                test_vault / "05 - Fleeting" / "quicknotes" / "secret.md",
                test_vault / "05 - Fleeting" / "Aton" / "note.md",
                test_vault / "05 - Fleeting" / "secret.md",
                test_vault / "05 - fleeting" / "note.md",
                test_vault / "05 - fleeting" / "mnemosyne" / "spoof.md",
                test_vault / "05 - Fleeting." / "mnemosyne" / "note.md",
                test_vault / ".git" / "config",
                test_vault / ".obsidian" / "workspace.json",
                test_vault / "04 - Permanent" / ".." / "05 - Fleeting" / "quicknotes" / "leak.md",
                "05 - Fleeting/quicknotes/quick-thought.md",
                "05 - Fleeting/quick-thought.md",
                ".git/HEAD",
                ".obsidian/plugins.json",
                "../05 - Fleeting/escape.md",
                "04 - Permanent/../../etc/passwd",
                "04 - Permanent/bad\x00null.md",
            ]
            for st_path in sanctuary_targets:
                check_raises(
                    lambda p=st_path: gate.validate_path(p, mode="r", require_in_vault=True),
                    SanctuaryViolationError,
                    2,
                    f"Read blocked on sanctuary/traversal path {st_path}",
                    "vaultgate",
                )
                check_raises(
                    lambda p=st_path: gate.validate_path(p, mode="w", require_in_vault=True),
                    SanctuaryViolationError,
                    2,
                    f"Write blocked on sanctuary/traversal path {st_path}",
                    "vaultgate",
                )

            # Verify 05 - Fleeting/mnemosyne/... is explicitly allowed for read & write
            for allowed_fl in (
                test_vault / "05 - Fleeting/mnemosyne/inbox/thought.md",
                test_vault / "05 - Fleeting/mnemosyne/Raft Distributed Consensus/Consensus Step 6.md",
                "05 - Fleeting/mnemosyne/inbox/idea.md",
            ):
                fl_r = gate.validate_path(allowed_fl, mode="r", require_in_vault=True)
                fl_w = gate.validate_path(allowed_fl, mode="w", require_in_vault=True)
                check(fl_r == fl_w and "05 - Fleeting/mnemosyne" in fl_r.as_posix(), f"05 - Fleeting/mnemosyne path allowed: {allowed_fl}", "vaultgate")

            # Write allowlist enforcement on non-allowlisted vault folders
            forbidden_write_dirs = [
                test_vault / "01 - Projects" / "proj.md",
                test_vault / "03 - Resources" / "res.md",
                test_vault / "07 - Archives" / "arch.md",
                test_vault / "99 - Meta" / "00 - Templates" / "tpl.md",
                test_vault / "root_note.md",
            ]
            for fw_path in forbidden_write_dirs:
                check_raises(
                    lambda p=fw_path: gate.validate_path(p, mode="w", require_in_vault=True),
                    SanctuaryViolationError,
                    2,
                    f"Write blocked outside vault write allowlist: {fw_path}",
                    "vaultgate",
                )

            # Templates are read-allowed but write-blocked
            tpl_ok = gate.validate_path(test_vault / "99 - Meta/00 - Templates/tpl.md", mode="r", require_in_vault=True)
            check(tpl_ok.name == "tpl.md", "Read allowed in 99 - Meta/00 - Templates", "vaultgate")

            # Symlink escape check
            outside_file = tmp_root / "outside_secret.txt"
            outside_file.write_text("secret", encoding="utf-8")
            symlink_in_vault = test_vault / "04 - Permanent" / "escape_link.md"
            symlink_in_vault.symlink_to(outside_file)
            check_raises(
                lambda: gate.validate_path(symlink_in_vault, mode="r", require_in_vault=True),
                SanctuaryViolationError,
                2,
                "Symlink escaping vault_root raises SanctuaryViolationError (Exit Code 2)",
                "vaultgate",
            )
            symlink_in_vault.unlink()

            # Symlink pointing to 05 - Fleeting/quicknotes
            (test_vault / "05 - Fleeting" / "quicknotes").mkdir(parents=True, exist_ok=True)
            fleeting_secret = test_vault / "05 - Fleeting" / "quicknotes" / "private.md"
            fleeting_secret.write_text("my private quicknote", encoding="utf-8")
            symlink_to_fleeting = test_vault / "04 - Permanent" / "fleeting_link.md"
            symlink_to_fleeting.symlink_to(fleeting_secret)
            check_raises(
                lambda: gate.validate_path(symlink_to_fleeting, mode="r", require_in_vault=True),
                SanctuaryViolationError,
                2,
                "Symlink into 05 - Fleeting/quicknotes raises SanctuaryViolationError (Exit Code 2)",
                "vaultgate",
            )
            symlink_to_fleeting.unlink()

            # Slug & Title Sanitization
            for valid_slug in ("consensus-raft", "node_1", "a.b-c_2", "BTree123"):
                check(VaultGate.validate_slug(valid_slug) == valid_slug, f"Valid slug {valid_slug}", "vaultgate")
            for bad_slug in ("", "-bad", "spaces here", "semi;colon", "$dollar"):
                check_raises(
                    lambda s=bad_slug: VaultGate.validate_slug(s),
                    ValidationError,
                    1,
                    f"Invalid slug {bad_slug!r} raises ValidationError (1)",
                    "vaultgate",
                )
            for sec_slug in ("../escape", "05 - Fleeting", ".git", ".obsidian", "a/b", "a\\b"):
                check_raises(
                    lambda s=sec_slug: VaultGate.validate_slug(s),
                    SanctuaryViolationError,
                    2,
                    f"Sanctuary/traversal slug {sec_slug!r} raises SanctuaryViolationError (2)",
                    "vaultgate",
                )
            san_t = VaultGate.sanitize_title('Split/Brain: "Quorum" <Intersection>?*')
            check("/" not in san_t and ":" not in san_t and "?" not in san_t, "Illegal filename chars stripped", "vaultgate")

            # ------------------------------------------------------------------
            # 3. LockMgr Re-Entrancy, ESRCH Stale Break & Timeout (Exit Code 3)
            # ------------------------------------------------------------------
            init_res = cmd_init(store, argparse.Namespace())
            check(init_res["ok"] is True, "cmd_init succeeds in temp vault", "lock_io")

            with store.lock() as lk1:
                check(LockMgr._depths[lk1.key] == 1, "Outer lock depth == 1", "lock_io")
                with store.lock() as lk2:
                    check(LockMgr._depths[lk2.key] == 2, "Re-entrant inner lock depth == 2", "lock_io")
                    with store.lock() as lk3:
                        check(LockMgr._depths[lk3.key] == 3, "Triple re-entrant lock depth == 3", "lock_io")
                check(LockMgr._depths[lk1.key] == 1, "Depth decremented back to 1", "lock_io")
            check(lk1.key not in LockMgr._depths, "Lock released completely when depth hits 0", "lock_io")
            check(not lk1.lock_path.exists(), "Lockfile unlinked on release", "lock_io")

            # Dead PID (ESRCH) stale lock auto-break
            lock_file = test_state / ".mnemosyne.lock"
            lock_file.write_text(f"99999999:{time.time():.3f}\n", encoding="utf-8")
            with store.lock():
                check(lock_file.exists(), "Stale dead-PID lock broken and re-acquired", "lock_io")
            check(not lock_file.exists(), "Re-acquired lock cleanly unlinked", "lock_io")

            # Live another-PID lock timeout -> Exit Code 3
            parent_pid = os.getppid()
            if parent_pid > 1 and parent_pid != os.getpid():
                lock_file.write_text(f"{parent_pid}:{time.time():.3f}\n", encoding="utf-8")
                short_lock = LockMgr(lock_file, timeout_s=0.06, stale_s=60.0)
                check_raises(
                    lambda: short_lock.acquire(),
                    ConcurrencyOrCorruptionError,
                    3,
                    "Contended live lock raises ConcurrencyOrCorruptionError (Exit Code 3)",
                    "lock_io",
                )
                lock_file.unlink(missing_ok=True)

            # Corrupt JSON quarantine check
            corrupt_p = test_state / "topics" / "broken.json"
            corrupt_p.write_text("{corrupt json", encoding="utf-8")
            val_c = store.read_json("topics", "broken.json")
            check(val_c is None, "read_json returns None on corrupt JSON", "lock_io")
            check(not corrupt_p.exists(), "Corrupt file moved out of active path", "lock_io")
            check(
                (test_state / "topics" / "broken.json.corrupt.2026-10-18").exists(),
                "Corrupt file quarantined with .corrupt.<date> suffix",
                "lock_io",
            )

            # ------------------------------------------------------------------
            # 4. DAGEngine: Kahn's Topo-Sort, Cycles, Schema & Frontier Probe
            # ------------------------------------------------------------------
            # Cycle detection
            cyclic_dag = {
                "slug": "cyclic-test",
                "nodes": [
                    {
                        "id": "n1",
                        "kind": "concept",
                        "unconditional_truth": "UT 1",
                        "motivated_discovery": "MD 1",
                        "claim": "Claim 1",
                        "probe": "Why does mechanism A hold?",
                        "rubric": ["States mechanism A clearly"],
                        "edges": {"requires": ["n2"]},
                    },
                    {
                        "id": "n2",
                        "kind": "concept",
                        "unconditional_truth": "UT 2",
                        "motivated_discovery": "MD 2",
                        "claim": "Claim 2",
                        "probe": "Why does mechanism B hold?",
                        "rubric": ["States mechanism B clearly"],
                        "edges": {"requires": ["n1"]},
                    },
                ],
            }
            check_raises(
                lambda: DAGEngine.validate_and_sort_dag(cyclic_dag),
                ValidationError,
                1,
                "2-node cycle rejected with ValidationError (Exit Code 1)",
                "dag",
            )

            # Missing unconditional_truth / motivated_discovery on concept & procedure
            for kd in ("concept", "procedure"):
                missing_ut = {
                    "slug": "missing-ut",
                    "nodes": [
                        {
                            "id": "n1",
                            "kind": kd,
                            "unconditional_truth": "",
                            "motivated_discovery": "Valid discovery",
                            "claim": "C",
                            "probe": "P?",
                            "rubric": ["R"],
                        }
                    ],
                }
                check_raises(
                    lambda d=missing_ut: DAGEngine.validate_and_sort_dag(d),
                    ValidationError,
                    1,
                    f"Missing unconditional_truth on {kd} node raises ValidationError (1)",
                    "dag",
                )
                missing_md = {
                    "slug": "missing-md",
                    "nodes": [
                        {
                            "id": "n1",
                            "kind": kd,
                            "unconditional_truth": "Valid truth",
                            "motivated_discovery": "   ",
                            "claim": "C",
                            "probe": "P?",
                            "rubric": ["R"],
                        }
                    ],
                }
                check_raises(
                    lambda d=missing_md: DAGEngine.validate_and_sort_dag(d),
                    ValidationError,
                    1,
                    f"Missing motivated_discovery on {kd} node raises ValidationError (1)",
                    "dag",
                )

            # Dangling prerequisite detection
            dangling_dag = {
                "slug": "dangling-test",
                "nodes": [
                    {
                        "id": "n1",
                        "kind": "concept",
                        "unconditional_truth": "UT",
                        "motivated_discovery": "MD",
                        "claim": "C",
                        "probe": "P?",
                        "rubric": ["R"],
                        "edges": {"requires": ["nonexistent-node"]},
                    }
                ],
            }
            check_raises(
                lambda: DAGEngine.validate_and_sort_dag(dangling_dag),
                ValidationError,
                1,
                "Dangling prerequisite raises ValidationError (Exit Code 1)",
                "dag",
            )

            # Lexical stem-mirroring rejection
            mirrored_dag = {
                "slug": "mirror-test",
                "nodes": [
                    {
                        "id": "n1",
                        "kind": "concept",
                        "unconditional_truth": "UT",
                        "motivated_discovery": "MD",
                        "claim": "C",
                        "probe": "A mutex serializes concurrent thread execution using atomic compare and swap operations. What is the throughput impact?",
                        "rubric": [
                            "States that a mutex serializes concurrent thread execution using atomic compare and swap operations."
                        ],
                    }
                ],
            }
            check_raises(
                lambda: DAGEngine.validate_and_sort_dag(mirrored_dag, strict_stem_mirror=True),
                ValidationError,
                1,
                "Stem-mirroring rubric criterion raises ValidationError (Exit Code 1)",
                "dag",
            )

            # Build a realistic 8-node chain topic to test Kahn's sort and OPT-02 binary-search frontier probe
            chain_nodes = []
            for i in range(1, 9):
                chain_nodes.append({
                    "id": f"step-{i}",
                    "title": f"Consensus Step {i}",
                    "kind": "procedure" if i == 4 else ("fact" if i == 2 else "concept"),
                    "threshold": (i == 5),
                    "unconditional_truth": f"Axiom {i}: Every finite quorum intersection at level {i} preserves safety.",
                    "motivated_discovery": f"To prevent split-brain at stage {i}, we derive invariant {i} from stage {i-1}.",
                    "claim": f"Invariant {i} guarantees monotonic log commitment across leader transitions.",
                    "probe": f"How does invariant {i} guarantee monotonic commitment when leader {i} crashes?",
                    "transfer_probe": f"In a {2*i+1}-node cluster with asymmetric links, how does invariant {i} behave?",
                    "rubric": [
                        f"Explains pigeonhole overlap for stage {i} majorities.",
                        f"Concludes leader {i} must witness committed entries from term {i-1}.",
                    ],
                    "edges": {
                        "requires": [f"step-{i-1}"] if i > 1 else [],
                        "contrasts_with": ["step-1"] if i > 1 else [],
                        "analogous_to": [],
                    },
                    "mermaid_block": f"flowchart LR\n  A{i}[\"Node {i}\"] --> B{i}[\"Quorum {i}\"]",
                })

            raft_dag_file = tmp_root / "raft-dag.json"
            raft_dag_file.write_text(
                json.dumps(
                    {
                        "slug": "consensus-raft",
                        "title": "Raft Distributed Consensus",
                        "domain": "Distributed Systems",
                        "note_target": "04 - Permanent",
                        "goal": "Implement Raft consensus from first principles",
                        "nodes": list(reversed(chain_nodes)),  # Purposely reversed to test Kahn's sort!
                    }
                ),
                encoding="utf-8",
            )
            vd_res = cmd_validate_dag(store, argparse.Namespace(file=str(raft_dag_file), json=None, topic=None, allow_stem_overlap=False, dry_run=False, replace=False, extend=False))
            check(vd_res["ok"] is True, "validate-dag succeeds on valid 8-node DAG", "dag")
            check(
                vd_res["topological_order"] == [f"step-{i}" for i in range(1, 9)],
                "Kahn's O(V+E) topological sort orders step-1..step-8 accurately from reversed input",
                "dag",
            )

            # OPT-02 Binary-Search Frontier Probe on 8-node chain (max_probes <= ceil(log2 8) + 2 = 5)
            fp1 = cmd_next(store, argparse.Namespace(topic="consensus-raft", frontier_of="step-8", due=False, interleave=False))
            check(fp1["status"] == "probing", "Initial frontier probe status is 'probing'", "dag")
            check(fp1["probe_bounds"] == [0, 7], "Initial probe_bounds == [0, 7]", "dag")
            check(fp1["candidate_node"]["id"] == "step-4", "Midpoint of [0..7] is index 3 (step-4)", "dag")

            # Pass step-4 -> credits step-1..step-4, bounds become [4, 7], next candidate step-6 (index 5)
            pr1 = cmd_probe(store, argparse.Namespace(topic="consensus-raft", node="step-4", result="pass", target="step-8"))
            check(set(pr1["credited_nodes"]) == {"step-1", "step-2", "step-3", "step-4"}, "Passing step-4 credits step-1..step-4", "dag")
            check(pr1["probe_bounds"] == [4, 7], "Bounds narrow to [4, 7]", "dag")
            check(pr1["candidate_node"]["id"] == "step-6", "Next midpoint is step-6", "dag")

            # Fail step-6 -> bounds become [4, 4], next candidate step-5 (index 4)
            pr2 = cmd_probe(store, argparse.Namespace(topic="consensus-raft", node="step-6", result="fail", target="step-8"))
            check(pr2["probe_bounds"] == [4, 4], "Bounds narrow to [4, 4]", "dag")
            check(pr2["candidate_node"]["id"] == "step-5", "Next midpoint is step-5", "dag")

            # Fail step-5 -> bounds become [4, 3] (low > high -> bracketed! floor=step-4, ceiling=step-5)
            pr3 = cmd_probe(store, argparse.Namespace(topic="consensus-raft", node="step-5", result="fail", target="step-8"))
            check(pr3["bracketed"] is True, "Frontier is bracketed after 3 probes (<= ceil(log2 8)+2)", "dag")
            check(pr3["status"] == "frontier_found", "Frontier status == 'frontier_found'", "dag")
            check(pr3["floor_node"] == "step-4", "Floor node is step-4", "dag")
            check(pr3["ceiling_node"] == "step-5", "Ceiling node is step-5", "dag")
            check(pr3["teach_from"] == "step-5", "Teach plan anchored at step-5", "dag")
            check(pr3["probes_taken"] == 3 and pr3["probes_taken"] <= pr3["max_probes"], "Probe count within logarithmic bound", "dag")

            # Verify prerequisite propagation (weight=0.5) occurred on step-1..step-3
            t_loaded = store.load_topic("consensus-raft")
            by_id_loaded = {n["id"]: n for n in t_loaded["nodes"]}
            check(by_id_loaded["step-3"].get("implicit_credit") == 0.5, "Prerequisite propagation recorded weight=0.5 on step-3", "dag")

            # ------------------------------------------------------------------
            # 5. FSRS-4.5 Analytical Equations, Slip Floor & Dose Caps
            # ------------------------------------------------------------------
            for g_idx, expected_s0 in enumerate(DEFAULT_W[:4], start=1):
                s0_calc = FSRSEngine.init_stability(g_idx)
                check(abs(s0_calc - expected_s0) < 1e-6, f"S0({g_idx}) == {expected_s0}", "fsrs")
                d0_calc = FSRSEngine.init_difficulty(g_idx)
                expected_d0 = clamp_num(DEFAULT_W[4] - (g_idx - 3) * DEFAULT_W[5], 1.0, 10.0)
                check(abs(d0_calc - expected_d0) < 1e-6, f"D0({g_idx}) == {expected_d0:.4f}", "fsrs")

            # Power-law retrievability R(t=S, S) == 0.90 exactly because FACTOR = 19/81 and DECAY = -0.5
            for s_test in (1.0, 3.7145, 10.0, 45.0, 120.0):
                r_at_s = FSRSEngine.retrievability(s_test, s_test)
                check(abs(r_at_s - 0.90) < 1e-9, f"R(t=S={s_test}, S) == 0.90 exactly", "fsrs")
                r_at_0 = FSRSEngine.retrievability(0.0, s_test)
                check(abs(r_at_0 - 1.0) < 1e-9, f"R(0, {s_test}) == 1.0", "fsrs")

            # Optimal interval at R_req = 0.90 and multiplier = 1.0 equals round(S)
            for s_ivl in (2.4, 3.7145, 13.8206, 30.0, 100.0):
                ivl_calc = FSRSEngine.optimal_interval(s_ivl, 0.90, 1.0)
                check(ivl_calc == round(s_ivl), f"optimal_interval({s_ivl}, 0.90) == {round(s_ivl)}", "fsrs")

            # Stability transitions: Recall (G=2,3,4) increases S; Lapse (G=1) decreases or caps S
            st_init, _, _ = FSRSEngine.apply_rating(FSRSState(), 3, date(2026, 10, 18))
            check(st_init.s == 3.7145 and st_init.d == 5.1618 and st_init.interval == 4, "Initial Good encode state", "fsrs")

            st_hard, _, _ = FSRSEngine.apply_rating(st_init, 2, date(2026, 10, 22))
            st_good, _, _ = FSRSEngine.apply_rating(st_init, 3, date(2026, 10, 22))
            st_easy, _, _ = FSRSEngine.apply_rating(st_init, 4, date(2026, 10, 22))
            check(st_init.s < st_hard.s < st_good.s < st_easy.s, "Recall stability strictly monotonic in rating G (2 < 3 < 4)", "fsrs")
            check(st_hard.d > st_good.d > st_easy.d, "Next difficulty strictly monotonic inverse in rating G", "fsrs")

            # Lapse & Post-Lapse Relearning Dose Caps (c1=2d, c2=6d)
            st_lapsed, trans_l, _ = FSRSEngine.apply_rating(st_good, 1, date(2026, 11, 2), is_threshold=False)
            check(st_lapsed.s <= st_good.s, "Lapse never increases stability", "fsrs")
            check(st_lapsed.lapses == 1, "Lapse increments lapses counter", "fsrs")
            check(st_lapsed.relearn_step == 2, "Lapse sets relearn_step=2 on standard node", "fsrs")
            check(st_lapsed.interval == 1, "Lapse interval capped at 1 day", "fsrs")

            # First post-lapse recall -> interval capped at c1 = 2 days
            st_rel1, trans_r1, _ = FSRSEngine.apply_rating(st_lapsed, 4, date(2026, 11, 3))
            check(st_rel1.interval <= 2 and trans_r1["dose_capped"] is True, "First post-lapse recall interval capped at c1=2 days", "fsrs")
            check(st_rel1.relearn_step == 1, "relearn_step decremented to 1", "fsrs")

            # Second post-lapse recall -> interval capped at c2 = 6 days
            st_rel2, trans_r2, _ = FSRSEngine.apply_rating(st_rel1, 4, date(2026, 11, 5))
            check(st_rel2.interval <= 6 and trans_r2["dose_capped"] is True, "Second post-lapse recall interval capped at c2=6 days", "fsrs")
            check(st_rel2.relearn_step == 0, "relearn_step decremented to 0 after second post-lapse recall", "fsrs")

            # Procedure node execution slip floor: G=1 with error_class="slip" on procedure node -> floored to G=2!
            st_slip, _, eff_g_slip = FSRSEngine.apply_rating(
                st_good, 1, date(2026, 11, 2), node_kind="procedure", error_class="slip"
            )
            check(eff_g_slip == 2, "Procedure node with error_class='slip' floors G=1 to G=2 (hard/partial)", "fsrs")
            check(st_slip.lapses == st_good.lapses, "Procedure slip does not increment memory lapses", "fsrs")

            # ------------------------------------------------------------------
            # 6. StashEngine, Claim-Check SHA-256 & Receipt Validation
            # ------------------------------------------------------------------
            stash_res = cmd_stash(
                store,
                argparse.Namespace(
                    action="add",
                    file=None,
                    json=json.dumps({
                        "topic": "consensus-raft",
                        "node": "step-5",
                        "production": "Pigeonhole overlap guarantees stage 5 majorities intersect so leader 5 sees term 4 commits.",
                        "confidence": 4,
                        "kind": "encode",
                    }),
                ),
            )
            check(stash_res["ok"] is True and stash_res["pending"] == 1, "stash add persists record", "stash_receipt")
            sid_5 = stash_res["sid"]
            sha_5 = stash_res["stash_sha256"]

            # Zero-context export-assessor check
            env_5 = cmd_stash(store, argparse.Namespace(action="export-assessor", sid=sid_5, out=None))
            expected_env_keys = {
                "sid", "stash_sha256", "topic", "node", "kind", "event_kind",
                "node_kind", "claim", "probe", "rubric", "production",
                "produced", "production_clipped", "confidence",
            }
            check(set(env_5.keys()) == expected_env_keys, "export-assessor emits exact zero-context key whitelist", "stash_receipt")
            for forbidden_k in ("fsrs", "s", "d", "due", "unconditional_truth", "motivated_discovery", "gold_grade"):
                check(forbidden_k not in env_5, f"export-assessor strips {forbidden_k}", "stash_receipt")

            # Tampered stash_sha256 in receipt -> Exit Code 1 & stash untouched
            check_raises(
                lambda: cmd_receipt(
                    store,
                    argparse.Namespace(
                        file=None,
                        json=json.dumps({
                            "sid": sid_5,
                            "stash_sha256": "0" * 64,
                            "grade": "recalled",
                            "rating": "good",
                            "score": 3,
                        }),
                    ),
                ),
                ValidationError,
                1,
                "Forged/mismatched stash_sha256 rejected with ValidationError (Exit Code 1)",
                "stash_receipt",
            )
            check(len(store.read_jsonl("stash.jsonl")) == 1, "Stash untouched after rejected receipt", "stash_receipt")

            # produced: false with score >= 3 -> Exit Code 1
            for bad_score, bad_rating in ((3, "good"), (4, "easy")):
                check_raises(
                    lambda sc=bad_score, rt=bad_rating: cmd_receipt(
                        store,
                        argparse.Namespace(
                            file=None,
                            json=json.dumps({
                                "sid": sid_5,
                                "stash_sha256": sha_5,
                                "produced": False,
                                "score": sc,
                                "rating": rt,
                                "grade": "recalled",
                            }),
                        ),
                    ),
                    ValidationError,
                    1,
                    f"produced: false with score={bad_score} ({bad_rating}) rejected with ValidationError (Exit Code 1)",
                    "stash_receipt",
                )

            # Valid receipt settlement & idempotent duplicate retry
            rec_ok = cmd_receipt(
                store,
                argparse.Namespace(
                    file=None,
                    json=json.dumps({
                        "sid": sid_5,
                        "stash_sha256": sha_5,
                        "grade": "recalled",
                        "rating": "good",
                        "score": 3,
                        "criteria_met": [True, True],
                        "rationale": "Both rubric criteria satisfied.",
                    }),
                ),
            )
            check(rec_ok["ok"] is True and rec_ok["results"][0]["applied"] is True, "Valid receipt settles cleanly", "stash_receipt")
            check(len(store.read_jsonl("stash.jsonl")) == 0, "Settled sid drained from stash.jsonl", "stash_receipt")

            # Idempotent retry of same sid
            rec_dup = cmd_receipt(
                store,
                argparse.Namespace(
                    file=None,
                    json=json.dumps({
                        "sid": sid_5,
                        "stash_sha256": sha_5,
                        "grade": "recalled",
                        "rating": "good",
                        "score": 3,
                    }),
                ),
            )
            check(
                rec_dup["ok"] is True and rec_dup["results"][0]["idempotent_noop"] is True,
                "Duplicate sid receipt retry is an idempotent no-op (Exit Code 0)",
                "stash_receipt",
            )

            # Test stash pop & clear
            s_tmp = cmd_stash(
                store,
                argparse.Namespace(
                    action="add",
                    file=None,
                    json=json.dumps({"topic": "consensus-raft", "node": "step-6", "production": "Draft answer"}),
                ),
            )
            pop_res = cmd_stash(store, argparse.Namespace(action="pop", sid=s_tmp["sid"]))
            check(pop_res["ok"] is True and pop_res["pending"] == 0, "stash pop removes entry", "stash_receipt")

            # ------------------------------------------------------------------
            # 7. ASTEval (`verify-expr`, OPT-03 Cached Vector & 5-Slip Detection)
            # ------------------------------------------------------------------
            equiv_pairs = [
                (r"\frac{n(n-1)}{2}", "0.5 * n * (n - 1)", "n"),
                (r"\sqrt{x^2 + y^2}", "(x**2 + y**2)**0.5", "x,y"),
                (r"2\sin(x)\cos(x)", "sin(2*x)", "x"),
                (r"\ln(e^{2x})", "2*x", "x"),
                ("comb(n, 2)", "n*(n-1)/2", "n"),
                ("perm(n, 2)", "n*(n-1)", "n"),
                ("factorial(5)", "120", None),
                ("gcd(48, 18)", "6", None),
                ("(x + 1)(x - 1)", "x^2 - 1", "x"),
            ]
            for exp_e, act_e, v_str in equiv_pairs:
                rep = cmd_verify_expr(store, argparse.Namespace(expected=exp_e, actual=act_e, vars=v_str))
                check(rep["equivalent"] is True, f"verify-expr equivalence: {exp_e} == {act_e}", "asteval")
                check(rep["slip_candidate"] is False, f"Equivalent expr has slip_candidate=False: {exp_e}", "asteval")

            # 5 Structural Slips Detection
            slip_cases = [
                ("n*(n-1)/2", "n*(n-1)/2 + 1", "off_by_one_plus"),
                ("n*(n-1)/2", "n*(n-1)/2 - 1", "off_by_one_minus"),
                ("2*x + 4", "x + 2", "missing_factor_2"),
                ("x^2 + 3*x", "2*(x^2 + 3*x)", "extra_factor_2"),
                ("x^2 - 5*x", "5*x - x^2", "sign_flip"),
            ]
            for exp_s, act_s, expected_slip_kind in slip_cases:
                rep_s = cmd_verify_expr(store, argparse.Namespace(expected=exp_s, actual=act_s, vars=None))
                check(rep_s["equivalent"] is False, f"Slip {expected_slip_kind} is not equivalent", "asteval")
                check(rep_s["slip_candidate"] is True, f"Slip {expected_slip_kind} sets slip_candidate=True", "asteval")
                check(rep_s["slip_kind"] == expected_slip_kind, f"Diagnosed slip_kind == {expected_slip_kind}", "asteval")
                check(rep_s["error_class_hint"] == "slip", f"Slip error_class_hint == 'slip' for {expected_slip_kind}", "asteval")

            # Conceptual non-slip mismatch
            rep_conc = cmd_verify_expr(store, argparse.Namespace(expected="n*(n-1)/2", actual="n^3 + 7", vars="n"))
            check(rep_conc["equivalent"] is False and rep_conc["slip_candidate"] is False, "Conceptual wrong formula is not a slip", "asteval")
            check(rep_conc["error_class_hint"] == "conceptual", "Conceptual wrong formula hints 'conceptual'", "asteval")

            # DoS & Domain Guards on verify-expr (OPT-03)
            dos_expressions = [
                "2**10000",
                "10**7**20",
                "factorial(171)",
                "factorial(-1)",
                "comb(200, 5)",
                "perm(180, 2)",
                "exp(710)",
                "gcd(10**19, 5)",
                "__import__('os').system('echo pwn')",
                "(lambda x: x)(1)",
                "[x for x in range(10)]",
                "x.__class__",
                "+".join(["x"] * 260),  # > 256 AST nodes
                "(" * 30 + "x" + ")" * 30,
            ]
            # Wait: parentheses don't add AST nodes in Python, nested unary/binary ops do:
            deep_expr = " + ".join(["1"] * 30)
            for bad_expr in dos_expressions[:-1] + [deep_expr]:
                check_raises(
                    lambda b=bad_expr: cmd_verify_expr(store, argparse.Namespace(expected="x", actual=b, vars="x")),
                    ValidationError,
                    1,
                    f"ASTEval rejects unsafe/DoS expression {bad_expr[:32]!r} with ValidationError (1)",
                    "asteval",
                )

            # ------------------------------------------------------------------
            # 8. MDCompiler (`synthesize`), SEC-YAML-01, OCC & `sync-sr` Bridge
            # ------------------------------------------------------------------
            synth_res = cmd_synthesize(store, argparse.Namespace(topic="consensus-raft", all_nodes=False))
            check(synth_res["ok"] is True, "cmd_synthesize succeeds", "md_sync")
            check(synth_res["compiled_notes_count"] == 5, "5 credited nodes (step-1..step-5) compiled to Markdown", "md_sync")

            moc_file = test_vault / "00 - Maps of Content" / "Raft Distributed Consensus MoC.md"
            check(moc_file.is_file(), "Topic MoC.md created in 00 - Maps of Content/", "md_sync")
            moc_text = moc_file.read_text(encoding="utf-8")
            check("flowchart TD" in moc_text and "✅" in moc_text and "🔒" in moc_text, "MoC contains Mermaid DAG and mastery badges", "md_sync")

            note5_file = test_vault / "04 - Permanent" / "Consensus Step 5.md"
            check(note5_file.is_file(), "Compiled note exists in 04 - Permanent/", "md_sync")
            note5_text = note5_file.read_text(encoding="utf-8")

            # Verify all 5 epistemological blocks & unquoted sr-due
            for req_block in (
                "> [!important] Unconditional Truth",
                "## Motivated Discovery",
                "> [!quote] Learner's Own Words",
                "## Visual Model",
                "> [!warning] Misconceptions & Traps Overcome",
                "sr-due: 2026-10-22",
                "sr-interval: 4",
                "sr-ease: 221",
            ):
                check(req_block in note5_text, f"Compiled note contains {req_block!r}", "md_sync")

            # SEC-YAML-01: Add custom user YAML keys (including block scalar and wikilink) and custom outer prose
            sp_orig, pr_orig, rb_orig = MDCompiler.parse_frontmatter_spans(note5_text)
            custom_yaml_inject = (
                '---\n'
                'up: "[[Distributed Systems MoC]]"\n'
                'cssclasses:\n'
                '  - zettel-permanent\n'
                '  - math-heavy\n'
                'custom_block: |\n'
                '  line one of user block\n'
                '  line two of user block\n'
                + note5_text[4:].replace("tags:\n", "tags:\n  - user/custom-tag\n", 1)
            )
            custom_full = custom_yaml_inject + "\nMy custom personal Zettelkasten note at the bottom!\n"
            note5_file.write_text(custom_full, encoding="utf-8")

            # Re-synthesize and verify byte-for-byte preservation of user YAML spans, merged tags, and outer prose
            cmd_synthesize(store, argparse.Namespace(topic="consensus-raft", all_nodes=False))
            re_text = note5_file.read_text(encoding="utf-8")
            check('up: "[[Distributed Systems MoC]]"' in re_text, "Custom user wikilink key preserved verbatim", "md_sync")
            check("  - zettel-permanent\n  - math-heavy" in re_text, "Custom user list span preserved verbatim", "md_sync")
            check("  line one of user block\n  line two of user block" in re_text, "Custom user block scalar preserved verbatim", "md_sync")
            check("  - user/custom-tag" in re_text and "  - review" in re_text, "User tags and Mnemosyne tags additively merged", "md_sync")
            check("My custom personal Zettelkasten note at the bottom!" in re_text, "Outer prose outside managed markers preserved", "md_sync")

            # OPT-01 Fast-Path: Unchanged notes are skipped in O(1) via os.stat()
            sr_fast = cmd_sync_sr(store, argparse.Namespace(topic="consensus-raft"))
            check(sr_fast["fast_skipped"] == 5 and sr_fast["reconciled_count"] == 0, "OPT-01 stat() fast-path skips all 5 unchanged notes", "md_sync")

            # Reverse sync-sr: Simulate an external review in Obsidian SR plugin (sr-due changed, sr-ease increased by +10 -> Easy G=4)
            mod_sr_text = re_text.replace("sr-due: 2026-10-22", "sr-due: 2026-10-30").replace("sr-interval: 4", "sr-interval: 12").replace("sr-ease: 221", "sr-ease: 231")
            note5_file.write_text(mod_sr_text, encoding="utf-8")

            sr_reconcile = cmd_sync_sr(store, argparse.Namespace(topic="consensus-raft"))
            check(sr_reconcile["reconciled_count"] == 1, "sync-sr detects and reconciles external Obsidian SR review", "md_sync")
            rec_item = sr_reconcile["reconciled"][0]
            check(rec_item["node"] == "step-5" and rec_item["inferred_score"] == 4 and rec_item["inferred_rating"] == "easy", "Reverse SR math infers G=4 (easy) from delta_ease=+10", "md_sync")

            # Verify receipt was logged with source="obsidian-sr" and excluded from blind retention/refit
            ret_check = cmd_retention(store, argparse.Namespace(topic="consensus-raft"))
            check(ret_check["obsidian_sr_reviews_excluded"] == 1, "obsidian-sr receipt excluded from blind retention metrics", "md_sync")

            # OCC Conflict Snapshot: User manually edits INSIDE <!-- mnemosyne:start --> ... <!-- mnemosyne:end -->
            curr_note5 = note5_file.read_text(encoding="utf-8")
            tampered_inner = curr_note5.replace("## Motivated Discovery", "## Motivated Discovery\nUSER MANUAL INNER EDIT!")
            note5_file.write_text(tampered_inner, encoding="utf-8")
            synth_occ = cmd_synthesize(store, argparse.Namespace(topic="consensus-raft", all_nodes=False))
            check(len(synth_occ["conflicts"]) == 1, "OCC detects inner managed-block edit and creates conflict snapshot", "md_sync")
            conflict_rel = synth_occ["conflicts"][0]
            conflict_abs = test_vault / conflict_rel
            check(conflict_abs.is_file() and "USER MANUAL INNER EDIT!" in conflict_abs.read_text(encoding="utf-8"), "Conflict snapshot preserves user's manual inner edit", "md_sync")

            # Corrupted markers / malformed frontmatter on existing file -> Exit Code 3 without clobbering
            broken_marker_text = note5_file.read_text(encoding="utf-8").replace(_MANAGED_END, "<!-- broken marker -->")
            note5_file.write_text(broken_marker_text, encoding="utf-8")
            check_raises(
                lambda: cmd_synthesize(store, argparse.Namespace(topic="consensus-raft", all_nodes=False)),
                ConcurrencyOrCorruptionError,
                3,
                "Missing <!-- mnemosyne:end --> marker raises ConcurrencyOrCorruptionError (Exit Code 3)",
                "md_sync",
            )
            check(
                note5_file.read_text(encoding="utf-8") == broken_marker_text,
                "Corrupted file is never clobbered on Exit Code 3",
                "md_sync",
            )
            # Restore valid note
            note5_file.unlink()
            cmd_synthesize(store, argparse.Namespace(topic="consensus-raft", all_nodes=False))

            # Full Zettelkasten Graduation: Fleeting (score <= 2) -> Permanent (score >= 3) with user prose migration
            st6_res = cmd_stash(
                store,
                argparse.Namespace(
                    action="add",
                    file=None,
                    json=json.dumps({
                        "topic": "consensus-raft",
                        "node": "step-6",
                        "production": "Partial attempt at step 6 mechanism without full invariant.",
                        "confidence": 2,
                        "kind": "encode",
                    }),
                ),
            )
            sid6_fl = st6_res["sid"]
            sha6_fl = st6_res["stash_sha256"]
            cmd_receipt(
                store,
                argparse.Namespace(
                    positional_file=None,
                    file=None,
                    json=json.dumps({
                        "sid": sid6_fl,
                        "stash_sha256": sha6_fl,
                        "topic": "consensus-raft",
                        "node": "step-6",
                        "grade": "partial",
                        "rating": "hard",
                        "score": 2,
                        "produced": True,
                        "confidence": 2,
                        "production": "Partial attempt at step 6 mechanism without full invariant.",
                        "rationale": "Partial recall (score 2) -> stays in learning/fleeting stage.",
                    }),
                ),
            )
            synth_fl = cmd_synthesize(store, argparse.Namespace(topic="consensus-raft", all_nodes=False))
            fleeting6_file = test_vault / "05 - Fleeting" / "mnemosyne" / "Raft Distributed Consensus" / "Consensus Step 6.md"
            perm6_file = test_vault / "04 - Permanent" / "Consensus Step 6.md"
            check(fleeting6_file.is_file(), "Unmastered node (score <= 2) compiles to 05 - Fleeting/mnemosyne/<Topic>/<Node>.md", "md_sync")
            check(not perm6_file.is_file(), "Unmastered node does not prematurely appear in 04 - Permanent/", "md_sync")
            fl6_text = fleeting6_file.read_text(encoding="utf-8")
            check('status: "fleeting"' in fl6_text, "Fleeting note has status: 'fleeting' in YAML frontmatter", "md_sync")
            moc_fl_text = moc_file.read_text(encoding="utf-8")
            check("05 - Fleeting/mnemosyne/Raft Distributed Consensus/Consensus Step 6" in moc_fl_text, "MoC links 🔄 fleeting node to its fleeting note", "md_sync")

            # User writes custom YAML and personal prose in the fleeting draft before graduation
            fl6_customized = (
                '---\n'
                'fleeting_origin: "study-session-oct-18"\n'
                + fl6_text[4:]
                + "\nUser fleeting margin note that MUST survive graduation to Permanent!\n"
            )
            fleeting6_file.write_text(fl6_customized, encoding="utf-8")

            # Now learner masters step-6 (score = 3, rating = good) -> graduates to 04 - Permanent/
            st6_grad = cmd_stash(
                store,
                argparse.Namespace(
                    action="add",
                    file=None,
                    json=json.dumps({
                        "topic": "consensus-raft",
                        "node": "step-6",
                        "production": "Complete derivation of step 6 consensus safety and quorum intersection.",
                        "confidence": 4,
                        "kind": "encode",
                    }),
                ),
            )
            cmd_receipt(
                store,
                argparse.Namespace(
                    positional_file=None,
                    file=None,
                    json=json.dumps({
                        "sid": st6_grad["sid"],
                        "stash_sha256": st6_grad["stash_sha256"],
                        "topic": "consensus-raft",
                        "node": "step-6",
                        "grade": "recalled",
                        "rating": "good",
                        "score": 3,
                        "produced": True,
                        "confidence": 4,
                        "production": "Complete derivation of step 6 consensus safety and quorum intersection.",
                        "rationale": "Mastered all rubric criteria -> graduates to permanent.",
                    }),
                ),
            )
            cmd_synthesize(store, argparse.Namespace(topic="consensus-raft", all_nodes=False))
            check(perm6_file.is_file(), "Graduated node (score >= 3) compiled into 04 - Permanent/", "md_sync")
            check(not fleeting6_file.exists(), "Obsolete fleeting draft unlinked upon graduation to prevent duplicates", "md_sync")
            perm6_text = perm6_file.read_text(encoding="utf-8")
            check('status: "permanent"' in perm6_text, "Graduated note has status: 'permanent'", "md_sync")
            check('fleeting_origin: "study-session-oct-18"' in perm6_text, "Custom YAML property migrated from fleeting draft to permanent note", "md_sync")
            check("User fleeting margin note that MUST survive graduation to Permanent!" in perm6_text, "User prose outside markers migrated from fleeting draft to permanent note", "md_sync")

            # Inbox CLI (inbox add / inbox list) & status.inbox_count
            inb_add = cmd_inbox(
                store,
                argparse.Namespace(
                    action="add",
                    title="Raft Joint Consensus Edge Case",
                    text="Investigate why C_old,new is needed during membership changes.",
                ),
            )
            check(inb_add["ok"] is True and inb_add["path"] == "05 - Fleeting/mnemosyne/inbox/Raft Joint Consensus Edge Case.md", "inbox add creates note in 05 - Fleeting/mnemosyne/inbox/", "cli_extras")
            inb_list = cmd_inbox(store, argparse.Namespace(action="list", title=None, text=None))
            check(inb_list["ok"] is True and inb_list["count"] == 1 and inb_list["items"][0]["title"] == "Raft Joint Consensus Edge Case", "inbox list returns created fleeting inbox note", "cli_extras")
            st_with_inbox = cmd_status(store, argparse.Namespace(topic=None))
            check(st_with_inbox.get("inbox_count") == 1, "cmd_status reports inbox_count == 1", "cli_extras")

            # ------------------------------------------------------------------
            # 9. Coordinate-Search `refit`, `doctor --repair`, `artifact`, `report`
            # ------------------------------------------------------------------
            # Refit with < 30 blind reviews fails cleanly without --force
            refit_under = cmd_refit(store, argparse.Namespace(force=False))
            check(refit_under["ok"] is False and refit_under["required_min"] == 30, "refit rejects < 30 blind reviews without --force", "refit_doctor")

            # Generate 32 synthetic blind review receipts across days and run coordinate-search refit
            synth_receipts = store.read_jsonl("receipts", "consensus-raft.jsonl")
            for k in range(32):
                r_day = (date(2026, 10, 20) + timedelta(days=k)).isoformat()
                synth_receipts.append({
                    "id": f"rc-bench-{k:03d}",
                    "sid": f"st-bench-{k:03d}",
                    "stash_sha256": "a" * 64,
                    "ts": r_day,
                    "captured_at": f"{r_day}T12:00:00Z",
                    "settled_at": f"{r_day}T12:05:00Z",
                    "source": "blind-assessor",
                    "topic": "consensus-raft",
                    "node": f"step-{(k % 5) + 1}",
                    "kind": "review",
                    "node_kind": "concept",
                    "grade": "recalled" if (k % 7 != 0) else "lapsed",
                    "rating": "good" if (k % 7 != 0) else "again",
                    "score": 3 if (k % 7 != 0) else 1,
                    "produced": True,
                    "confidence": 3,
                    "fsrs_transition": {
                        "s_before": 4.0 + (k % 5),
                        "s_after": 8.0 + (k % 5),
                        "d_before": 5.0,
                        "d_after": 5.0,
                        "retrievability": 0.88,
                        "interval_days": 5,
                        "dose_capped": False,
                    },
                })
            store.write_jsonl(synth_receipts, "receipts", "consensus-raft.jsonl")

            refit_ok = cmd_refit(store, argparse.Namespace(force=False))
            check(refit_ok["ok"] is True and refit_ok["n_blind_reviews"] >= 32, "refit succeeds with >= 30 blind reviews", "refit_doctor")
            check(len(refit_ok["fsrs_params"]) == 17, "refit outputs 17 FSRS-4.5 weights", "refit_doctor")
            check(refit_ok["loss_after"] <= refit_ok["loss_before"], "refit coordinate search never degrades BCE loss", "refit_doctor")

            # Doctor --repair reconstructs topic FSRS state from append-only receipt log
            doc_res = cmd_doctor(store, argparse.Namespace(repair=True))
            check(doc_res["ok"] is True and "consensus-raft" in doc_res["repaired_topics"], "doctor --repair replays receipts deterministically", "refit_doctor")

            # Artifact registration with CSP enforcement
            bad_html = tmp_root / "bad.html"
            bad_html.write_text("<html><script src='https://cdn.evil.com/x.js'></script></html>", encoding="utf-8")
            check_raises(
                lambda: cmd_artifact(store, argparse.Namespace(action="set", topic="consensus-raft", node="step-1", file=str(bad_html), path=None)),
                ValidationError,
                1,
                "HTML artifact without offline CSP or with external CDN script is rejected",
                "artifact_report",
            )

            good_svg = tmp_root / "quorum.svg"
            good_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>', encoding="utf-8")
            art_set = cmd_artifact(store, argparse.Namespace(action="set", topic="consensus-raft", node="step-1", file=str(good_svg), path=None))
            check(art_set["ok"] is True and art_set["artifact"].startswith("99 - Meta/attachments/viz-step-1-"), "Valid SVG artifact registered in 99 - Meta/attachments/", "artifact_report")

            rep_res = cmd_report(store, argparse.Namespace(topic=None, out=None))
            check(rep_res["ok"] is True and Path(rep_res["report_path"]).is_file(), "HTML dashboard report generated with valid offline CSP", "artifact_report")

            # Additional CLI coverage: model, misconception, experiment, decay, edit-node
            mod_res = cmd_model(store, argparse.Namespace(set=["desired_retention=0.90"]))
            check(mod_res["ok"] is True and abs(mod_res["model"]["desired_retention"] - 0.90) < 1e-6, "cmd_model updates desired_retention", "cli_extras")
            misc_res = cmd_misconception(store, argparse.Namespace(action="add", topic="consensus-raft", node="step-1", description="Confused split vote with leader crash"))
            check(misc_res["ok"] is True and misc_res["total"] >= 1, "cmd_misconception logs misconception", "cli_extras")
            exp_res = cmd_experiment(store, argparse.Namespace(name="interleaved-vs-blocked"))
            check(exp_res["ok"] is True and len(exp_res["experiments"]) == 1, "cmd_experiment registers n-of-1 study", "cli_extras")
            dec_res = cmd_decay(store, argparse.Namespace(days=14))
            check(dec_res["ok"] is True and dec_res["days_ahead"] == 14, "cmd_decay projects retrievability", "cli_extras")
            en_res = cmd_edit_node(store, argparse.Namespace(topic="consensus-raft", node="step-1", file=None, json=json.dumps({"elaboration_question": "Why does split vote require randomized timeouts?"})))
            check(en_res["ok"] is True and "elaboration_question" in en_res["updated_fields"], "cmd_edit_node updates non-schedule fields", "cli_extras")

            # ------------------------------------------------------------------
            # 10. Gold Calibration Set & Latency Gate (< 150ms per command)
            # ------------------------------------------------------------------
            gold_file = gate.repo_root / "gold" / "assessor-gold.jsonl"
            if gold_file.is_file():
                t_cal0 = time.monotonic()
                cal_res = cmd_calibrate(store, argparse.Namespace(gold=str(gold_file), file=None, json=None))
                cal_ms = (time.monotonic() - t_cal0) * 1000.0
                check(cal_res["ok"] is True, "calibrate passes on bundled gold/assessor-gold.jsonl", "calibrate")
                check(cal_res["gold_total"] >= 258, f"Gold set has >= 258 items ({cal_res['gold_total']})", "calibrate")
                check(cal_res["qwk"] >= 0.85, f"Gold self-calibration QWK {cal_res['qwk']} >= 0.85", "calibrate")
                check(cal_res["krippendorff_alpha"] >= 0.80, f"Gold Krippendorff alpha {cal_res['krippendorff_alpha']} >= 0.80", "calibrate")
                check(cal_res["zero_criteria_inflations"] == 0, "0 upward inflations on zero-criteria items", "calibrate")
                check(cal_res["produced_false_violations"] == 0, "0 produced: false violations", "calibrate")
                check(cal_ms < 150.0, f"calibrate executed in {cal_ms:.1f}ms (< 150ms gate)", "latency")

                # Verify per-item structural and pedagogical invariants across all gold items
                raw_gold_lines = [ln.strip() for ln in gold_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
                for idx_g, raw_ln in enumerate(raw_gold_lines):
                    g_obj = json.loads(raw_ln)
                    g_id = g_obj.get("sid") or g_obj.get("id")
                    g_score = g_obj.get("gold_score") or g_obj.get("expected_score") or g_obj.get("score")
                    g_rating = g_obj.get("gold_rating") or g_obj.get("expected_rating") or g_obj.get("rating")
                    g_crit = g_obj.get("criteria_met") if "criteria_met" in g_obj else g_obj.get("criteria_locks")
                    check(
                        bool(g_id)
                        and g_obj.get("node_kind") in ("concept", "procedure", "fact")
                        and g_score in (1, 2, 3, 4)
                        and g_rating in ("again", "hard", "good", "easy")
                        and isinstance(g_crit, list)
                        and len(g_crit) >= 1
                        and (g_obj.get("produced") is True or g_score == 1),
                        f"Gold item #{idx_g + 1} ({g_id}) satisfies schema & rubric invariants",
                        "calibrate_items",
                    )

            # Benchmark p99 CLI operation latency (< 150ms)
            t_op0 = time.monotonic()
            cmd_status(store, argparse.Namespace(topic=None))
            cmd_next(store, argparse.Namespace(topic="consensus-raft", frontier_of=None, due=False, interleave=True))
            cmd_sync_sr(store, argparse.Namespace(topic="consensus-raft"))
            op_ms = (time.monotonic() - t_op0) * 1000.0
            check(op_ms < 150.0, f"Core CLI status+next+sync-sr latency {op_ms:.2f}ms < 150ms", "latency")

    finally:
        if old_today is None:
            os.environ.pop("MNEMOSYNE_TODAY", None)
        else:
            os.environ["MNEMOSYNE_TODAY"] = old_today

    elapsed_s = time.monotonic() - t_start
    check(elapsed_s < 5.0, f"Entire selftest completed in {elapsed_s:.3f}s (< 5.0s gate)", "latency")
    check(assertions >= 350, f"Total assertions {assertions} >= 350 minimum gate", "core")

    return {
        "ok": True,
        "assertions_passed": assertions,
        "elapsed_ms": round(elapsed_s * 1000.0, 2),
        "categories": categories,
        "engine_version": ENGINE_VERSION,
    }


# ==============================================================================
# CLI ARGUMENT PARSER & TOP-LEVEL EXCEPTION-TO-EXIT-CODE MAPPER
# ==============================================================================

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mnemosyne.py",
        description="Mnemosyne Deterministic CLI-First FSRS-4.5 & Zettelkasten Study Engine",
    )
    parser.add_argument("--vault", dest="vault", default=None, help="Override Obsidian Vault root path")
    parser.add_argument("--state-dir", dest="state_dir", default=None, help="Override state ledger directory")

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="Initialize Vault directories and state ledger")

    # validate-dag / add-topic
    for cmd_name in ("validate-dag", "add-topic"):
        p_vd = sub.add_parser(cmd_name, help="Validate and register a curriculum topic DAG JSON")
        p_vd.add_argument("positional_file", nargs="?", default=None, help="Path to topic DAG JSON file")
        p_vd.add_argument("--file", "-f", default=None, help="Path to topic DAG JSON file ('-' for stdin)")
        p_vd.add_argument("--json", "-j", default=None, help="Inline JSON payload")
        p_vd.add_argument("--topic", "-t", default=None, help="Validate existing topic slug")
        p_vd.add_argument("--replace", action="store_true", help="Replace topic while preserving FSRS states and soft-archiving removed nodes")
        p_vd.add_argument("--extend", action="store_true", help="Extend topic while preserving existing FSRS states")
        p_vd.add_argument("--dry-run", action="store_true", help="Validate without saving to state")
        p_vd.add_argument("--allow-stem-overlap", action="store_true", help="Skip strict lexical stem-mirroring check")

    # status / stats / topic-status
    for cmd_name in ("status", "stats", "topic-status"):
        p_st = sub.add_parser(cmd_name, help="Show learner model, topic progress, and due counts")
        p_st.add_argument("--topic", "-t", default=None, help="Filter by topic slug")

    # next / due
    for cmd_name in ("next", "due"):
        p_nx = sub.add_parser(cmd_name, help="Get next due review, unlocked encoding node, or binary-search frontier probe")
        p_nx.add_argument("--topic", "-t", default=None, help="Topic slug")
        p_nx.add_argument("--frontier-of", dest="frontier_of", default=None, help="Target node ID for OPT-02 binary-search frontier probe")
        p_nx.add_argument("--due", action="store_true", default=(cmd_name == "due"), help="Return due review queue only")
        p_nx.add_argument("--interleave", action="store_true", help="Interleave due nodes across topics")

    # probe
    p_pr = sub.add_parser("probe", help="Record binary-search prerequisite frontier probe result (pass|fail)")
    p_pr.add_argument("pos_topic", nargs="?", default=None, help="Topic slug")
    p_pr.add_argument("pos_node", nargs="?", default=None, help="Probed node ID")
    p_pr.add_argument("pos_result", nargs="?", default=None, help="Probe result: pass or fail")
    p_pr.add_argument("--topic", "-t", default=None, help="Topic slug")
    p_pr.add_argument("--node", "-n", default=None, help="Probed node ID")
    p_pr.add_argument("--result", "-r", default=None, help="Probe result: pass or fail")
    p_pr.add_argument("--target", default=None, help="Target node ID being bracketed")

    # unlock
    p_un = sub.add_parser("unlock", help="Unlock eligible nodes whose prerequisites are satisfied")
    p_un.add_argument("pos_topic", nargs="?", default=None, help="Topic slug")
    p_un.add_argument("pos_node", nargs="?", default=None, help="Node ID")
    p_un.add_argument("--topic", "-t", default=None, help="Topic slug")
    p_un.add_argument("--node", "-n", default=None, help="Node ID")
    p_un.add_argument("--force", action="store_true", help="Force unlock even if prerequisites are uncredited")

    # stash
    p_sh = sub.add_parser("stash", help="Manage ungraded learner production stash and zero-context assessor exports")
    p_sh.add_argument("action", nargs="?", default="list", choices=("add", "pop", "list", "clear", "count", "export-assessor"))
    p_sh.add_argument("--file", "-f", default=None, help="Input JSON file ('-' for stdin)")
    p_sh.add_argument("--json", "-j", default=None, help="Inline JSON payload")
    p_sh.add_argument("--sid", default=None, help="Stash transaction ID (sid)")
    p_sh.add_argument("--out", "-o", default=None, help="Output file path for export-assessor")
    p_sh.add_argument("--topic", "-t", default=None, help="Topic slug")
    p_sh.add_argument("--node", "-n", default=None, help="Node ID")
    p_sh.add_argument("--production", default=None, help="Learner production text")
    p_sh.add_argument("--probe", default=None, help="Probe question")
    p_sh.add_argument("--claim", default=None, help="Core claim")
    p_sh.add_argument("--confidence", type=int, default=None, help="Pre-feedback confidence (1..4)")
    p_sh.add_argument("--kind", default="encode", help="Event kind (encode|review|pretest|transfer)")

    # receipt / batch / rate
    for cmd_name in ("receipt", "batch", "rate"):
        p_rc = sub.add_parser(cmd_name, help="Validate and settle blind-assessor receipt(s) atomically")
        p_rc.add_argument("positional_file", nargs="?", default=None, help="Path to receipt JSON file")
        p_rc.add_argument("--file", "-f", default=None, help="Path to receipt JSON file ('-' for stdin)")
        p_rc.add_argument("--json", "-j", default=None, help="Inline JSON payload")
        p_rc.add_argument("--sid", default=None, help="Stash transaction ID")
        p_rc.add_argument("--stash-sha256", dest="stash_sha256", default=None, help="Claim-check SHA-256")
        p_rc.add_argument("--topic", "-t", default=None, help="Topic slug")
        p_rc.add_argument("--node", "-n", default=None, help="Node ID")
        p_rc.add_argument("--rating", default=None, help="FSRS rating (again|hard|good|easy)")
        p_rc.add_argument("--grade", default=None, help="Assessor grade (lapsed|partial|recalled)")
        p_rc.add_argument("--score", type=int, default=None, help="Numeric score (1..4)")
        p_rc.add_argument("--production", default=None, help="Verbatim production")
        p_rc.add_argument("--error-class", dest="error_class", default=None, help="Error class (slip|conceptual)")
        p_rc.add_argument("--confidence", type=int, default=None, help="Pre-feedback confidence (1..4)")
        p_rc.add_argument("--rationale", default=None, help="Grading rationale")

    # sync-sr
    p_sr = sub.add_parser("sync-sr", help="Reconcile external obsidian-spaced-repetition reviews via OPT-01 stat() fast-path")
    p_sr.add_argument("--topic", "-t", default=None, help="Filter by topic slug")

    # synthesize
    p_sy = sub.add_parser("synthesize", help="Compile verified Zettelkasten notes and Topic MoCs with OCC")
    p_sy.add_argument("--topic", "-t", default=None, help="Filter by topic slug")
    p_sy.add_argument("--all-nodes", dest="all_nodes", action="store_true", help="Compile all nodes including uncredited ones")

    # inbox
    p_ib = sub.add_parser("inbox", help="List or add fleeting study notes in 05 - Fleeting/mnemosyne/inbox/")
    p_ib.add_argument("action", nargs="?", default="list", choices=("list", "add"))
    p_ib.add_argument("--title", default=None, help="Note title for inbox add")
    p_ib.add_argument("--text", default=None, help="Note body text for inbox add")

    # artifact
    p_ar = sub.add_parser("artifact", help="Register, list, or clear visual artifacts in 99 - Meta/attachments/")
    p_ar.add_argument("action", nargs="?", default="list", choices=("set", "list", "clear"))
    p_ar.add_argument("--topic", "-t", default=None, help="Topic slug")
    p_ar.add_argument("--node", "-n", default=None, help="Node ID")
    p_ar.add_argument("--file", "-f", default=None, help="Source artifact file path")
    p_ar.add_argument("--path", "-p", default=None, help="Source artifact file path")

    # verify-expr
    p_ve = sub.add_parser("verify-expr", help="Verify mathematical/algebraic equivalence and diagnose slips via restricted AST")
    p_ve.add_argument("--expected", "-e", required=True, help="Expected expression (LaTeX or Python math)")
    p_ve.add_argument("--actual", "-a", required=True, help="Learner's actual expression")
    p_ve.add_argument("--vars", "-v", default=None, help="Comma-separated variable names (e.g. x,y)")

    # retention / adherence
    for cmd_name in ("retention", "adherence"):
        p_rt = sub.add_parser(cmd_name, help="Compute blind-graded retention metrics across interval horizons")
        p_rt.add_argument("--topic", "-t", default=None, help="Filter by topic slug")

    # refit
    p_rf = sub.add_parser("refit", help="Fit FSRS-4.5 parameters via coordinate search on >= 30 blind reviews")
    p_rf.add_argument("--force", action="store_true", help="Force refit below 30 reviews")

    # calibrate / assessor-audit / gold
    for cmd_name in ("calibrate", "assessor-audit", "gold"):
        p_ca = sub.add_parser(cmd_name, help="Validate gold/assessor-gold.jsonl and audit grader QWK, alpha, and leniency bounds")
        p_ca.add_argument("--gold", default=None, help="Path to assessor-gold.jsonl")
        p_ca.add_argument("--file", "-f", default=None, help="Path to assessor verdicts JSON")
        p_ca.add_argument("--json", "-j", default=None, help="Inline assessor verdicts JSON")

    # report
    p_rp = sub.add_parser("report", help="Generate offline CSP-protected HTML analytics dashboard")
    p_rp.add_argument("--topic", "-t", default=None, help="Filter by topic slug")
    p_rp.add_argument("--out", "-o", default=None, help="Custom output HTML file path")

    # doctor
    p_dc = sub.add_parser("doctor", help="Audit ledger integrity and optionally replay receipts (--repair)")
    p_dc.add_argument("--repair", action="store_true", help="Reconstruct topic FSRS states from append-only receipt logs")

    # edit-node, model, misconception, experiment, decay
    p_en = sub.add_parser("edit-node", help="Update non-schedule fields on an existing DAG node")
    p_en.add_argument("--topic", "-t", required=True)
    p_en.add_argument("--node", "-n", required=True)
    p_en.add_argument("--file", "-f", default=None)
    p_en.add_argument("--json", "-j", default=None)

    p_md = sub.add_parser("model", help="Inspect or update learner-model.json settings")
    p_md.add_argument("--set", action="append", default=None, help="key=value setting assignment")

    p_mc = sub.add_parser("misconception", help="List or log learner misconceptions")
    p_mc.add_argument("action", nargs="?", default="list", choices=("list", "add"))
    p_mc.add_argument("--topic", "-t", default=None)
    p_mc.add_argument("--node", "-n", default=None)
    p_mc.add_argument("--description", "-d", default=None)

    p_ex = sub.add_parser("experiment", help="List or register n-of-1 pedagogical experiments")
    p_ex.add_argument("--name", default=None)

    p_dy = sub.add_parser("decay", help="Project memory retrievability decay ahead by N days")
    p_dy.add_argument("--days", type=int, default=7)

    # selftest
    sub.add_parser("selftest", help="Run >= 350 isolated self-test assertions in TemporaryDirectory")

    return parser


COMMAND_DISPATCH: Dict[str, Callable[[StateStore, argparse.Namespace], Any]] = {
    "init": cmd_init,
    "validate-dag": cmd_validate_dag,
    "add-topic": cmd_validate_dag,
    "status": cmd_status,
    "stats": cmd_status,
    "topic-status": cmd_status,
    "next": cmd_next,
    "due": cmd_next,
    "probe": cmd_probe,
    "unlock": cmd_unlock,
    "stash": cmd_stash,
    "receipt": cmd_receipt,
    "batch": cmd_receipt,
    "rate": cmd_receipt,
    "sync-sr": cmd_sync_sr,
    "synthesize": cmd_synthesize,
    "inbox": cmd_inbox,
    "artifact": cmd_artifact,
    "verify-expr": cmd_verify_expr,
    "retention": cmd_retention,
    "adherence": cmd_retention,
    "refit": cmd_refit,
    "calibrate": cmd_calibrate,
    "assessor-audit": cmd_calibrate,
    "gold": cmd_calibrate,
    "report": cmd_report,
    "doctor": cmd_doctor,
    "edit-node": cmd_edit_node,
    "model": cmd_model,
    "misconception": cmd_misconception,
    "experiment": cmd_experiment,
    "decay": cmd_decay,
    "selftest": cmd_selftest,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return 0 if code == 0 else int(ExitCode.VALIDATION_ERROR)

    try:
        if args.command == "selftest":
            # Never touch real Vault during selftest; pass a dummy tempdir gate
            with tempfile.TemporaryDirectory(prefix="mnemosyne_boot_") as boot_tmp:
                boot_gate = VaultGate(vault_override=boot_tmp, state_override=boot_tmp)
                boot_store = StateStore(boot_gate)
                res = cmd_selftest(boot_store, args)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return int(ExitCode.OK)

        gate = VaultGate(vault_override=args.vault, state_override=args.state_dir)
        store = StateStore(gate)
        handler = COMMAND_DISPATCH.get(args.command)
        if handler is None:
            raise ValidationError(f"Unknown command {args.command!r}.")
        result = handler(store, args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return int(ExitCode.OK)

    except MnemosyneError as exc:
        err_payload = exc.to_dict()
        print(json.dumps(err_payload, indent=2, ensure_ascii=False), file=sys.stderr)
        return int(exc.exit_code)
    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": type(exc).__name__,
            "exit_code": int(ExitCode.VALIDATION_ERROR),
            "message": str(exc),
        }
        print(json.dumps(err_payload, indent=2, ensure_ascii=False), file=sys.stderr)
        return int(ExitCode.VALIDATION_ERROR)


if __name__ == "__main__":
    sys.exit(main())
