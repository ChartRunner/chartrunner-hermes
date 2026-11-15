"""ChartRunner links. The plugin builds these. It never signs a transaction, and no link opens real-money trading."""

from __future__ import annotations

import re
from urllib.parse import urlparse

ORIGIN = "https://app.chartrunner.xyz"
# Hosts the plugin may talk to. CHARTRUNNER_ORIGIN can only pick one of these (or a local dev server), so a changed
# environment cannot point the agent at a look-alike "ChartRunner".
ALLOWED_HOSTS = frozenset({"app.chartrunner.xyz"})
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})

MINT_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
ROOM_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{8}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Chart symbols the terminal offers for perps (lib/perps/views.ts). Links open them in practice mode (paper money).
PERP_CHARTS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "HYPE": "HYPEUSDT",
    "DOGE": "DOGEUSDT",
}


def origin_of(value: str | None) -> str:
    text = (value or ORIGIN).strip().rstrip("/")
    parsed = urlparse(text)
    host = parsed.hostname or ""
    if parsed.path or parsed.query or parsed.fragment or parsed.username or " " in text:
        raise ValueError("ChartRunner origin must be a bare origin such as https://app.chartrunner.xyz")
    if host in LOCAL_HOSTS and parsed.scheme in ("http", "https"):
        return text
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise ValueError("ChartRunner origin must be https://app.chartrunner.xyz (or localhost for development)")
    return text


def normalise_code(value: str) -> str | None:
    """Room, cup, and battle invite codes. Crockford: O is 0, I and L are 1."""
    compact = re.sub(r"[\s\-._]", "", value.upper()).replace("O", "0").replace("I", "1").replace("L", "1")
    return compact if ROOM_RE.fullmatch(compact) else None


def normalise_uuid(value: str) -> str | None:
    text = value.strip().lower()
    return text if UUID_RE.fullmatch(text) else None


def cup_key(value: str) -> str | None:
    return normalise_uuid(value) or normalise_code(value)


def perp_symbol(value: str) -> str | None:
    text = value.strip().upper().replace(" ", "")
    if text.endswith("-PERP"):
        text = text[: -len("-PERP")]
    base = text[: -len("USDT")] if text.endswith("USDT") else text
    return PERP_CHARTS.get(base)


def practice_chart_url(origin: str, chart_symbol: str) -> str:
    return f"{origin}/terminal?s={chart_symbol}&mode=practice"


def room_url(origin: str, code: str) -> str:
    return f"{origin}/r/{code}"


def battle_lobby_url(origin: str, code: str) -> str:
    return f"{origin}/battles/{code}"


def battle_result_url(origin: str, battle_id: str) -> str:
    return f"{origin}/battles/r/{battle_id}"
