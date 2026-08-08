#!/usr/bin/env node
/**
 * Generic Playwright fetcher — real Chrome channel (not bundled Chromium).
 *
 * PATCHED FOR the shared browser container — see ../README.md
 *   When INSANE_CDP_URL is set (or args.cdpUrl is passed) this connects to the
 *   shared CloakBrowser stealth Chromium container over CDP instead of
 *   launching a local Chrome. That container runs its own Xvfb, so the
 *   headed mode these anti-bot systems require works on a headless server
 *   with no X display, no GPU access, and no per-user Chrome install.
 *   With the variable unset the original local-launch behaviour is unchanged.
 *
 * Usage (driven by engine/executor.py):
 *   echo '{"url":"...", "profileDir":"/tmp/.p", "waitSelector":"article"}' | node playwright_real_chrome.js
 *
 * Outputs page HTML to stdout on success; errors to stderr with non-zero exit.
 *
 * NO-SITE-NAME RULE: this file must never branch on specific hostnames.
 * All site specifics come from the JSON input (url, waitSelector).
 *
 * Dependencies (install once on target machine):
 *   npm i -g playwright playwright-extra puppeteer-extra-plugin-stealth
 *   npx playwright install chrome    # system Chrome binary
 *   (CDP mode needs only `playwright` — no browser download required)
 */

const fs = require('fs');
const crypto = require('crypto');

// Drain stdout fully before exiting. `process.exit()` can truncate a large
// HTML payload because it does not wait for pending stdout I/O (Node docs).
function writeStdoutAsync(payload) {
  return new Promise((resolve, reject) => {
    process.stdout.write(payload, (err) => (err ? reject(err) : resolve()));
  });
}

// Structured envelope so the Python side can (a) validate on real status /
// final URL and (b) bridge the browser-cleared cookies + UA into curl_cffi.
async function buildEnvelope(ctx, page, html, resp, automation) {
  let cookies = [];
  try { cookies = (await ctx.cookies()).map((c) => ({ name: c.name, value: c.value, domain: c.domain })); } catch (_e) {}
  let userAgent = '';
  try { userAgent = await page.evaluate(() => navigator.userAgent); } catch (_e) {}
  let finalUrl = '';
  try { finalUrl = page.url(); } catch (_e) {}
  let status = 0;
  try { status = resp ? resp.status() : 0; } catch (_e) {}
  // innerText feeds the render-merge step: SPAs often expose visible text
  // only via innerText, which the extractor compares against the body text.
  let innerText = '';
  try { innerText = await page.evaluate(() => document.body && document.body.innerText || ''); } catch (_e) {}
  return JSON.stringify({ html, finalUrl, status, cookies, userAgent, automation, innerText });
}

async function readStdinJson() {
  return await new Promise((resolve, reject) => {
    let data = '';
    process.stdin.on('data', (c) => (data += c));
    process.stdin.on('end', () => {
      try { resolve(JSON.parse(data || '{}')); }
      catch (e) { reject(e); }
    });
    process.stdin.on('error', reject);
  });
}

// cloakserve multiplexes one Chrome process per `fingerprint` seed. Deriving
// the seed from profileDir keeps a retry on the same identity (and therefore
// the same cookie jar) instead of handing the WAF a brand new browser
// mid-challenge, which is exactly the pattern that gets a session flagged.
function cdpEndpoint(baseUrl, profileDir) {
  const seed = parseInt(
    crypto.createHash('sha256').update(String(profileDir)).digest('hex').slice(0, 8),
    16,
  );
  const sep = baseUrl.includes('?') ? '&' : '?';
  return `${baseUrl}${sep}fingerprint=${seed}`;
}

async function main() {
  const args = await readStdinJson();
  const url = args.url;
  if (!url) { process.stderr.write('missing url\n'); process.exit(2); }

  const profileDir = args.profileDir || '/tmp/.insane_pw_profile';
  const waitSelector = args.waitSelector || null;
  const timeoutMs = args.timeout || 60000;
  const headless = args.headless ?? false;     // Akamai/etc detect headless
  const viewport = args.viewport || { width: 1366, height: 900 };
  const cdpUrl = args.cdpUrl || process.env.INSANE_CDP_URL || '';

  let chromium;
  let automation = 'playwright';

  if (cdpUrl) {
    // CDP mode. The stealth work happens in the container's C++-patched
    // Chromium, so the launch-time evasion forks (patchright / stealth
    // plugin) are not just unnecessary here, they are dead weight — plain
    // playwright speaks CDP fine.
    try {
      ({ chromium } = require('playwright'));
    } catch (_e) {
      try { ({ chromium } = require('playwright-core')); }
      catch (_e2) { ({ chromium } = require('patchright')); }
    }
    automation = 'cloakbrowser-cdp';
  } else {
    try {
      // Patchright is a DROP-IN Playwright fork (same API) that closes the CDP
      // Runtime.enable leak Cloudflare/DataDome now detect. Preferred when
      // installed; it does its own patching, so NO stealth plugin is added.
      // Additive only: if patchright is absent we fall back to exactly the
      // previous playwright-extra(+stealth) → playwright behaviour.
      ({ chromium } = require('patchright'));
      automation = 'patchright';
    } catch (_e0) {
      try {
        ({ chromium } = require('playwright-extra'));
        const stealth = require('puppeteer-extra-plugin-stealth')();
        chromium.use(stealth);
        automation = 'playwright-extra+stealth';
      } catch (_e) {
        // Fallback to plain playwright (no stealth). Still uses channel:chrome.
        ({ chromium } = require('playwright'));
        automation = 'playwright';
      }
    }
  }

  let ctx;
  let browser;        // set in CDP mode only
  let page;
  try {
    if (cdpUrl) {
      browser = await chromium.connectOverCDP(cdpEndpoint(cdpUrl, profileDir), {
        timeout: Math.min(timeoutMs, 30000),
      });
      // Reuse the seed's existing default context so its cookie jar survives
      // across attempts; only fabricate one if the browser came up bare.
      ctx = browser.contexts()[0] || (await browser.newContext({ viewport: null }));
      page = ctx.pages()[0] || (await ctx.newPage());
    } else {
      // Patchright official best practice: channel:'chrome', headless:false,
      // no_viewport (JS: viewport:null), persistent context, and NO custom
      // headers/UA/flags. We only override viewport for patchright; plain
      // playwright keeps the fixed viewport it has always used.
      const ctxOpts = { channel: 'chrome', headless };
      if (automation === 'patchright') {
        ctxOpts.viewport = null;     // == no_viewport=True (use real window size)
      } else {
        ctxOpts.viewport = viewport;
      }
      ctx = await chromium.launchPersistentContext(profileDir, ctxOpts);
      page = await ctx.newPage();
    }
    // Single shared deadline across warmup + main + reload navigations so the
    // first nav can't eat the whole budget and starve the rest.
    const deadline = Date.now() + timeoutMs;
    const rem = (cap) => Math.max(1000, Math.min(cap || timeoutMs, deadline - Date.now()));

    // Warmup hop: visit the site root first so Akamai-style bot managers
    // can run their JS sensor and set a resolved session cookie. Direct
    // landing on a search/deep URL is the classic first-hit rejection pattern.
    // Use domcontentloaded (not networkidle) — many SPAs keep analytics/xhr
    // open indefinitely and would hit the 90s timeout.
    try {
      const urlObj = new URL(url);
      const rootUrl = `${urlObj.protocol}//${urlObj.host}/`;
      if (rootUrl !== url) {
        await page.goto(rootUrl, { waitUntil: 'domcontentloaded', timeout: rem(90000) });
        await page.waitForTimeout(3500);   // let sensor JS finish
      }
    } catch (_e) {
      // warmup is best-effort; continue even if it hiccups
    }

    // Main page — DOM loaded then give the sensor a moment.
    let mainResp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: rem(90000) });
    await page.waitForTimeout(2500);

    if (waitSelector) {
      try {
        await page.waitForSelector(waitSelector, { timeout: rem(20000) });
      } catch (_e) {
        // Selector still missing — try one hard reload in case the first hit
        // landed on a challenge page and the sensor has just cleared.
        try {
          mainResp = await page.reload({ waitUntil: 'domcontentloaded', timeout: rem(90000) });
          await page.waitForTimeout(2000);
          try {
            await page.waitForSelector(waitSelector, { timeout: rem(10000) });
          } catch (_e2) {
            // Still no luck — caller validates HTML anyway.
          }
        } catch (_e3) {
          // reload failed — proceed with whatever we have
        }
      }
    } else {
      // Without a positive-proof selector, give the sensor a couple more seconds.
      await page.waitForTimeout(2000);
    }

    const html = await page.content();
    const payload = await buildEnvelope(ctx, page, html, mainResp, automation);
    await writeStdoutAsync(payload);  // flush fully before any exit
    process.exitCode = 0;
    return;                           // let finally close ctx, then exit naturally
  } catch (e) {
    process.stderr.write(`${e.name || 'Error'}: ${e.message || e}\n`);
    process.exitCode = 1;
    return;
  } finally {
    if (cdpUrl) {
      // Measured against cloakserve 0.4.13: it hands out a NEW Chrome process
      // per CDP connection, so browser.close() tears down only our own and
      // leaves the multiplexer and every other caller untouched. The flip side
      // is that no cookie jar survives a disconnect — which is why the warmup
      // hop above has to happen inside this same connection.
      try { if (page) await page.close(); } catch (_e) {}
      try { if (browser) await browser.close(); } catch (_e) {}
    } else {
      try { if (ctx) await ctx.close(); } catch (_e) {}
    }
  }
}

main();
