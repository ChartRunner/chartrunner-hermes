"""Public ChartRunner reads through the versioned feed /api/public/v1. GET only. No session, no wallet, no key."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import quote, urlencode, urlparse

from .links import ORIGIN, origin_of

VERSION = "0.2.0"
FEED = "/api/public/v1"
SCHEMA_VERSION = 1
TIMEOUT_S = 15
MAX_BYTES = 1_000_000
USER_AGENT = f"chartrunner-hermes/{VERSION} (+https://github.com/ChartRunner/chartrunner-hermes)"

GetJson = Callable[[str], Any]

# Error classes the tools report. `retryable` says whether trying again later can help.
RETRYABLE = {"rate_limited": True, "upstream_unavailable": True, "not_configured": True, "network_error": True}


class ApiError(Exception):
    """A failed read, as a fixed class plus a short plain message. Never carries an HTML body."""

    def __init__(self, status: int, error_class: str, message: str, retry_after_s: int | None = None, phase: str | None = None):
        super().__init__(message)
        self.status = status
        self.error_class = error_class
        self.message = message
        self.retry_after_s = retry_after_s
        self.phase = phase

    @property
    def retryable(self) -> bool:
        return RETRYABLE.get(self.error_class, False)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.error_class, "message": self.message, "status": self.status, "retryable": self.retryable}
        if self.retry_after_s is not None:
            out["retryAfterSeconds"] = self.retry_after_s
        if self.phase is not None:
            out["phase"] = self.phase
        return out


MESSAGES = {
    "blocked_by_edge": "ChartRunner's bot protection refused the request. It is not your input. Do not retry or try to get around it.",
    "rate_limited": "Too many requests. Wait before asking again.",
    "invalid_parameters": "ChartRunner refused the parameters.",
    "not_found": "Not found.",
    "not_final": "The cup is not finished yet; results appear once it is frozen.",
    "radar_off": "The radar is switched off on ChartRunner right now.",
    "not_configured": "ChartRunner cannot serve this right now.",
    "upstream_unavailable": "ChartRunner's data source is unavailable right now.",
    "schema_mismatch": "ChartRunner answered in a format this plugin version does not know. Update the plugin.",
}


def _retry_after(headers: Any) -> int | None:
    raw = headers.get("retry-after") if headers is not None else None
    try:
        return max(1, int(raw)) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _error_from(status: int, headers: Any, raw: bytes) -> ApiError:
    content_type = (headers.get("content-type") or "") if headers is not None else ""
    mitigated = (headers.get("x-vercel-mitigated") or "") if headers is not None else ""
    if mitigated or "text/html" in content_type:
        return ApiError(status, "blocked_by_edge", MESSAGES["blocked_by_edge"])
    try:
        body = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        body = None
    code = body.get("error") if isinstance(body, dict) else None
    if not isinstance(code, str) or code not in MESSAGES:
        code = "rate_limited" if status == 429 else "upstream_unavailable"
    phase = body.get("phase") if isinstance(body, dict) and isinstance(body.get("phase"), str) else None
    return ApiError(status, code, MESSAGES[code], _retry_after(headers), phase)


class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise ApiError(code, "blocked_by_edge", "ChartRunner redirected the request; the plugin does not follow redirects.")


def get_json(url: str, *, timeout: float = TIMEOUT_S) -> Any:
    host = urlparse(url).hostname
    opener = urllib.request.build_opener(_RejectRedirect)
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=timeout) as response:
            if urlparse(response.geturl()).hostname != host:
                raise ApiError(response.status, "blocked_by_edge", "ChartRunner redirected the request.")
            raw = response.read(MAX_BYTES + 1)
            status = response.status
            headers = response.headers
    except ApiError:
        raise
    except urllib.error.HTTPError as exc:
        raise _error_from(exc.code, exc.headers, exc.read(4000)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError(0, "network_error", f"Could not reach ChartRunner: {getattr(exc, 'reason', exc)}") from exc
    if len(raw) > MAX_BYTES:
        raise ApiError(status, "schema_mismatch", "ChartRunner's answer was too large.")
    if "application/json" not in (headers.get("content-type") or ""):
        raise _error_from(status, headers, b"")
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError(status, "schema_mismatch", MESSAGES["schema_mismatch"]) from exc
    if not isinstance(body, dict) or body.get("schemaVersion") != SCHEMA_VERSION:
        raise ApiError(status, "schema_mismatch", MESSAGES["schema_mismatch"])
    return body


class Client:
    def __init__(self, origin: str | None = None, get: GetJson | None = None):
        self.origin = origin_of(origin or ORIGIN)
        self._get = get or get_json

    def get(self, path: str, query: dict[str, str] | None = None) -> Any:
        url = f"{self.origin}{FEED}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        return self._get(url)

    def cup_results(self, key: str) -> Any:
        return self.get(f"/cups/{quote(key, safe='')}/results")

    def anchors(self, kind: str | None = None, anchor_id: str | None = None, limit: int = 5) -> Any:
        query = {"limit": str(limit)}
        if kind:
            query["kind"] = kind
        if anchor_id:
            query["id"] = anchor_id
        return self.get("/anchors", query)

    def radar(self, tab: str, safe: str) -> Any:
        query = {"tab": tab}
        if safe != "all":
            query["safe"] = safe
        return self.get("/radar", query)
