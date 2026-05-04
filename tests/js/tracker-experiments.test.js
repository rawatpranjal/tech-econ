/**
 * Tests for the Phase-7 server-side hookup in static/js/tracker.js:
 * `getExperimentAssignments` reads window.Experiments.getAllAssignments()
 * and returns a string->string map; `track()` attaches the result as
 * `event.exp` when non-empty, omits the field when empty.
 *
 * The tracker IIFE auto-runs init() on load, which depends on a bunch of
 * browser APIs and TRACKER_CONFIG. We sidestep all that by:
 *   1. Setting TRACKER_CONFIG.enabled = false BEFORE evaluating the script,
 *      so init() short-circuits and no listeners register.
 *   2. Driving the helpers directly via the underscored test surface
 *      (Tracker._getExperimentAssignments, Tracker._hasAnyAssignment).
 *   3. For the track() integration test, we manually unblock sessionId
 *      via document.cookie + re-eval the script with enabled=true.
 *
 * No real network. No DOM mutation outside what the IIFE itself does.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/tracker.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

/**
 * Re-evaluating the IIFE wipes any prior window.Tracker binding.
 * Caller controls window.TRACKER_CONFIG and window.Experiments before
 * calling this so the loaded module observes the desired environment.
 */
function loadTracker() {
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

beforeEach(() => {
  // Default: tracker disabled so init() short-circuits. Individual tests
  // that exercise track() override this.
  window.TRACKER_CONFIG = { endpoint: null, enabled: false, debug: false };
  delete window.Tracker;
  delete window.Experiments;
});

afterEach(() => {
  delete window.Tracker;
  delete window.Experiments;
  delete window.TRACKER_CONFIG;
});

// --------------------------------------------------------------------------
// _getExperimentAssignments
// --------------------------------------------------------------------------

describe('_getExperimentAssignments', () => {
  it('returns {} when window.Experiments is undefined', () => {
    loadTracker();
    expect(window.Tracker._getExperimentAssignments()).toEqual({});
  });

  it('returns {} when getAllAssignments is not a function', () => {
    window.Experiments = { getAllAssignments: 'not-a-function' };
    loadTracker();
    expect(window.Tracker._getExperimentAssignments()).toEqual({});
  });

  it('returns {} when getAllAssignments returns null', () => {
    window.Experiments = { getAllAssignments: () => null };
    loadTracker();
    expect(window.Tracker._getExperimentAssignments()).toEqual({});
  });

  it('returns {} when getAllAssignments returns an empty object', () => {
    window.Experiments = { getAllAssignments: () => ({}) };
    loadTracker();
    expect(window.Tracker._getExperimentAssignments()).toEqual({});
  });

  it('returns the map verbatim when valid', () => {
    window.Experiments = {
      getAllAssignments: () => ({
        homepage_row_mmr_vs_baseline: 'treatment',
        search_intent_boost: 'control',
      }),
    };
    loadTracker();
    expect(window.Tracker._getExperimentAssignments()).toEqual({
      homepage_row_mmr_vs_baseline: 'treatment',
      search_intent_boost: 'control',
    });
  });

  it('drops non-string keys/values defensively', () => {
    window.Experiments = {
      getAllAssignments: () => ({
        valid_exp: 'treatment',
        bad_value_null: null,
        bad_value_number: 42,
        bad_value_object: { foo: 'bar' },
      }),
    };
    loadTracker();
    // Only the string->string entry survives.
    expect(window.Tracker._getExperimentAssignments()).toEqual({
      valid_exp: 'treatment',
    });
  });

  it('returns {} when getAllAssignments throws', () => {
    window.Experiments = {
      getAllAssignments: () => {
        throw new Error('boom');
      },
    };
    loadTracker();
    expect(window.Tracker._getExperimentAssignments()).toEqual({});
  });

  it('does not crawl prototype chain', () => {
    // If Experiments.getAllAssignments returns an object whose prototype
    // has extra keys, we should ignore them. Pure-data reading.
    function FakeMap() {
      this.real_exp = 'treatment';
    }
    FakeMap.prototype.injected = 'should-not-appear';
    window.Experiments = { getAllAssignments: () => new FakeMap() };
    loadTracker();
    const out = window.Tracker._getExperimentAssignments();
    expect(out).toEqual({ real_exp: 'treatment' });
    expect(out.injected).toBeUndefined();
  });
});

// --------------------------------------------------------------------------
// _hasAnyAssignment
// --------------------------------------------------------------------------

describe('_hasAnyAssignment', () => {
  it('returns false for empty / null / undefined', () => {
    loadTracker();
    expect(window.Tracker._hasAnyAssignment({})).toBe(false);
    expect(window.Tracker._hasAnyAssignment(null)).toBe(false);
    expect(window.Tracker._hasAnyAssignment(undefined)).toBe(false);
  });

  it('returns true when at least one own key exists', () => {
    loadTracker();
    expect(window.Tracker._hasAnyAssignment({ exp1: 'a' })).toBe(true);
  });
});

// --------------------------------------------------------------------------
// track() — integration: event.exp attached when assignments exist
// --------------------------------------------------------------------------

describe('track() event shape', () => {
  /**
   * Drive track() and capture the event that gets queued by intercepting
   * fetch (which flush() calls). We rely on flush() to serialise the
   * queue into a JSON payload we can parse and inspect.
   */
  function driveAndCaptureEvent(experimentSetup) {
    // Real-ish config: enabled, with an endpoint we mock.
    window.TRACKER_CONFIG = {
      endpoint: 'https://example.test/events',
      enabled: true,
      debug: false,
    };
    if (experimentSetup) experimentSetup();

    // jsdom doesn't always have crypto.randomUUID; tracker has a fallback,
    // but ensure document.cookie is read-write (it is in jsdom by default).
    let captured = null;
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((_url, opts) => {
      captured = JSON.parse(opts.body);
      return Promise.resolve({ ok: true });
    });

    loadTracker();
    // The IIFE wires init() on DOMContentLoaded OR runs it immediately if
    // readyState !== 'loading'. In jsdom readyState is 'complete', so init()
    // already ran. That sets sessionId so track() works.

    window.Tracker.track('test_event', { foo: 'bar' });
    window.Tracker.flush();
    fetchSpy.mockRestore();
    return captured;
  }

  it('omits event.exp when no Experiments global is loaded', () => {
    const payload = driveAndCaptureEvent();
    // Find the synthetic event we triggered (init() also fires a 'pageview'
    // and sometimes a 'sequence'; we want our 'test_event').
    const ours = (payload.events || []).find((e) => e.t === 'test_event');
    expect(ours).toBeDefined();
    expect(ours.exp).toBeUndefined();
  });

  it('attaches event.exp when assignments are non-empty', () => {
    const payload = driveAndCaptureEvent(() => {
      window.Experiments = {
        getAllAssignments: () => ({
          homepage_row_mmr_vs_baseline: 'treatment',
        }),
      };
    });
    const ours = (payload.events || []).find((e) => e.t === 'test_event');
    expect(ours).toBeDefined();
    expect(ours.exp).toEqual({
      homepage_row_mmr_vs_baseline: 'treatment',
    });
  });

  it('omits event.exp when getAllAssignments returns {}', () => {
    const payload = driveAndCaptureEvent(() => {
      window.Experiments = { getAllAssignments: () => ({}) };
    });
    const ours = (payload.events || []).find((e) => e.t === 'test_event');
    expect(ours).toBeDefined();
    expect(ours.exp).toBeUndefined();
  });
});
