# ChartRunner for Hermes

Hermes tools for ChartRunner. They read public data and build links. They do not sign, and they do not call the swap or perp execute routes.

| Tool | What it returns |
| --- | --- |
| `chartrunner_verify` | Whether the rows, or one leaf plus a proof, rebuild a `chartrunner:v1` memo. |
| `chartrunner_cup` | Frozen cup standings, and whether those standings rebuild the anchor ChartRunner published. |
| `chartrunner_radar` | New, trending, or graduated launches with the server's safety level and flags. |
| `chartrunner_spot` | The public buy verdict for a mint, and the terminal link where the wallet reviews the swap. |
| `chartrunner_perps` | The real-mode chart link for BTC, ETH, SOL, HYPE, or DOGE. |
| `chartrunner_room` | The link for a room code. |
| `chartrunner_battle` | A SIM battle lobby link, or the public result link for a battle id. |

A memo match means the rows rebuild that root. It does not prove the fills were fair. The cup anchor check uses the anchor record ChartRunner's API published. It does not fetch the Solana transaction.

The default origin is `https://chartrunner-app.vercel.app`. Set `CHARTRUNNER_ORIGIN` to point the tools at another deployment.

## Check

From this directory:

```bash
python3 -m unittest tests/test_plugin.py
hermes plugins doctor . --ci
```

This repository is the plugin. Install it with:

```bash
hermes plugins install https://github.com/ChartRunner/chartrunner-hermes
```

The memo rules and `test-vectors/v1.json` come from [ChartRunner/chartrunner-onchain](https://github.com/ChartRunner/chartrunner-onchain). Do not edit the vectors here. Change the spec there first.
