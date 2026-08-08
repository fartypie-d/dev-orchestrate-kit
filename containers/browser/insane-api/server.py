#!/usr/bin/env python3
"""HTTP front end for the insane-search fetch engine.

Why this exists: upstream ships the bypass logic as a Claude Code plugin, so
only Claude users can reach it. The engine underneath is plain Python with a
clean `fetch()` entrypoint and no LLM calls of its own, so exposing it over
HTTP makes the same escalation pipeline (Phase 0 public endpoints → probes →
curl_cffi TLS impersonation → real headed browser) usable from opencode, a
shell script, or anything else on this host.

Stdlib only — the CloakBrowser base image has no web framework and this needs
no more than a threaded request loop.

Bind: 0.0.0.0 inside the container; compose publishes it on 127.0.0.1 only.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import cdp_bridge

CDP_MODE = cdp_bridge.install()

from engine import fetch, safety  # noqa: E402  (must come after the bridge is installed)

LOG = logging.getLogger("insane-api")

PORT = int(os.environ.get("INSANE_API_PORT", "9223"))
# Every browser fallback is a real Chrome. This is a shared machine, so cap
# how many can be in flight at once rather than letting a burst of callers
# fork Chrome until the box swaps.
MAX_CONCURRENCY = int(os.environ.get("INSANE_MAX_CONCURRENCY", "4"))
MAX_BODY_BYTES = 64 * 1024

_slots = threading.BoundedSemaphore(MAX_CONCURRENCY)

USAGE = {
    "service": "insane-search engine over HTTP",
    "upstream": "https://github.com/fivetaku/insane-search (MIT)",
    "cdp_mode": CDP_MODE,
    "endpoints": {
        "GET  /health": "liveness + config",
        "GET  /fetch?url=...": "query-string form; repeatable &selector=",
        "POST /fetch": "JSON body, same field names",
    },
    "fields": {
        "url": "required, http(s) only",
        "selectors": "list[str] — positive-proof CSS selectors",
        "device": "auto | desktop | mobile",
        "timeout": "per-attempt seconds (default 25)",
        "max_attempts": "int or null for exhaustive",
        "playwright": "bool — allow the headed-browser fallback (default true)",
        "phase0": "bool — allow the official-API router (default true)",
        "extraction": "bool — PDF/JSON-LD/render-merge rescue (default true)",
        "retry": "bool — retry transient 429/5xx (default true)",
        "wrap": "bool — also return the untrusted-content-wrapped text",
    },
    "note": (
        "Private, loopback, link-local and cloud-metadata targets are refused "
        "by the engine's own SSRF guard and that is not overridable here."
    ),
}


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "off", "")


def _params_from_query(qs: str) -> dict:
    q = parse_qs(qs, keep_blank_values=False)

    def one(key):
        vals = q.get(key)
        return vals[0] if vals else None

    return {
        "url": one("url"),
        "selectors": q.get("selector") or q.get("selectors"),
        "device": one("device"),
        "timeout": one("timeout"),
        "max_attempts": one("max_attempts"),
        "playwright": one("playwright"),
        "phase0": one("phase0"),
        "extraction": one("extraction"),
        "retry": one("retry"),
        "wrap": one("wrap"),
    }


def _run_fetch(params: dict) -> tuple[int, dict]:
    url = (params.get("url") or "").strip()
    if not url:
        return 400, {"error": "missing 'url'"}
    scheme = urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        return 400, {"error": f"unsupported scheme: {scheme or '(none)'}"}

    # The engine only applies its SSRF guard inside the curl transport — the
    # browser fallback navigates whatever URL it is handed. Verified: a request
    # for 169.254.169.254 came back empty, but a real Chrome window had already
    # opened on it. Gate the caller-supplied URL here so every phase is covered.
    allowed, reason = safety.classify_url(url, allow_private=False)
    if not allowed:
        return 403, {"error": f"blocked target: {reason}"}

    selectors = params.get("selectors")
    if isinstance(selectors, str):
        selectors = [selectors]

    device = (params.get("device") or "auto").lower()
    if device not in ("auto", "desktop", "mobile"):
        return 400, {"error": "device must be auto|desktop|mobile"}

    try:
        timeout = int(params.get("timeout") or 25)
        raw_max = params.get("max_attempts")
        max_attempts = int(raw_max) if raw_max not in (None, "", "null") else None
    except (TypeError, ValueError):
        return 400, {"error": "timeout/max_attempts must be integers"}

    wrap = _as_bool(params.get("wrap"), False)

    if not _slots.acquire(timeout=120):
        # Better an explicit 503 than a caller blocking forever behind a queue
        # of browser launches.
        return 503, {"error": f"busy: more than {MAX_CONCURRENCY} fetches in flight"}
    try:
        result = fetch(
            url,
            success_selectors=selectors,
            device_class=device,
            timeout=timeout,
            max_attempts=max_attempts,
            enable_playwright=_as_bool(params.get("playwright"), True),
            enable_phase0=_as_bool(params.get("phase0"), True),
            enable_extraction=_as_bool(params.get("extraction"), True),
            enable_retry=_as_bool(params.get("retry"), True),
        )
    except Exception as e:
        LOG.exception("fetch failed for %s", url)
        return 500, {"error": f"{type(e).__name__}: {e}"}
    finally:
        _slots.release()

    payload = result.to_dict()
    payload["content"] = result.content
    if wrap:
        # The engine's own untrusted-content envelope, with the prompt-injection
        # verdict attached. Worth requesting when the caller pipes this into
        # an LLM.
        try:
            payload["untrusted_text"] = result.to_untrusted_text()
        except Exception:
            payload["untrusted_text"] = result.content
    return (200 if result.ok else 502), payload


class Handler(BaseHTTPRequestHandler):
    server_version = "insane-api"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):  # route access logs through logging
        LOG.info("%s - %s", self.address_string(), fmt % a)

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass  # caller hung up mid-transfer; nothing to salvage

    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path in ("/", "/usage"):
            return self._send(200, USAGE)
        if parts.path == "/health":
            return self._send(200, {
                "ok": True,
                "cdp_mode": CDP_MODE,
                "cdp_url": os.environ.get("INSANE_CDP_URL", ""),
                "max_concurrency": MAX_CONCURRENCY,
            })
        if parts.path == "/fetch":
            code, payload = _run_fetch(_params_from_query(parts.query))
            return self._send(code, payload)
        return self._send(404, {"error": "not found", "try": "/usage"})

    def do_POST(self):
        parts = urlsplit(self.path)
        if parts.path != "/fetch":
            return self._send(404, {"error": "not found", "try": "/usage"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, {"error": "bad Content-Length"})
        if length > MAX_BODY_BYTES:
            return self._send(413, {"error": "body too large"})
        raw = self.rfile.read(length) if length else b"{}"
        try:
            params = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return self._send(400, {"error": f"invalid JSON body: {e}"})
        if not isinstance(params, dict):
            return self._send(400, {"error": "body must be a JSON object"})
        code, payload = _run_fetch(params)
        return self._send(code, payload)


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("INSANE_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    LOG.info(
        "starting on :%d cdp_mode=%s cdp_url=%s max_concurrency=%d",
        PORT, CDP_MODE, os.environ.get("INSANE_CDP_URL", "-"), MAX_CONCURRENCY,
    )
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
