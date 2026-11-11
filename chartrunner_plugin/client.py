"""Public ChartRunner reads. GET only. No session, no wallet, no order route."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import quote, urlencode, urlparse

from .links import ORIGIN, origin_of

TIMEOUT_S = 15
MAX_BYTES = 1_000_000
USER_AGENT = "chartrunner-hermes/0.1"

GetJson = Callable[[str], Any]


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _no_redirect(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})


class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise ApiError(code, "redirect refused")


def get_json(url: str, *, timeout: float = TIMEOUT_S) -> Any:
    host = urlparse(url).hostname
    opener = urllib.request.build_opener(_RejectRedirect)
    try:
        with opener.open(_no_redirect(url), timeout=timeout) as response:
            final = urlparse(response.geturl()).hostname
            if final != host:
                raise ApiError(response.status, "redirect refused")
            raw = response.read(MAX_BYTES + 1)
            status = response.status
    except ApiError:
        raise
    except urllib.error.HTTPError as exc:
        detail = exc.read(400).decode("utf-8", "replace")
        try:
            body = json.loads(detail)
            message = body.get("error") or body.get("reason") or detail[:180]
        except json.JSONDecodeError:
            message = detail[:180] or exc.reason
        raise ApiError(exc.code, str(message)) from exc
    except urllib.error.URLError as exc:
        raise ApiError(0, f"network error: {exc.reason}") from exc
    if len(raw) > MAX_BYTES:
        raise ApiError(status, "response too large")
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError(status, "response was not JSON") from exc


class Client:
    def __init__(self, origin: str | None = None, get: GetJson | None = None):
        self.origin = origin_of(origin or ORIGIN)
        self._get = get or get_json

    def get(self, path: str, query: dict[str, str] | None = None) -> Any:
        url = self.origin + path
        if query:
            url = f"{url}?{urlencode(query)}"
        return self._get(url)

    def cup_results(self, key: str) -> Any:
        return self.get(f"/api/cups/{quote(key, safe='')}/results")

    def anchors(self, kind: str, anchor_id: str) -> Any:
        return self.get("/api/anchors", {"kind": kind, "id": anchor_id, "limit": "5"})

    def radar(self, tab: str, safe: str) -> Any:
        query = {"tab": tab}
        if safe != "all":
            query["safe"] = safe
        return self.get("/api/radar/list", query)

    def verdict(self, mint: str) -> Any:
        return self.get("/api/swap/verdict", {"mint": mint})
