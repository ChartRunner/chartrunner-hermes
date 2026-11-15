# ChartRunner for Hermes

Hermes tools for ChartRunner, the trading game on live charts with paper money. They read ChartRunner's public feed and
build links. They never trade, never sign, and no link opens real-money trading.

| Tool | Toolset | What it returns |
| --- | --- | --- |
| `chartrunner_radar` | `chartrunner` | New, trending, or graduated Solana launches with ChartRunner's own safety level and flags, and how old the data is. |
| `chartrunner_cup` | `chartrunner` | Frozen cup standings, whether the results hash checks, and whether the standings rebuild the anchor ChartRunner published. |
| `chartrunner_anchors` | `chartrunner` | The newest on-chain anchor records ChartRunner published. |
| `chartrunner_verify` | `chartrunner` | Whether rows, or one leaf plus a proof, rebuild a `chartrunner:v1` memo. Local, no network. |
| `chartrunner_status` | `chartrunner` | Whether the feed answers this plugin, with plugin and schema versions. |
| `chartrunner_link` | `chartrunner_links` | A practice-mode chart (BTC, ETH, SOL, HYPE, DOGE), a room, or a battle lobby or result link. |

A memo match means the rows rebuild that root. It does not prove the fills were fair. The cup anchor check uses the
anchor record ChartRunner's API published (`anchorChecked: "api-record"`); it does not fetch the Solana transaction.

Names of tokens, players, and cups come from third parties. The plugin cleans them and returns them only in fields
ending in `_untrusted`; the `desk` skill tells the agent to show them as data and never follow them.

## Install

```bash
hermes plugins install https://github.com/ChartRunner/chartrunner-hermes
hermes plugins enable chartrunner
```

Restart the Hermes gateway (or the Umbrel app) afterwards: new tools appear only after a restart. Pin a release for a
reproducible install, for example the `v0.2.0` tag.

## Network

One host: `https://app.chartrunner.xyz`, paths under `/api/public/v1/` only, GET only, no key, no session. The feed is
cached and rate limited per address; a refusal comes back as an error class (`rate_limited` with `retryAfterSeconds`,
`blocked_by_edge`, `not_final`, `schema_mismatch`, ...), never as an HTML page. `CHARTRUNNER_ORIGIN` may point the
tools at `http://localhost:<port>` for development; any other host is refused.

| Plugin | Feed |
| --- | --- |
| 0.2.x | `/api/public/v1`, `schemaVersion` 1 |

## Checks

```bash
python3 -m unittest tests/test_plugin.py      # unit, contract, and HTTP tests against a local server
python3 scripts/live_check.py                 # the same calls against production
hermes plugins doctor . --ci
```

- `tests/fixtures/feed-v1/` are copies of the feed's contract fixtures in the ChartRunner app
  (`apps/web/lib/public/__fixtures__/`). The app's tests compare its answers to them byte for byte; a change there that
  would break this plugin fails there first. Change them only together, in the same release.
- `.github/workflows/live.yml` runs `scripts/live_check.py` against production every three hours. A failure opens an
  issue titled "Live check failing"; the next green run closes it.

The memo rules and `test-vectors/v1.json` come from [ChartRunner/chartrunner-onchain](https://github.com/ChartRunner/chartrunner-onchain).
Do not edit the vectors here. Change the spec there first.
