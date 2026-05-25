/**
 * Regression test: tracker.js must write te_uid cookie eagerly at page load
 * (not deferred to first user interaction). Bug fixed in Stream A.6.
 *
 * Root cause (A.5 audit): tracker.js generated a userId UUID at module init
 * but only wrote the te_uid cookie inside a setOnInteraction listener (fired
 * on first click or scroll). experiments.js called getCookie('te_uid') on the
 * first impression (before any interaction) and found an empty cookie, so it
 * minted its own ephemeral UUID. Once the user scrolled/clicked, tracker.js
 * wrote the REAL te_uid (a different UUID). From that point every event used
 * the tracker's UUID. Same user, two distinct IDs → two different bucket
 * assignments in the same page session.
 *
 * Fix: tracker.js now writes te_uid synchronously in initUserIdentity() for
 * new users (no more setOnInteraction deferral for new users).
 *
 * These tests assert the fixed behaviour and are designed to catch any future
 * regression that re-introduces the deferral.
 *
 * Test strategy:
 *   - Load tracker.js with TRACKER_CONFIG.enabled=false so init() short-
 *     circuits before registering any event listeners or firing pageview.
 *     This lets us examine initUserIdentity() in isolation by exposing it
 *     via the Tracker test surface.
 *   - Separately load experiments.js and confirm it reads the same cookie.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const TRACKER_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/tracker.js'
);
const EXPERIMENTS_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/experiments.js'
);
const TRACKER_SOURCE = fs.readFileSync(TRACKER_PATH, 'utf8');

const require = createRequire(import.meta.url);

/**
 * Evaluate tracker.js IIFE in the current window context.
 * Caller must set window.TRACKER_CONFIG before calling this.
 */
function loadTracker() {
  // eslint-disable-next-line no-new-func
  new Function(TRACKER_SOURCE).call(window);
}

function clearTeCookies() {
  document.cookie = 'te_uid=; path=/; max-age=0';
  document.cookie = 'te_sn=; path=/; max-age=0';
}

function getCookieValue(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

beforeEach(() => {
  clearTeCookies();
  window.TRACKER_CONFIG = { endpoint: null, enabled: false, debug: false };
  delete window.Tracker;
  delete window.Experiments;
});

afterEach(() => {
  clearTeCookies();
  delete window.Tracker;
  delete window.Experiments;
  delete window.TRACKER_CONFIG;
});

// ---------------------------------------------------------------------------
// Core regression: cookie must be written without any user interaction
// ---------------------------------------------------------------------------

describe('tracker.js cookie timing — regression for A.5 bug', () => {
  it('writes te_uid cookie before any user interaction on a first-visit page load', () => {
    // No te_uid in cookies at this point (cleared in beforeEach).
    expect(getCookieValue('te_uid')).toBeNull();

    // Load tracker with init() disabled so the only thing that runs is
    // module-level setup and initUserIdentity() (called inside init()).
    // To exercise initUserIdentity() without triggering full init(), we
    // enable the tracker but mock the endpoint and suppress the fetch.
    window.TRACKER_CONFIG = { endpoint: 'https://example.test/events', enabled: true, debug: false };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true });
    loadTracker();
    vi.restoreAllMocks();

    // The fix: te_uid must already be set by the time any event fires.
    // No click or scroll has happened — the cookie must be present.
    const uid = getCookieValue('te_uid');
    expect(uid).not.toBeNull();
    expect(typeof uid).toBe('string');
    expect(uid.length).toBeGreaterThan(0);
  });

  it('te_uid written at load is a valid UUID-like string', () => {
    window.TRACKER_CONFIG = { endpoint: 'https://example.test/events', enabled: true, debug: false };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true });
    loadTracker();
    vi.restoreAllMocks();

    const uid = getCookieValue('te_uid');
    expect(uid).not.toBeNull();
    // UUID v4 pattern OR the fallback hex-32 pattern used when crypto.randomUUID
    // is unavailable. Both are non-empty strings without whitespace.
    expect(uid).toMatch(/^[0-9a-f-]+$/i);
  });

  it('te_sn session number cookie is also written eagerly for new users', () => {
    window.TRACKER_CONFIG = { endpoint: 'https://example.test/events', enabled: true, debug: false };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true });
    loadTracker();
    vi.restoreAllMocks();

    const sn = getCookieValue('te_sn');
    expect(sn).toBe('1');
  });

  it('returning user preserves existing te_uid without overwriting', () => {
    const existingUid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
    document.cookie = 'te_uid=' + existingUid + '; path=/';
    document.cookie = 'te_sn=3; path=/';

    window.TRACKER_CONFIG = { endpoint: 'https://example.test/events', enabled: true, debug: false };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true });
    loadTracker();
    vi.restoreAllMocks();

    // Returning user: te_uid must be the same value tracker found in the cookie.
    expect(getCookieValue('te_uid')).toBe(existingUid);
  });
});

// ---------------------------------------------------------------------------
// Cross-module check: experiments.js reads the same UID that tracker wrote
// ---------------------------------------------------------------------------

describe('experiments.js reads the te_uid that tracker.js wrote', () => {
  it('getOrMintUid in experiments.js returns the tracker-written te_uid, not an ephemeral id', () => {
    // Step 1: load tracker (which writes te_uid eagerly for a new user).
    window.TRACKER_CONFIG = { endpoint: 'https://example.test/events', enabled: true, debug: false };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true });
    loadTracker();
    vi.restoreAllMocks();

    const trackerWrittenUid = getCookieValue('te_uid');
    expect(trackerWrittenUid).not.toBeNull();

    // Step 2: load experiments.js AFTER tracker has run (as it would in the
    // browser with <script src="tracker.js"> before <script src="experiments.js">).
    delete require.cache[EXPERIMENTS_PATH];
    const Experiments = require(EXPERIMENTS_PATH);

    // Step 3: set up a minimal active config so getVariant() actually calls
    // getOrMintUid() and resolves a variant (not null).
    const configEl = document.createElement('script');
    configEl.id = 'experiments-config';
    configEl.type = 'application/json';
    configEl.textContent = JSON.stringify({
      experiments: [
        {
          id: 'timing_test_exp',
          status: 'active',
          variants: [
            { id: 'control', traffic: 50 },
            { id: 'treatment', traffic: 50 },
          ],
        },
      ],
    });
    document.body.appendChild(configEl);

    // The variant that experiments.js resolves for the tracker-written uid.
    const variantForTrackerUid = Experiments.resolveVariant(
      JSON.parse(configEl.textContent),
      trackerWrittenUid,
      'timing_test_exp'
    );
    expect(['control', 'treatment']).toContain(variantForTrackerUid);

    // The variant that getAllAssignments() resolves (which reads from the cookie).
    const assignments = Experiments.getAllAssignments();
    expect(assignments.timing_test_exp).toBe(variantForTrackerUid);

    // Clean up DOM.
    document.body.removeChild(configEl);
  });

  it('same uid produces same variant across first impression and later events', () => {
    // Simulate two sequential calls to getOrMintUid() — the first represents
    // the impression event, the second represents a click event. With the bug,
    // the first call found no cookie and minted an ephemeral id, while the
    // second found the real cookie. With the fix, both calls find the same cookie.

    window.TRACKER_CONFIG = { endpoint: 'https://example.test/events', enabled: true, debug: false };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true });
    loadTracker();
    vi.restoreAllMocks();

    const trackerWrittenUid = getCookieValue('te_uid');
    expect(trackerWrittenUid).not.toBeNull();

    delete require.cache[EXPERIMENTS_PATH];
    const Experiments = require(EXPERIMENTS_PATH);

    const cfg = {
      experiments: [
        {
          id: 'stability_test',
          status: 'active',
          variants: [
            { id: 'control', traffic: 50 },
            { id: 'treatment', traffic: 50 },
          ],
        },
      ],
    };

    // Wire the config into the DOM so getVariant() can read it.
    const configEl = document.createElement('script');
    configEl.id = 'experiments-config';
    configEl.type = 'application/json';
    configEl.textContent = JSON.stringify(cfg);
    document.body.appendChild(configEl);

    // Simulate: first impression call, then a later click call (same page load).
    // No user interaction has fired — with the OLD code the first call would
    // find no te_uid cookie and mint an ephemeral id, producing a potentially
    // different variant than the second call (after the real cookie was written).
    // With the fix the cookie is already set so both calls use the real uid.
    const variantOnFirstImpression = Experiments.getVariant('stability_test');
    const variantOnLaterClick = Experiments.getVariant('stability_test');

    // Both calls must resolve the same variant.
    expect(variantOnFirstImpression).toBe(variantOnLaterClick);
    expect(['control', 'treatment']).toContain(variantOnFirstImpression);

    // The variant resolved from the cookie uid must match what resolveVariant
    // returns when given the uid directly (proves it used the cookie, not ephemeral).
    const expectedVariant = Experiments.resolveVariant(cfg, trackerWrittenUid, 'stability_test');
    expect(variantOnFirstImpression).toBe(expectedVariant);

    document.body.removeChild(configEl);
  });
});
