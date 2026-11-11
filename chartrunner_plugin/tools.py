"""Hermes tool handlers. Every handler returns a JSON string and never signs."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping

from .client import ApiError, Client
from .links import (
    MINT_RE,
    battle_lobby_url,
    battle_result_url,
    cup_key,
    normalise_code,
    normalise_uuid,
    perp_symbol,
    perp_url,
    room_url,
    spot_url,
)
from .verify import Memo, build_root, cup_leaf, prepare_leaves, verify_against_memo

SIGNING = "Hermes does not sign. Open the link and review the transaction in your wallet."
PASS_LIMIT = (
    "A match means these rows rebuild the root in the memo. "
    "It does not prove the fills were fair, and it does not read Solana unless you supply the memo yourself."
)
MAX_ROWS = 10_000
RADAR_TABS = ("new", "trending", "graduated")
RADAR_SAFE = ("all", "no-red", "green")


def _dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _err(message: str, **extra: Any) -> str:
    body: dict[str, Any] = {"ok": False, "error": message}
    body.update(extra)
    return _dump(body)


def _client(origin: str | None = None) -> Client:
    return Client(origin or os.environ.get("CHARTRUNNER_ORIGIN"))


def _parse_rows(args: Mapping[str, Any]) -> tuple[list[Any] | None, str | None]:
    raw = args.get("rows_json", args.get("rows"))
    if raw is None:
        return None, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None, "rows_json is not JSON"
    if not isinstance(raw, list):
        return None, "rows must be a JSON array"
    if len(raw) > MAX_ROWS:
        return None, f"at most {MAX_ROWS} rows"
    return raw, None


def _parse_proof(args: Mapping[str, Any]) -> tuple[Any, str | None]:
    raw = args.get("proof_json", args.get("proof"))
    if raw is None:
        return None, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None, "proof_json is not JSON"
    return raw, None


def verify_memo(args: Mapping[str, Any], **_: Any) -> str:
    memo = args.get("memo")
    if not isinstance(memo, str) or not memo.strip():
        return _err("memo is required")
    rows, row_error = _parse_rows(args)
    if row_error:
        return _err(row_error)
    proof, proof_error = _parse_proof(args)
    if proof_error:
        return _err(proof_error)
    leaf = args.get("leaf")
    result = verify_against_memo(
        memo.strip(),
        rows=rows,
        leaf=leaf if rows is None else None,
        proof=proof if rows is None else None,
        expect_kind=args.get("expect_kind") or None,
        expect_id=args.get("expect_id") or None,
    )
    result["limit"] = PASS_LIMIT
    return _dump(result)


def _standing_view(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rank": row.get("rank"),
        "name": row.get("name"),
        "equity": row.get("equity"),
        "pnl": row.get("pnl"),
        "pnlPct": row.get("pnlPct"),
        "trades": row.get("trades"),
        "disqualified": row.get("disqualified"),
        "fillsHash": row.get("fillsHash"),
    }


def _anchor_check(standings: list[Mapping[str, Any]], cup_id: str, anchors: Any) -> dict[str, Any]:
    published = anchors.get("anchors") if isinstance(anchors, dict) else None
    if not published:
        return {"matched": False, "reason": "no_anchor"}
    first = published[0]
    if not isinstance(first, dict) or not isinstance(first.get("root"), str):
        return {"matched": False, "reason": "anchor_unreadable"}
    try:
        leaves = [cup_leaf(cup_id, row) for row in standings]
        prepared = prepare_leaves(leaves)
        root = build_root([item[1] for item in prepared])
        memo = Memo("cup", cup_id, first["root"], int(first["count"]))
        checked = verify_against_memo(memo.text, rows=leaves)
    except (KeyError, TypeError, ValueError):
        return {"matched": False, "reason": "standings_incomplete", "publishedRoot": first.get("root")}
    return {
        "matched": checked.get("ok") is True and root == first.get("root"),
        "publishedRoot": first.get("root"),
        "computedRoot": root,
        "count": first.get("count"),
        "signature": first.get("signature"),
        "slot": first.get("slot"),
        "cluster": first.get("cluster"),
        "signer": first.get("signer"),
        "reason": None if checked.get("ok") else checked.get("reason"),
        "limit": "Compared with the anchor ChartRunner published. This call does not read the Solana transaction.",
    }


def read_cup(args: Mapping[str, Any], *, client: Client | None = None, **_: Any) -> str:
    key = cup_key(str(args.get("code") or ""))
    if key is None:
        return _err("code must be an 8-character room code or a cup id")
    api = client or _client()
    try:
        payload = api.cup_results(key)
    except ApiError as exc:
        return _err(exc.message, status=exc.status)
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), dict):
        return _err("cup results were not a results document")
    results = payload["results"]
    raw_standings = results.get("standings")
    if not isinstance(raw_standings, list):
        return _err("cup results have no standings")
    standings = [row for row in raw_standings if isinstance(row, dict)]
    results_json = payload.get("resultsJson")
    reported = payload.get("hash")
    recomputed = hashlib.sha256(results_json.encode()).hexdigest() if isinstance(results_json, str) else None
    cup_id = str(payload.get("cupId") or results.get("cup", {}).get("id") or "")
    anchor: dict[str, Any] | None = None
    if cup_id:
        try:
            anchor = _anchor_check(standings, cup_id, api.anchors("cup", cup_id))
        except ApiError as exc:
            anchor = {"matched": False, "reason": exc.message, "status": exc.status}
    return _dump(
        {
            "ok": True,
            "cupId": cup_id,
            "name": payload.get("name"),
            "resultsHash": reported,
            "resultsHashMatches": recomputed == reported if recomputed and isinstance(reported, str) else None,
            "standings": [_standing_view(row) for row in standings if isinstance(row, dict)],
            "anchor": anchor,
            "limit": "SIM standings. A host prize line is text, not a payout. Account ids are omitted.",
        }
    )


def _radar_card(token: Mapping[str, Any]) -> dict[str, Any]:
    safety = token.get("safety") if isinstance(token.get("safety"), dict) else {}
    swap = token.get("swap") if isinstance(token.get("swap"), dict) else {}
    return {
        "mint": token.get("mint"),
        "symbol": token.get("symbol"),
        "name": token.get("name"),
        "ageMin": token.get("ageMin"),
        "liquidityUsd": token.get("liquidityUsd"),
        "safety": safety.get("level"),
        "flags": safety.get("flags") or [],
        "swapAllowed": swap.get("allowed"),
        "status": token.get("status"),
    }


def read_radar(args: Mapping[str, Any], *, client: Client | None = None, **_: Any) -> str:
    tab = str(args.get("tab") or "new")
    safe = str(args.get("safe") or "all")
    if tab not in RADAR_TABS:
        return _err("tab must be new, trending, or graduated")
    if safe not in RADAR_SAFE:
        return _err("safe must be all, no-red, or green")
    api = client or _client()
    try:
        payload = api.radar(tab, safe)
    except ApiError as exc:
        return _err(exc.message, status=exc.status)
    tokens = payload.get("tokens") if isinstance(payload, dict) else None
    if not isinstance(tokens, list):
        return _err("radar response has no tokens")
    limit = args.get("limit") or 8
    try:
        count = max(1, min(20, int(limit)))
    except (TypeError, ValueError):
        return _err("limit must be an integer")
    return _dump(
        {
            "ok": True,
            "tab": tab,
            "safe": safe,
            "computedAt": payload.get("computedAt"),
            "tokens": [_radar_card(token) for token in tokens[:count] if isinstance(token, dict)],
            "limit": "Safety flags are ChartRunner's checks. They are not a promise the token is safe to buy.",
        }
    )


def spot_review(args: Mapping[str, Any], *, client: Client | None = None, **_: Any) -> str:
    mint = str(args.get("mint") or "").strip()
    if not MINT_RE.fullmatch(mint):
        return _err("mint must be a Solana address")
    api = client or _client()
    url = spot_url(api.origin, mint)
    try:
        verdict = api.verdict(mint)
    except ApiError as exc:
        return _err(exc.message, status=exc.status, reviewUrl=url, signing=SIGNING)
    if not isinstance(verdict, dict):
        return _err("verdict was not an object", reviewUrl=url, signing=SIGNING)
    return _dump(
        {
            "ok": True,
            "mint": mint,
            "allowed": verdict.get("allowed"),
            "code": verdict.get("code"),
            "reason": verdict.get("reason"),
            "risk": verdict.get("risk"),
            "warnings": verdict.get("warnings"),
            "reviewUrl": url,
            "signing": SIGNING,
            "limit": "The verdict is advice. The order route checks the mint again, and the wallet signs in ChartRunner.",
        }
    )


def perp_review(args: Mapping[str, Any], *, client: Client | None = None, **_: Any) -> str:
    chart = perp_symbol(str(args.get("symbol") or ""))
    if chart is None:
        return _err("symbol must be BTC, ETH, SOL, HYPE, or DOGE")
    api = client or _client()
    return _dump(
        {
            "ok": True,
            "symbol": chart,
            "reviewUrl": perp_url(api.origin, chart),
            "signing": SIGNING,
            "limit": (
                "The link opens the real-mode perp chart. Phoenix is allowlist-only, "
                "the public deployment may answer not_enabled, and the order stays unsigned until the wallet signs."
            ),
        }
    )


def open_room(args: Mapping[str, Any], *, client: Client | None = None, **_: Any) -> str:
    code = normalise_code(str(args.get("code") or ""))
    if code is None:
        return _err("code must be an 8-character room code")
    api = client or _client()
    return _dump(
        {
            "ok": True,
            "code": code,
            "url": room_url(api.origin, code),
            "limit": "Hermes cannot join, chat, or draw. Opening the link uses your ChartRunner session.",
        }
    )


def open_battle(args: Mapping[str, Any], *, client: Client | None = None, **_: Any) -> str:
    raw = str(args.get("code") or "")
    api = client or _client()
    battle_id = normalise_uuid(raw)
    if battle_id:
        return _dump(
            {
                "ok": True,
                "kind": "result",
                "url": battle_result_url(api.origin, battle_id),
                "limit": "Public result page for a finished SIM battle. The invite code is not in this link.",
            }
        )
    code = normalise_code(raw)
    if code is None:
        return _err("pass an 8-character battle code or a battle id")
    return _dump(
        {
            "ok": True,
            "kind": "lobby",
            "code": code,
            "url": battle_lobby_url(api.origin, code),
            "limit": "SIM only. A registered ChartRunner account joins and places fills. Hermes does neither.",
        }
    )


def _schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }


STRING = {"type": "string"}
TOOLS = (
    (
        "chartrunner_verify",
        _schema(
            "chartrunner_verify",
            "Check ChartRunner rows, or one leaf plus a Merkle proof, against a chartrunner:v1 memo. A pass rebuilds the memo root. It does not read Solana and does not prove fills were fair.",
            {
                "memo": {**STRING, "description": "Exact memo text chartrunner:v1:<kind>:<id>:<root>:<count>"},
                "rows_json": {**STRING, "description": "JSON array of leaf rows. Use this or leaf plus proof."},
                "leaf": {**STRING, "description": "Canonical JSON of one leaf, when using a proof."},
                "proof_json": {**STRING, "description": "JSON array of {side: L|R, hash} steps."},
                "expect_kind": {**STRING, "description": "Reject the memo unless its kind matches."},
                "expect_id": {**STRING, "description": "Reject the memo unless its id matches."},
            },
            ["memo"],
        ),
        verify_memo,
        "🔎",
    ),
    (
        "chartrunner_cup",
        _schema(
            "chartrunner_cup",
            "Load a finished ChartRunner Trading Cup by invite code or cup id. Returns standings and whether they rebuild the published cup anchor. Account ids are left out.",
            {"code": {**STRING, "description": "8-character invite code or cup id"}},
            ["code"],
        ),
        read_cup,
        "🏆",
    ),
    (
        "chartrunner_radar",
        _schema(
            "chartrunner_radar",
            "List Solana launches from ChartRunner radar with the server's safety level, flags, liquidity, and age.",
            {
                "tab": {"type": "string", "enum": list(RADAR_TABS), "description": "new, trending, or graduated"},
                "safe": {"type": "string", "enum": list(RADAR_SAFE), "description": "all, no-red, or green"},
                "limit": {"type": "integer", "description": "How many tokens to return, 1 to 20. Default 8."},
            },
            ["tab"],
        ),
        read_radar,
        "📡",
    ),
    (
        "chartrunner_spot",
        _schema(
            "chartrunner_spot",
            "Read ChartRunner's public buy verdict for a Solana mint and return the terminal link. The wallet signs in the app. Hermes does not.",
            {"mint": {**STRING, "description": "Solana mint address"}},
            ["mint"],
        ),
        spot_review,
        "◎",
    ),
    (
        "chartrunner_perps",
        _schema(
            "chartrunner_perps",
            "Return the ChartRunner real-mode perp chart link for BTC, ETH, SOL, HYPE, or DOGE. The Phoenix order stays unsigned until the user's wallet signs.",
            {"symbol": {**STRING, "description": "BTC, ETH, SOL, HYPE, or DOGE"}},
            ["symbol"],
        ),
        perp_review,
        "📈",
    ),
    (
        "chartrunner_room",
        _schema(
            "chartrunner_room",
            "Return the link for a ChartRunner room code. Hermes cannot join, chat, or draw.",
            {"code": {**STRING, "description": "8-character room code"}},
            ["code"],
        ),
        open_room,
        "🗺",
    ),
    (
        "chartrunner_battle",
        _schema(
            "chartrunner_battle",
            "Return a ChartRunner battle lobby link from an invite code, or the public result link from a battle id. Battles are SIM. Hermes does not join or trade.",
            {"code": {**STRING, "description": "8-character battle code, or a battle id for the result page"}},
            ["code"],
        ),
        open_battle,
        "⚔",
    ),
)
