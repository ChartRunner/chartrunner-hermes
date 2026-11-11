"""Format-v1 ChartRunner memo checks. Same rules as packages/verify (SPEC.md).

A pass means the rows rebuild the root written in the memo. It does not read
Solana, and it does not prove the fills behind a cup were fair.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

SAFE_INT = 2**53 - 1
MAX_BATTLE_LEAVES = 10_000
LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
MEMO_RE = re.compile(r"^chartrunner:v1:([a-z]+):([A-Za-z0-9._-]{1,64}):([0-9a-f]{64}):([1-9][0-9]{0,8})$")
BATTLE_WINDOW_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T(00|04|08|12|16|20)$")

USER_KINDS = ("map", "strategy", "bot", "backtest")
ANCHOR_KINDS = (
    "freeplay",
    "daily",
    "cup",
    "xp",
    "map",
    "strategy",
    "bot",
    "backtest",
    "dailyrun",
    "dailyrace",
    "battle",
)
ONE_COUNT = frozenset(USER_KINDS)

Leaf = dict[str, Any]


@dataclass(frozen=True)
class Memo:
    kind: str
    id: str
    root: str
    count: int

    @property
    def text(self) -> str:
        return f"chartrunner:v1:{self.kind}:{self.id}:{self.root}:{self.count}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def user_hash(user_id: str) -> str:
    return sha256_hex(f"chartrunner:user:{user_id}".encode())


def handle_hash(handle: str) -> str:
    return sha256_hex(f"chartrunner:handle:{handle.lower()}".encode())


def _js_string(value: str) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _js_value(value: Any, field: str) -> str:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return "null" if value is None else ("true" if value is True else "false" if value is False else _js_string(value))
    if isinstance(value, int) and not isinstance(value, bool) and -SAFE_INT <= value <= SAFE_INT:
        return str(value)
    raise ValueError(f"leaf field {field} must be a safe integer, a string, a boolean or null")


def canonical_json(entry: Mapping[str, Any]) -> str:
    if type(entry) is not dict:
        raise ValueError("a row must be a plain JSON object (not an array, null or a class instance)")
    parts = []
    for key in sorted(entry):
        if not isinstance(key, str):
            raise ValueError("leaf field names must be strings")
        parts.append(f"{_js_string(key)}:{_js_value(entry[key], key)}")
    return "{" + ",".join(parts) + "}"


def hash_leaf(canonical: str) -> str:
    return sha256_hex(LEAF_PREFIX + canonical.encode())


def hash_node(left: str, right: str) -> str:
    if not HASH_RE.fullmatch(left) or not HASH_RE.fullmatch(right):
        raise ValueError("invalid hash")
    return sha256_hex(NODE_PREFIX + bytes.fromhex(left) + bytes.fromhex(right))


def prepare_leaves(entries: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    if not entries:
        raise ValueError("cannot commit to zero leaves")
    prepared = []
    for entry in entries:
        text = canonical_json(dict(entry))
        prepared.append((text, hash_leaf(text)))
    prepared.sort(key=lambda item: item[1])
    for index in range(1, len(prepared)):
        if prepared[index][1] == prepared[index - 1][1]:
            raise ValueError("duplicate leaf")
    return prepared


def build_root(sorted_hashes: Sequence[str]) -> str:
    if not sorted_hashes:
        raise ValueError("cannot commit to zero leaves")
    level = [bytes.fromhex(item) for item in sorted_hashes]
    while len(level) > 1:
        nxt: list[bytes] = []
        for index in range(0, len(level), 2):
            left = level[index]
            if index + 1 < len(level):
                nxt.append(hashlib.sha256(NODE_PREFIX + left + level[index + 1]).digest())
            else:
                nxt.append(left)
        level = nxt
    return level[0].hex()


def max_proof_length(count: int) -> int:
    if count <= 1:
        return 0
    return math.ceil(math.log2(count))


def _is_battle_window(value: str) -> bool:
    match = BATTLE_WINDOW_RE.fullmatch(value)
    if not match:
        return False
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if year < 1 or month < 1 or month > 12 or day < 1:
        return False
    leap = (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return day <= days


def kind_rule_violation(kind: str, anchor_id: str, count: int) -> str | None:
    if kind in ONE_COUNT and count != 1:
        return f'Kind "{kind}" anchors a single leaf, so its count must be 1.'
    if kind == "battle":
        if not _is_battle_window(anchor_id):
            return 'A "battle" id must be a 4-hour UTC window YYYY-MM-DDTHH with HH 00, 04, 08, 12, 16 or 20, on a real date.'
        if count > MAX_BATTLE_LEAVES:
            return f"A battle anchor carries at most {MAX_BATTLE_LEAVES} leaves."
    return None


def parse_memo(text: str) -> Memo | None:
    match = MEMO_RE.fullmatch(text)
    if not match or match.group(1) not in ANCHOR_KINDS:
        return None
    count = int(match.group(4))
    if kind_rule_violation(match.group(1), match.group(2), count) is not None:
        return None
    return Memo(match.group(1), match.group(2), match.group(3), count)


def verify_against_memo(
    memo_text: str,
    *,
    rows: Sequence[Mapping[str, Any]] | None = None,
    leaf: str | Mapping[str, Any] | None = None,
    proof: Sequence[Mapping[str, Any]] | None = None,
    expect_kind: str | None = None,
    expect_id: str | None = None,
) -> dict[str, Any]:
    """Check rows, or one leaf plus a proof, against a chartrunner:v1 memo. Never raises."""
    memo = parse_memo(memo_text) if isinstance(memo_text, str) else None
    if memo is None:
        return {"ok": False, "reason": "memo_malformed", "message": "The text is not a chartrunner:v1 memo."}
    if expect_kind is not None and expect_kind != memo.kind:
        return _fail("memo_subject_mismatch", f'Memo is for kind "{memo.kind}", expected "{expect_kind}".', memo)
    if expect_id is not None and expect_id != memo.id:
        return _fail("memo_subject_mismatch", f'Memo is for id "{memo.id}", expected "{expect_id}".', memo)

    if rows is not None:
        if not isinstance(rows, (list, tuple)) or len(rows) == 0:
            return _fail("rows_invalid", "rows must be a non-empty array.", memo)
        try:
            prepared = prepare_leaves(rows)
            root = build_root([item[1] for item in prepared])
        except (TypeError, ValueError) as exc:
            return _fail("rows_invalid", str(exc), memo)
        if root != memo.root:
            return _fail("root_mismatch", "The rows do not rebuild the root committed in the memo.", memo, root)
        if len(prepared) != memo.count:
            return _fail("count_mismatch", f"The memo commits {memo.count} rows, got {len(prepared)}.", memo, root)
        return {"ok": True, "mode": "rows", "memo": _memo_dict(memo), "root": root}

    if leaf is not None and proof is not None:
        try:
            canonical = leaf if isinstance(leaf, str) else canonical_json(leaf)
        except (TypeError, ValueError) as exc:
            return _fail("leaf_invalid", str(exc), memo)
        if not canonical:
            return _fail("leaf_invalid", "leaf must be canonical JSON text or a row.", memo)
        if not isinstance(proof, (list, tuple)):
            return _fail("proof_invalid", "A proof step is malformed.", memo)
        steps: list[tuple[str, str]] = []
        for step in proof:
            if not isinstance(step, Mapping):
                return _fail("proof_invalid", "A proof step is malformed.", memo)
            side = step.get("side")
            digest = step.get("hash")
            if side not in ("L", "R") or not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
                return _fail("proof_invalid", "A proof step is malformed.", memo)
            steps.append((side, digest))
        if len(steps) > max_proof_length(memo.count):
            return _fail("proof_invalid", "The proof is longer than a tree with this many rows allows.", memo)
        try:
            computed = hash_leaf(canonical)
            for side, digest in steps:
                computed = hash_node(digest, computed) if side == "L" else hash_node(computed, digest)
        except ValueError as exc:
            return _fail("proof_invalid", str(exc), memo)
        if computed != memo.root:
            return _fail("root_mismatch", "The leaf and proof do not lead to the root committed in the memo.", memo, computed)
        return {"ok": True, "mode": "proof", "memo": _memo_dict(memo), "root": computed}

    return _fail("input_invalid", "Provide either rows, or leaf and proof.", memo)


def cup_leaf(cup_id: str, standing: Mapping[str, Any]) -> Leaf:
    """One cup leaf from a frozen standing. `u` and `h` are pseudonyms, not the account id."""
    return {
        "v": 1,
        "k": "cup",
        "id": cup_id,
        "rank": standing["rank"],
        "u": user_hash(str(standing["userId"])),
        "h": handle_hash(str(standing["name"])),
        "eq": standing["equity"],
        "pct": standing["pnlPct"],
        "tr": standing["trades"],
        "dq": standing["disqualified"],
        "fh": standing["fillsHash"],
    }


def _memo_dict(memo: Memo) -> dict[str, Any]:
    return {"kind": memo.kind, "id": memo.id, "root": memo.root, "count": memo.count, "text": memo.text}


def _fail(reason: str, message: str, memo: Memo, computed_root: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "reason": reason, "message": message, "memo": _memo_dict(memo)}
    if computed_root is not None:
        out["computedRoot"] = computed_root
    return out
