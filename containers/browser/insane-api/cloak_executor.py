"""CloakBrowser CDP executor — drop-in replacement for the Node/Playwright path.

Upstream insane-search shells out to `node engine/templates/*.js`, which needs
a per-machine Chrome install, a writable profile dir, and an X display for the
headed mode anti-bot systems demand. None of that is available to every user of
a shared headless server.

This module speaks CDP to the shared CloakBrowser container instead. The
stealth work happens there, in a Chromium with source-level C++ fingerprint
patches, so the launch-time evasion stack upstream reaches for (patchright,
playwright-extra + stealth plugin) is redundant here and is not used.

It deliberately emits the SAME JSON envelope the JS templates emit, so
`executor._parse_envelope`, the validators, the curl_cffi cookie bridge and the
render-merge innerText path downstream all keep working untouched. The only
upstream edit needed is a single dispatch line in `_run_node_template`.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

# Matches the JS template's default. Kept identical so behaviour does not
# silently diverge between the two executors.
MOBILE_DEVICE = "iPhone 13 Pro"


def _fingerprint_seed(profile_dir: str) -> int:
    """cloakserve gives each `fingerprint` seed its own browser identity.

    Deriving it from the caller's profileDir (which upstream already hashes
    per-host) keeps one site pinned to one identity, instead of handing a WAF
    a different fingerprint on every retry — the pattern that gets a session
    flagged mid-challenge.
    """
    digest = hashlib.sha256(profile_dir.encode("utf-8", "ignore")).hexdigest()
    return int(digest[:8], 16)


def _endpoint(base_url: str, profile_dir: str) -> str:
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}fingerprint={_fingerprint_seed(profile_dir)}"


def _envelope(context, page, html: str, resp, automation: str) -> str:
    """Same shape the JS templates write to stdout."""
    try:
        cookies = [
            {"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain")}
            for c in context.cookies()
        ]
    except Exception:
        cookies = []
    try:
        user_agent = page.evaluate("() => navigator.userAgent")
    except Exception:
        user_agent = ""
    try:
        final_url = page.url
    except Exception:
        final_url = ""
    try:
        status = resp.status if resp is not None else 0
    except Exception:
        status = 0
    try:
        # SPAs often expose visible text only through innerText; upstream's
        # render-merge step compares it against the parsed body text.
        inner_text = page.evaluate("() => document.body && document.body.innerText || ''")
    except Exception:
        inner_text = ""
    return json.dumps(
        {
            "html": html,
            "finalUrl": final_url,
            "status": status,
            "cookies": cookies,
            "userAgent": user_agent,
            "automation": automation,
            "innerText": inner_text,
        },
        ensure_ascii=False,
    )


def run_via_cdp(
    cdp_url: str,
    template: str,
    args: dict[str, Any],
    timeout: int = 90,
) -> tuple[int, str, str]:
    """Return (returncode, stdout, stderr) exactly like `_run_node_template`."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # pragma: no cover - import guard
        return 1, "", f"playwright unavailable: {type(e).__name__}: {e}"

    url = args.get("url")
    if not url:
        return 2, "", "missing url"

    # Defence in depth. Upstream enforces its SSRF guard only in the curl
    # transport, so a URL that reaches the browser executor — via a profile's
    # URL transform, or a caller that skipped the API — has never been checked
    # against private/loopback/link-local/metadata targets.
    try:
        from engine import safety

        allowed, reason = safety.classify_url(url, allow_private=safety.allow_private_default())
        if not allowed:
            return 1, "", f"blocked target: {reason}"
    except ImportError:
        pass  # standalone use without the engine on the path

    profile_dir = args.get("profileDir") or "/tmp/.insane_pw_profile"
    wait_selector = args.get("waitSelector")
    # Upstream passes milliseconds in args["timeout"]; `timeout` is seconds.
    timeout_ms = int(args.get("timeout") or timeout * 1000)
    is_mobile = "mobile" in template

    deadline = time.monotonic() + timeout_ms / 1000.0

    def remaining(cap_ms: int) -> float:
        """Shared budget across warmup + main + reload, so the first navigation
        cannot eat the whole allowance and starve the rest."""
        left = (deadline - time.monotonic()) * 1000.0
        return max(1000.0, min(float(cap_ms), left))

    browser = None
    context = None
    page = None
    owns_context = False
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(
                _endpoint(cdp_url, profile_dir),
                timeout=min(timeout_ms, 30000),
            )
            if is_mobile:
                # channel:'chrome' + device descriptor upstream keeps a real
                # Chrome TLS fingerprint while emulating mobile at the HTTP
                # layer. Here the TLS stack is CloakBrowser's patched Chromium,
                # so only the emulation half is needed.
                context = browser.new_context(**pw.devices[MOBILE_DEVICE])
                owns_context = True
            else:
                context = browser.contexts[0] if browser.contexts else browser.new_context(no_viewport=True)
                owns_context = not browser.contexts
            page = context.pages[0] if context.pages else context.new_page()

            # Warmup hop: land on the site root first so an Akamai-style sensor
            # can run and set a resolved session cookie. Going straight to a
            # deep URL is the classic first-hit rejection pattern.
            try:
                from urllib.parse import urlsplit

                parts = urlsplit(url)
                root = f"{parts.scheme}://{parts.netloc}/"
                if root != url:
                    page.goto(root, wait_until="domcontentloaded", timeout=remaining(90000))
                    page.wait_for_timeout(3500)
            except Exception:
                pass  # warmup is best-effort

            resp = page.goto(url, wait_until="domcontentloaded", timeout=remaining(90000))
            page.wait_for_timeout(2500)

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=remaining(20000))
                except Exception:
                    # Selector still missing — one hard reload, in case the
                    # first hit landed on a challenge page that has since
                    # cleared.
                    try:
                        resp = page.reload(wait_until="domcontentloaded", timeout=remaining(90000))
                        page.wait_for_timeout(2000)
                        try:
                            page.wait_for_selector(wait_selector, timeout=remaining(10000))
                        except Exception:
                            pass  # caller validates the HTML regardless
                    except Exception:
                        pass
            else:
                page.wait_for_timeout(2000)

            html = page.content()
            return 0, _envelope(context, page, html, resp, "cloakbrowser-cdp"), ""
    except Exception as e:
        return 1, "", f"{type(e).__name__}: {e}"[:300]
    finally:
        # Tear down only what we opened. cloakserve hands out a browser per
        # fingerprint seed and other callers on this host may hold their own.
        try:
            if page is not None:
                page.close()
        except Exception:
            pass
        try:
            if owns_context and context is not None:
                context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
