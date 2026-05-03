/**
 * Tests for static/js/debug-score.js (?debug=1 score overlay).
 *
 * Same loader pattern as because-you-viewed.test.js — load the IIFE
 * source via `new Function(SRC).call(window)`. Each test re-loads to
 * isolate window.DebugScore.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/debug-score.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

function loadScript() {
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

let DebugScore;
beforeEach(() => {
  delete window.DebugScore;
  document.body.innerHTML = '';
  loadScript();
  DebugScore = window.DebugScore;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('DebugScore — module surface', () => {
  it('exposes the documented public API', () => {
    expect(DebugScore).toBeDefined();
    expect(typeof DebugScore.init).toBe('function');
    expect(typeof DebugScore.isDebugEnabled).toBe('function');
    expect(typeof DebugScore.buildScoreLookup).toBe('function');
    expect(typeof DebugScore.formatScore).toBe('function');
    expect(typeof DebugScore.injectBadge).toBe('function');
    expect(typeof DebugScore.applyOverlay).toBe('function');
  });
});

describe('isDebugEnabled', () => {
  it('returns true for ?debug=1', () => {
    expect(DebugScore.isDebugEnabled('?debug=1')).toBe(true);
  });

  it('accepts the string "true" as well', () => {
    expect(DebugScore.isDebugEnabled('?debug=true')).toBe(true);
    expect(DebugScore.isDebugEnabled('?debug=yes')).toBe(true);
  });

  it('is case-insensitive', () => {
    expect(DebugScore.isDebugEnabled('?debug=TRUE')).toBe(true);
  });

  it('returns false for missing or empty', () => {
    expect(DebugScore.isDebugEnabled('')).toBe(false);
    expect(DebugScore.isDebugEnabled('?other=1')).toBe(false);
    expect(DebugScore.isDebugEnabled('?debug=')).toBe(false);
  });

  it('returns false for non-string input', () => {
    expect(DebugScore.isDebugEnabled(null)).toBe(false);
    expect(DebugScore.isDebugEnabled(undefined)).toBe(false);
    expect(DebugScore.isDebugEnabled(123)).toBe(false);
  });

  it('does not match unrelated values', () => {
    expect(DebugScore.isDebugEnabled('?debug=0')).toBe(false);
    expect(DebugScore.isDebugEnabled('?debug=false')).toBe(false);
  });
});

describe('buildScoreLookup', () => {
  it('returns empty object for null/non-array input', () => {
    expect(DebugScore.buildScoreLookup(null)).toEqual({});
    expect(DebugScore.buildScoreLookup(undefined)).toEqual({});
    expect(DebugScore.buildScoreLookup({})).toEqual({});
  });

  it('lowercases names as keys', () => {
    var lookup = DebugScore.buildScoreLookup([
      { name: 'Causal Inference', model_score: 0.5 },
    ]);
    expect(lookup['causal inference']).toBe(0.5);
    expect(lookup['Causal Inference']).toBeUndefined();
  });

  it('skips entries without a model_score number', () => {
    var lookup = DebugScore.buildScoreLookup([
      { name: 'OK', model_score: 0.42 },
      { name: 'NoScore' },
      { name: 'BadScore', model_score: 'high' },
      { name: 'NullScore', model_score: null },
    ]);
    expect(Object.keys(lookup)).toEqual(['ok']);
  });

  it('skips entries without a name string', () => {
    var lookup = DebugScore.buildScoreLookup([
      { model_score: 0.5 },
      { name: 123, model_score: 0.5 },
      { name: 'ValidName', model_score: 0.5 },
    ]);
    expect(Object.keys(lookup)).toEqual(['validname']);
  });
});

describe('formatScore', () => {
  it('returns "?" for non-numeric input', () => {
    expect(DebugScore.formatScore(null)).toBe('?');
    expect(DebugScore.formatScore(undefined)).toBe('?');
    expect(DebugScore.formatScore('0.5')).toBe('?');
    expect(DebugScore.formatScore(NaN)).toBe('?');
  });

  it('formats zero as "0"', () => {
    expect(DebugScore.formatScore(0)).toBe('0');
  });

  it('formats typical mid-range scores to 3 decimals', () => {
    expect(DebugScore.formatScore(0.42)).toBe('0.420');
    expect(DebugScore.formatScore(0.123456)).toBe('0.123');
  });

  it('formats scores >= 1 to 2 decimals', () => {
    expect(DebugScore.formatScore(1.0)).toBe('1.00');
    expect(DebugScore.formatScore(2.5)).toBe('2.50');
  });

  it('uses scientific notation for tiny scores', () => {
    expect(DebugScore.formatScore(0.0001)).toMatch(/e/);
  });
});

describe('injectBadge', () => {
  it('appends a badge as a child of the card', () => {
    document.body.innerHTML = '<div class="card-header">Card</div>';
    var card = document.body.firstElementChild;
    var added = DebugScore.injectBadge(card, 0.42);
    expect(added).toBe(true);
    expect(card.querySelectorAll('.debug-score-badge').length).toBe(1);
    expect(card.querySelector('.debug-score-badge').textContent).toBe('0.420');
  });

  it('is idempotent — calling twice does not duplicate', () => {
    document.body.innerHTML = '<div></div>';
    var card = document.body.firstElementChild;
    DebugScore.injectBadge(card, 0.5);
    var added = DebugScore.injectBadge(card, 0.5);
    expect(added).toBe(false);
    expect(card.querySelectorAll('.debug-score-badge').length).toBe(1);
  });

  it('returns false for missing card', () => {
    expect(DebugScore.injectBadge(null, 0.5)).toBe(false);
    expect(DebugScore.injectBadge(undefined, 0.5)).toBe(false);
  });

  it('prefers heading anchor when present', () => {
    document.body.innerHTML =
      '<div><h3 class="package-name">Foo</h3><p>desc</p></div>';
    var card = document.body.firstElementChild;
    DebugScore.injectBadge(card, 0.5);
    var badge = card.querySelector('.debug-score-badge');
    expect(badge).not.toBeNull();
    // Should be inside the h3, not a sibling of h3
    expect(badge.parentElement.tagName).toBe('H3');
  });
});

describe('applyOverlay', () => {
  it('walks [data-name] cards and adds a badge to each known one', () => {
    document.body.innerHTML =
      '<div data-name="foo"><h3>Foo</h3></div>' +
      '<div data-name="bar"><h3>Bar</h3></div>' +
      '<div data-name="baz"><h3>Baz</h3></div>';
    var lookup = { foo: 0.9, bar: 0.5 };
    var added = DebugScore.applyOverlay(document.body, lookup);
    expect(added).toBe(2);
    expect(document.querySelectorAll('.debug-score-badge').length).toBe(2);
    var bazCard = document.body.children[2];
    expect(bazCard.querySelector('.debug-score-badge')).toBeNull();
  });

  it('returns 0 for empty input or empty lookup', () => {
    document.body.innerHTML = '';
    expect(DebugScore.applyOverlay(document.body, { foo: 1 })).toBe(0);

    document.body.innerHTML = '<div data-name="foo"></div>';
    expect(DebugScore.applyOverlay(document.body, {})).toBe(0);
  });

  it('lowercases data-name during lookup', () => {
    document.body.innerHTML = '<div data-name="MIXED CASE"><h3>Hi</h3></div>';
    var added = DebugScore.applyOverlay(document.body, { 'mixed case': 0.7 });
    expect(added).toBe(1);
  });

  it('handles re-runs idempotently across multiple invocations', () => {
    document.body.innerHTML = '<div data-name="foo"><h3>Foo</h3></div>';
    var lookup = { foo: 0.5 };
    DebugScore.applyOverlay(document.body, lookup);
    DebugScore.applyOverlay(document.body, lookup);
    DebugScore.applyOverlay(document.body, lookup);
    expect(document.querySelectorAll('.debug-score-badge').length).toBe(1);
  });
});

describe('init — end-to-end', () => {
  // jsdom won't let us redefine window.location.search, so we pass the
  // search string explicitly through init({ search }) — that path is
  // exposed for exactly this purpose.

  it('is a no-op when ?debug=1 is missing', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.reject(new Error('should not be called')),
    );
    document.body.innerHTML = '<div data-name="foo"><h3>Foo</h3></div>';
    await DebugScore.init({ search: '' });
    expect(document.querySelectorAll('.debug-score-badge').length).toBe(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('renders badges when ?debug=1 is set', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            documents: [
              { name: 'Foo', model_score: 0.42 },
              { name: 'Bar', model_score: 0.99 },
            ],
          }),
      }),
    );
    document.body.innerHTML =
      '<div data-name="foo"><h3>Foo</h3></div>' +
      '<div data-name="bar"><h3>Bar</h3></div>' +
      '<div data-name="missing"><h3>Missing</h3></div>';
    await DebugScore.init({ search: '?debug=1' });
    var badges = document.querySelectorAll('.debug-score-badge');
    expect(badges.length).toBe(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('is silent on fetch failure', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.reject(new Error('network')),
    );
    document.body.innerHTML = '<div data-name="foo"><h3>Foo</h3></div>';
    // Should not throw — silent failure.
    await expect(DebugScore.init({ search: '?debug=1' })).resolves.toBeUndefined();
    expect(document.querySelectorAll('.debug-score-badge').length).toBe(0);
  });
});
