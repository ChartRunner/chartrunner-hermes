"""ChartRunner links. The plugin builds these. It never signs a transaction."""

from __future__ import annotations

import re

ORIGIN = "https://chartrunner-app.vercel.app"
MINT_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
ROOM_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{8}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Chart symbols the terminal offers for Phoenix perps (lib/perps/views.ts).
PERP_CHARTS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "HYPE": "HYPEUSDT",
    "DOGE": "DOGEUSDT",
}


def origin_of(value: str | None) -> str:
    text = (value or ORIGIN).strip().rstrip("/")
    if not text.startswith("https://") or " " in text:
        raise ValueError("ChartRunner origin must be an https URL")
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
    if text.endswith("USDT"):
        base = text[: -len("USDT")]
    else:
        base = text
    return PERP_CHARTS.get(base)


def spot_url(origin: str, mint: str) -> str:
    if not MINT_RE.fullmatch(mint):
        raise ValueError("invalid mint")
    return f"{origin}/terminal?s=sol:{mint}"


def perp_url(origin: str, chart_symbol: str) -> str:
    return f"{origin}/terminal?s={chart_symbol}&mode=real"


def room_url(origin: str, code: str) -> str:
    return f"{origin}/r/{code}"


def battle_lobby_url(origin: str, code: str) -> str:
    return f"{origin}/battles/{code}"


def battle_result_url(origin: str, battle_id: str) -> str:
    return f"{origin}/battles/r/{battle_id}"
