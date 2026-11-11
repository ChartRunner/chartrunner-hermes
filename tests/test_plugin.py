"""Verifier, links, and tool handlers. No network."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chartrunner_plugin.client import ApiError  # noqa: E402
from chartrunner_plugin.links import (  # noqa: E402
    battle_lobby_url,
    battle_result_url,
    normalise_code,
    perp_url,
    room_url,
    spot_url,
)
from chartrunner_plugin.tools import open_battle, open_room, perp_review, read_cup, read_radar, spot_review, verify_memo  # noqa: E402
from chartrunner_plugin.verify import (  # noqa: E402
    build_root,
    cup_leaf,
    handle_hash,
    hash_node,
    prepare_leaves,
    user_hash,
    verify_against_memo,
)

VECTORS = ROOT / "test-vectors" / "v1.json"
ORIGIN = "https://chartrunner-app.vercel.app"


class Vectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(VECTORS.read_text())

    def test_pseudonyms(self):
        fns = {"userHash": user_hash, "handleHash": handle_hash}
        for row in self.data["pseudonyms"]:
            fn = fns.get(row["fn"])
            if fn is None:
                continue
            self.assertEqual(fn(row["input"]), row["output"], row["fn"])

    def test_nodes(self):
        for row in self.data["nodes"]:
            self.assertEqual(hash_node(row["left"], row["right"]), row["node"])

    def test_trees_and_proofs(self):
        for tree in self.data["trees"]:
            checked = verify_against_memo(tree["memo"], rows=tree["rows"])
            self.assertTrue(checked["ok"], tree["name"])
            self.assertEqual(checked["root"], tree["root"])
            prepared = prepare_leaves(tree["rows"])
            self.assertEqual([item[0] for item in prepared], [leaf["canonical"] for leaf in tree["sortedLeaves"]])
            for proof in tree["proofs"]:
                proved = verify_against_memo(tree["memo"], leaf=proof["leaf"], proof=proof["proof"])
                self.assertTrue(proved["ok"], tree["name"])

    def test_tampered_row_mismatches(self):
        tree = self.data["trees"][0]
        rows = [dict(tree["rows"][0])]
        rows[0]["s"] = rows[0]["s"] + 1
        checked = verify_against_memo(tree["memo"], rows=rows)
        self.assertEqual(checked["reason"], "root_mismatch")
        self.assertNotEqual(checked["computedRoot"], tree["root"])


class Links(unittest.TestCase):
    def test_codes_and_urls(self):
        self.assertEqual(normalise_code("k7fm-9pq2"), "K7FM9PQ2")
        self.assertEqual(normalise_code("k7fm-9pql"), "K7FM9PQ1")
        mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        self.assertEqual(spot_url(ORIGIN, mint), f"{ORIGIN}/terminal?s=sol:{mint}")
        self.assertEqual(perp_url(ORIGIN, "SOLUSDT"), f"{ORIGIN}/terminal?s=SOLUSDT&mode=real")
        self.assertEqual(room_url(ORIGIN, "K7FM9PQ2"), f"{ORIGIN}/r/K7FM9PQ2")
        self.assertEqual(battle_lobby_url(ORIGIN, "K7FM9PQ2"), f"{ORIGIN}/battles/K7FM9PQ2")
        battle = "123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(battle_result_url(ORIGIN, battle), f"{ORIGIN}/battles/r/{battle}")


class _Fake:
    origin = ORIGIN

    def __init__(self, **responses):
        self.responses = responses

    def cup_results(self, key):
        return self.responses["cup"]

    def anchors(self, kind, anchor_id):
        return self.responses["anchors"]

    def radar(self, tab, safe):
        return self.responses["radar"]

    def verdict(self, mint):
        return self.responses["verdict"]


class Tools(unittest.TestCase):
    def test_verify_tool_rejects_a_bad_memo(self):
        body = json.loads(verify_memo({"memo": "nope", "rows_json": "[{\"id\":\"a\",\"s\":1}]"}))
        self.assertEqual(body["reason"], "memo_malformed")

    def test_cup_anchor_match_and_tamper(self):
        standing = {
            "rank": 1,
            "userId": "user-0001",
            "name": "Ada",
            "equity": "10.00",
            "pnl": "0",
            "pnlPct": "0.00",
            "trades": 1,
            "disqualified": False,
            "fillsHash": "cd" * 32,
        }
        leaf = cup_leaf("cup-1", standing)
        prepared = prepare_leaves([leaf])
        root = build_root([item[1] for item in prepared])
        text = json.dumps({"standings": [standing]}, separators=(",", ":"))
        payload = {
            "cupId": "cup-1",
            "name": "Friday",
            "hash": __import__("hashlib").sha256(text.encode()).hexdigest(),
            "resultsJson": text,
            "results": {"standings": [standing], "cup": {"id": "cup-1"}},
        }
        anchors = {"anchors": [{"root": root, "count": 1, "signature": "sig", "slot": 9, "cluster": "devnet", "signer": "op"}]}
        matched = json.loads(read_cup({"code": "K7FM9PQ2"}, client=_Fake(cup=payload, anchors=anchors)))
        self.assertTrue(matched["anchor"]["matched"])
        self.assertNotIn("userId", matched["standings"][0])
        tampered = json.loads(json.dumps(payload))
        tampered["results"]["standings"][0]["equity"] = "11.00"
        missed = json.loads(read_cup({"code": "K7FM9PQ2"}, client=_Fake(cup=tampered, anchors=anchors)))
        self.assertFalse(missed["anchor"]["matched"])
        self.assertEqual(missed["anchor"]["reason"], "root_mismatch")

    def test_radar_and_spot_and_links(self):
        radar = json.loads(
            read_radar(
                {"tab": "new", "safe": "green", "limit": 1},
                client=_Fake(radar={"computedAt": "2026-11-11T00:00:00Z", "tokens": [
                    {"mint": "a" * 32, "symbol": "AAA", "name": "Aaa", "ageMin": 3, "liquidityUsd": 1000, "safety": {"level": "green", "flags": []}, "swap": {"allowed": True}, "status": "curve"},
                    {"mint": "b" * 32, "symbol": "BBB", "name": "Bbb"},
                ]}),
            )
        )
        self.assertEqual(len(radar["tokens"]), 1)
        self.assertEqual(radar["tokens"][0]["safety"], "green")

        mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        spot = json.loads(spot_review({"mint": mint}, client=_Fake(verdict={"allowed": False, "code": "hard_check_failed", "reason": "freeze authority set"})))
        self.assertFalse(spot["allowed"])
        self.assertIn("/terminal?s=sol:", spot["reviewUrl"])
        self.assertIn("does not sign", spot["signing"])

        perp = json.loads(perp_review({"symbol": "sol-perp"}, client=_Fake()))
        self.assertEqual(perp["reviewUrl"], f"{ORIGIN}/terminal?s=SOLUSDT&mode=real")
        room = json.loads(open_room({"code": "k7fm 9pq2"}, client=_Fake()))
        self.assertEqual(room["url"], f"{ORIGIN}/r/K7FM9PQ2")
        battle = json.loads(open_battle({"code": "123E4567-E89B-12D3-A456-426614174000"}, client=_Fake()))
        self.assertEqual(battle["kind"], "result")
        lobby = json.loads(open_battle({"code": "K7FM9PQ2"}, client=_Fake()))
        self.assertEqual(lobby["kind"], "lobby")

    def test_api_error_is_a_failure(self):
        class Down(_Fake):
            def radar(self, tab, safe):
                raise ApiError(429, "rate_limited")

        body = json.loads(read_radar({"tab": "new"}, client=Down()))
        self.assertFalse(body["ok"])
        self.assertEqual(body["status"], 429)


if __name__ == "__main__":
    unittest.main()
