"""Redirect the vendored engine's browser fallback onto the CloakBrowser container.

Done as an import-time monkeypatch rather than an edit to `vendor/engine/`, so
the vendored tree stays a verbatim copy of upstream MIT source and can be
re-synced with a plain `cp` when insane-search releases a new version. Four
functions are swapped:

  _run_node_template()        → speak CDP instead of spawning `node`
  _chrome_channel_available() → stop gating on a local node/npx/Chrome install
  _pick_executor()            → stop routing to the Claude-only MCP executor
  run_playwright_fallback()   → same, for profile-forced executor names

All four keep their original behaviour when INSANE_CDP_URL is unset, so the
module is safe to import in an environment without the container.
"""
from __future__ import annotations

import os

from engine import executor as _executor

from cloak_executor import run_via_cdp

_orig_run_node_template = _executor._run_node_template
_orig_chrome_channel_available = _executor._chrome_channel_available
_orig_pick_executor = _executor._pick_executor
_orig_run_playwright_fallback = _executor.run_playwright_fallback

# Upstream reserves these two executor names for Playwright MCP, which only a
# Claude session can drive — `run_playwright_fallback` refuses them outright
# and burns an attempt. This service has a real headed browser on tap, so the
# JS-execution capability those names stand for is better served by the CDP
# path than by an error string.
_MCP_TO_REAL = {
    "playwright_mcp": "playwright_real_chrome",
    "playwright_mcp_mobile": "playwright_mobile_chrome",
}


def _cdp_url() -> str:
    return os.environ.get("INSANE_CDP_URL", "").strip()


def _run_node_template(template: str, args: dict, timeout: int = 90):
    cdp = _cdp_url()
    if not cdp:
        return _orig_run_node_template(template, args, timeout=timeout)
    return run_via_cdp(cdp, template, args, timeout=timeout)


def _chrome_channel_available() -> bool:
    # Upstream probes for a local node + npx because it shells out to a JS
    # template. In CDP mode the browser lives in another container, so that
    # probe would veto a fallback that is in fact available.
    if _cdp_url():
        return True
    return _orig_chrome_channel_available()


def _pick_executor(capabilities, device_class):
    choice = _orig_pick_executor(capabilities, device_class)
    if not _cdp_url():
        return choice
    return _MCP_TO_REAL.get(choice, choice)


def run_playwright_fallback(url, *, force_executor=None, **kwargs):
    # A WAF profile's `fallback_when_challenge` list can name an MCP executor
    # directly, bypassing _pick_executor entirely — rewrite it here too.
    if _cdp_url() and force_executor:
        force_executor = _MCP_TO_REAL.get(force_executor, force_executor)
    return _orig_run_playwright_fallback(url, force_executor=force_executor, **kwargs)


def install() -> bool:
    """Patch the engine. Returns True when running in CDP mode."""
    _executor._run_node_template = _run_node_template
    _executor._chrome_channel_available = _chrome_channel_available
    _executor._pick_executor = _pick_executor
    _executor.run_playwright_fallback = run_playwright_fallback
    return bool(_cdp_url())
