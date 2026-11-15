# Changelog

## 0.2.0

The tools read ChartRunner's versioned public feed and nothing that touches real money.

- Changed: every read goes to `https://app.chartrunner.xyz/api/public/v1/` (radar, anchors, cup results). The old app
  routes are no longer called; ChartRunner's bot protection blocked them for server-side clients since 2026-11-08.
- Changed: the default origin is `https://app.chartrunner.xyz`; `CHARTRUNNER_ORIGIN` accepts only that host or localhost.
- Removed: `chartrunner_spot` (the buy verdict and swap link). ChartRunner is paper money only.
- Removed: `chartrunner_perps`, `chartrunner_room`, `chartrunner_battle`. Replaced by `chartrunner_link`
  (`practice_chart`, `room`, `battle`) in its own toolset `chartrunner_links`. Chart links open practice mode, never
  real mode.
- Added: `chartrunner_anchors` (published anchor records) and `chartrunner_status` (is the feed reachable, which versions).
- Added: third-party text (token, player, and cup names) is cleaned and returned only as `*_untrusted` fields.
- Added: errors carry a class (`blocked_by_edge`, `rate_limited`, `not_final`, `schema_mismatch`, ...), `retryable`, and
  `retryAfterSeconds`; HTML pages never reach the agent. An unknown `schemaVersion` is refused as `schema_mismatch`.
- Changed: `chartrunner_cup` reads the standings from the hashed `resultsJson`, so the hash and the anchor check cover
  what is shown; it reports `anchorChecked: "api-record"`.
- Added: contract fixtures shared with the app, HTTP tests against a local server, CI, and a scheduled live check
  against production.

## 0.1.0

First release: verify, cup, radar, spot, perps, room, battle.
