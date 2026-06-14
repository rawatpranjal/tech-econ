/**
 * Tests for pure helpers in explore.js exposed via window.Explore._*:
 *   _slugify, _isNewItem, _isPopularItem, _getDailyHeroSeed,
 *   _selectDailyHero, _truncate, _getEngagementBadge
 *
 * Loaded via IIFE. explore.js calls init() only if window.DISCOVER_DATA_URLS
 * is set — we leave it undefined so no DOM work happens.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const EXPLORE_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/explore.js'
);
const EXPLORE_SOURCE = fs.readFileSync(EXPLORE_PATH, 'utf8');

function loadExplore() {
  // eslint-disable-next-line no-new-func
  new Function(EXPLORE_SOURCE).call(window);
}

beforeEach(() => {
  // Ensure DISCOVER_DATA_URLS is NOT set → init() returns early
  delete window.DISCOVER_DATA_URLS;
  delete window.Explore;
  // jsdom needs a minimal IntersectionObserver stub so the IIFE doesn't throw
  if (!window.IntersectionObserver) {
    window.IntersectionObserver = class {
      constructor() {}
      observe() {}
      disconnect() {}
    };
  }
  loadExplore();
});

afterEach(() => {
  delete window.Explore;
});

// ──────────────────────────────────────────────
// _slugify
// ──────────────────────────────────────────────
describe('Explore._slugify', () => {
  it('lowercases text', () => {
    expect(window.Explore._slugify('Hello World')).toBe('hello-world');
  });

  it('replaces special chars with hyphens', () => {
    expect(window.Explore._slugify('foo/bar.baz')).toBe('foo-bar-baz');
  });

  it('collapses consecutive non-alnum to single hyphen', () => {
    expect(window.Explore._slugify('foo  bar')).toBe('foo-bar');
  });

  it('strips leading and trailing hyphens', () => {
    expect(window.Explore._slugify('  hello  ')).toBe('hello');
  });

  it('preserves numbers', () => {
    expect(window.Explore._slugify('v1.5 model')).toBe('v1-5-model');
  });

  it('returns empty string for empty input', () => {
    expect(window.Explore._slugify('')).toBe('');
  });

  it('already-clean slug is unchanged', () => {
    expect(window.Explore._slugify('already-clean-123')).toBe('already-clean-123');
  });
});

// ──────────────────────────────────────────────
// _truncate
// ──────────────────────────────────────────────
describe('Explore._truncate', () => {
  it('returns empty string for falsy input', () => {
    expect(window.Explore._truncate(null, 10)).toBe('');
    expect(window.Explore._truncate('', 10)).toBe('');
    expect(window.Explore._truncate(undefined, 10)).toBe('');
  });

  it('returns string unchanged when shorter than limit', () => {
    expect(window.Explore._truncate('short', 100)).toBe('short');
  });

  it('returns string unchanged when exactly at limit', () => {
    expect(window.Explore._truncate('exact', 5)).toBe('exact');
  });

  it('truncates and appends ellipsis when over limit', () => {
    const result = window.Explore._truncate('This is too long', 7);
    expect(result).toMatch(/\.\.\.$/);
    expect(result.length).toBeLessThanOrEqual(10); // 7 chars + '...'
  });

  it('trims whitespace before appending ellipsis', () => {
    const result = window.Explore._truncate('Hello  ', 6);
    expect(result).not.toMatch(/ \.\.\.$/);
  });
});

// ──────────────────────────────────────────────
// _isPopularItem
// ──────────────────────────────────────────────
describe('Explore._isPopularItem', () => {
  it('returns true when model_score > 0.7', () => {
    expect(window.Explore._isPopularItem({ model_score: 0.8 })).toBe(true);
  });

  it('returns false when model_score exactly 0.7', () => {
    expect(window.Explore._isPopularItem({ model_score: 0.7 })).toBe(false);
  });

  it('returns false when model_score < 0.7', () => {
    expect(window.Explore._isPopularItem({ model_score: 0.5 })).toBe(false);
  });

  it('returns false when model_score missing', () => {
    expect(window.Explore._isPopularItem({})).toBe(false);
  });

  it('returns false when model_score is 0', () => {
    expect(window.Explore._isPopularItem({ model_score: 0 })).toBe(false);
  });
});

// ──────────────────────────────────────────────
// _isNewItem
// ──────────────────────────────────────────────
describe('Explore._isNewItem', () => {
  it('returns false when date_added missing', () => {
    expect(window.Explore._isNewItem({})).toBe(false);
  });

  it('returns true for date_added today', () => {
    const today = new Date().toISOString().slice(0, 10);
    expect(window.Explore._isNewItem({ date_added: today })).toBe(true);
  });

  it('returns true for date_added 4 days ago', () => {
    const d = new Date();
    d.setDate(d.getDate() - 4);
    expect(window.Explore._isNewItem({ date_added: d.toISOString().slice(0, 10) })).toBe(true);
  });

  it('returns false for date_added 6 days ago', () => {
    const d = new Date();
    d.setDate(d.getDate() - 6);
    expect(window.Explore._isNewItem({ date_added: d.toISOString().slice(0, 10) })).toBe(false);
  });

  it('returns false when date_added is null', () => {
    expect(window.Explore._isNewItem({ date_added: null })).toBe(false);
  });
});

// ──────────────────────────────────────────────
// _getDailyHeroSeed
// ──────────────────────────────────────────────
describe('Explore._getDailyHeroSeed', () => {
  it('returns a positive integer', () => {
    const seed = window.Explore._getDailyHeroSeed();
    expect(typeof seed).toBe('number');
    expect(seed).toBeGreaterThan(0);
    expect(Number.isInteger(seed)).toBe(true);
  });

  it('encodes YYYYMMDD: year * 10000 + month * 100 + day', () => {
    const today = new Date();
    const expected =
      today.getFullYear() * 10000 +
      (today.getMonth() + 1) * 100 +
      today.getDate();
    expect(window.Explore._getDailyHeroSeed()).toBe(expected);
  });

  it('is stable within the same day (two calls return same value)', () => {
    const a = window.Explore._getDailyHeroSeed();
    const b = window.Explore._getDailyHeroSeed();
    expect(a).toBe(b);
  });
});

// ──────────────────────────────────────────────
// _selectDailyHero
// ──────────────────────────────────────────────
describe('Explore._selectDailyHero', () => {
  const items = [
    { name: 'alpha' },
    { name: 'beta' },
    { name: 'gamma' },
  ];

  it('returns null for empty array', () => {
    expect(window.Explore._selectDailyHero([], 'carousel-1')).toBeNull();
  });

  it('returns null for null items', () => {
    expect(window.Explore._selectDailyHero(null, 'carousel-1')).toBeNull();
  });

  it('returns one of the items', () => {
    const hero = window.Explore._selectDailyHero(items, 'carousel-x');
    expect(items).toContain(hero);
  });

  it('is deterministic within the same day for the same carousel', () => {
    const hero1 = window.Explore._selectDailyHero(items, 'carousel-abc');
    const hero2 = window.Explore._selectDailyHero(items, 'carousel-abc');
    expect(hero1).toBe(hero2);
  });

  it('produces different heroes for different carousel IDs (usually)', () => {
    // With 3 items, carousel "a" vs "b" differ by 1 in charcode sum — should differ often
    const seen = new Set();
    for (const id of ['carousel-a', 'carousel-b', 'carousel-c', 'carousel-d']) {
      const hero = window.Explore._selectDailyHero(items, id);
      seen.add(hero.name);
    }
    // At least 2 different heroes across the 4 different IDs
    expect(seen.size).toBeGreaterThanOrEqual(2);
  });
});

// ──────────────────────────────────────────────
// _getEngagementBadge
// ──────────────────────────────────────────────
describe('Explore._getEngagementBadge', () => {
  it('returns empty string for plain item', () => {
    const badge = window.Explore._getEngagementBadge({ model_score: 0.3 });
    expect(badge).toBe('');
  });

  it('returns Popular badge when model_score > 0.7', () => {
    const badge = window.Explore._getEngagementBadge({ model_score: 0.9 });
    expect(badge).toContain('badge-popular');
    expect(badge).toContain('Popular');
  });

  it('returns New badge when recently added', () => {
    const today = new Date().toISOString().slice(0, 10);
    const badge = window.Explore._getEngagementBadge({ date_added: today, model_score: 0.1 });
    expect(badge).toContain('badge-new');
    expect(badge).toContain('New');
  });

  it('New takes priority over Popular', () => {
    const today = new Date().toISOString().slice(0, 10);
    const badge = window.Explore._getEngagementBadge({ date_added: today, model_score: 0.95 });
    expect(badge).toContain('badge-new');
    expect(badge).not.toContain('badge-popular');
  });
});

// ──────────────────────────────────────────────
// scoreCluster (via _scoreCluster)
// Note: scoreCluster reads from itemLookup (module-level map) — we test
// the structural scoring only (prioritized/deprioritized labels, item_count
// penalties). We supply clusters with no items (getClusterItems returns [])
// so engagement sampling falls through to 0.
// ──────────────────────────────────────────────

describe('Explore._scoreCluster', () => {
  it('is a function', () => {
    expect(typeof window.Explore._scoreCluster).toBe('function');
  });

  it('deprioritized label lowers score vs neutral', () => {
    const career = { id: 'c1', label: 'career portal jobs', item_count: 20 };
    const neutral = { id: 'c2', label: 'causal inference methods', item_count: 20 };
    const s1 = window.Explore._scoreCluster(career);
    const s2 = window.Explore._scoreCluster(neutral);
    // career has -50 penalty, neutral has +30 boost → neutral > career
    expect(s2).toBeGreaterThan(s1);
  });

  it('prioritized label raises score vs generic', () => {
    const generic = { id: 'g', label: 'general items', item_count: 20 };
    const tech = { id: 't', label: 'bayesian estimation', item_count: 20 };
    const sg = window.Explore._scoreCluster(generic);
    const st = window.Explore._scoreCluster(tech);
    // tech has +30, generic has 0 → tech > generic (ignoring random ≤20 noise)
    // use a wide margin since random adds up to 20
    expect(st - sg).toBeGreaterThan(5);
  });

  it('returns a number', () => {
    const c = { id: 'x', label: 'machine learning', item_count: 15 };
    expect(typeof window.Explore._scoreCluster(c)).toBe('number');
  });

  it('very large cluster (>100) gets penalty vs medium', () => {
    const big = { id: 'b', label: 'neutral thing', item_count: 150 };
    const med = { id: 'm', label: 'neutral thing', item_count: 25 };
    const sb = window.Explore._scoreCluster(big);
    const sm = window.Explore._scoreCluster(med);
    // big: -5 + random; medium: +10 + random — expect medium higher most of the time
    // check 10 times to reduce flakiness from random component
    let medWins = 0;
    for (let i = 0; i < 10; i++) {
      const rb = window.Explore._scoreCluster(big);
      const rm = window.Explore._scoreCluster(med);
      if (rm > rb) medWins++;
    }
    expect(medWins).toBeGreaterThanOrEqual(6);
  });
});

// ──────────────────────────────────────────────
// curatedSort (via _curatedSort)
// ──────────────────────────────────────────────

describe('Explore._curatedSort', () => {
  function makeClusters(n) {
    return Array.from({ length: n }, (_, i) => ({
      id: `c${i}`,
      label: `cluster ${i}`,
      item_count: 10 + i,
    }));
  }

  it('returns same number of clusters', () => {
    const clusters = makeClusters(9);
    const result = window.Explore._curatedSort(clusters);
    expect(result.length).toBe(9);
  });

  it('returns all original clusters (no duplicates)', () => {
    const clusters = makeClusters(6);
    const result = window.Explore._curatedSort(clusters);
    const ids = result.map(c => c.id);
    const unique = new Set(ids);
    expect(unique.size).toBe(6);
  });

  it('handles empty array', () => {
    expect(window.Explore._curatedSort([])).toEqual([]);
  });

  it('handles single cluster', () => {
    const c = [{ id: 'only', label: 'alone', item_count: 5 }];
    const result = window.Explore._curatedSort(c);
    expect(result.length).toBe(1);
    expect(result[0].id).toBe('only');
  });

  it('handles two clusters without crash', () => {
    const result = window.Explore._curatedSort(makeClusters(2));
    expect(result.length).toBe(2);
  });
});
