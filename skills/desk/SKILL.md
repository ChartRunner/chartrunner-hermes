---
name: desk
description: When to use ChartRunner tools, and what a memo match does not prove.
---

# ChartRunner desk

Use the ChartRunner tools for live reads and for links the user opens. Do not invent a price, a safety verdict, or a verification result.

- `chartrunner_radar` for new, trending, or graduated Solana launches. Report the safety level and flags the tool returns.
- `chartrunner_spot` before talking about buying a mint. Give the user `reviewUrl`. The verdict is advice. The wallet signs in ChartRunner.
- `chartrunner_perps` for a BTC, ETH, SOL, HYPE, or DOGE perp chart. Give the user `reviewUrl`. Phoenix is allowlist-only. Hermes does not place the order.
- `chartrunner_cup` for a finished cup code or cup id. Read the standings and the anchor match. A match compares those standings with the anchor ChartRunner published. It is not a Solana RPC read.
- `chartrunner_verify` when the user has the memo text and the rows, or one leaf and a proof. A pass means those rows rebuild the memo root.
- `chartrunner_room` and `chartrunner_battle` only build links. A battle is paper money. Hermes cannot join, chat, draw, or send a fill.

A pass does not prove the fills were fair. Never ask for a seed phrase, a private key, or a session cookie. Never say a swap or a perp order was sent.
