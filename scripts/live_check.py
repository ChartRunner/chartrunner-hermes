"""Live check: call ChartRunner's public feed the way the plugin does and fail loudly if anything changed.

Runs on a schedule in GitHub Actions (.github/workflows/live.yml) and by hand:

    python3 scripts/live_check.py                     # production, https://app.chartrunner.xyz
    python3 scripts/live_check.py --origin http://localhost:3000

Exit 0 = every tool path answered in the v1 contract. Exit 1 = at least one failed; the report says which and why.
It only reads. It prints status codes, error classes, and counts, never full bodies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chartrunner_plugin.client import Client  # noqa: E402
from chartrunner_plugin.tools import list_anchors, read_cup, read_radar, status  # noqa: E402


def check(name: str, raw: str, results: list[dict]) -> dict:
    body = json.loads(raw)
    entry = {"check": name, "ok": bool(body.get("ok"))}
    if not entry["ok"]:
        entry.update({k: body.get(k) for k in ("error", "message", "status", "retryable", "retryAfterSeconds")})
    results.append(entry)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default=None)
    args = parser.parse_args()
    client = Client(args.origin)
    results: list[dict] = []

    check("status", status({}, client=client), results)
    for tab in ("new", "trending", "graduated"):
        body = check(f"radar:{tab}", read_radar({"tab": tab, "limit": 3}, client=client), results)
        if body.get("ok"):
            results[-1]["tokens"] = len(body.get("tokens") or [])
            results[-1]["dataAgeSeconds"] = body.get("dataAgeSeconds")
    anchors = check("anchors:cup", list_anchors({"kind": "cup", "limit": 1}, client=client), results)
    newest = (anchors.get("anchors") or [None])[0] if anchors.get("ok") else None
    if newest and newest.get("id"):
        cup = check("cup:newest-anchored", read_cup({"code": newest["id"]}, client=client), results)
        if cup.get("ok"):
            results[-1]["resultsHashMatches"] = cup.get("resultsHashMatches")
            results[-1]["anchorMatched"] = (cup.get("anchor") or {}).get("matched")
            if cup.get("resultsHashMatches") is not True or (cup.get("anchor") or {}).get("matched") is not True:
                results[-1]["ok"] = False
                results[-1]["error"] = "verification_failed"
    else:
        results.append({"check": "cup:newest-anchored", "ok": True, "skipped": "no published cup anchor yet"})

    failed = [r for r in results if not r["ok"]]
    print(json.dumps({"origin": client.origin, "passed": len(results) - len(failed), "failed": len(failed), "results": results}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
