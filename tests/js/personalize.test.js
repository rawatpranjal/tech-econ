/**
 * Tests for static/js/personalize.js (Ra4 — homepage card multiplier).
 *
 * Strategy mirrors because-you-viewed.test.js:
 * - Pure-function tests for findItemId, buildBoostMap, buildNameToIdMap,
 *   and reorderRow (DOM only, no fetch).
 * - End-to-end tests for init() with mocked fetch + window.TechEconHistory,
 *   asserting that rows reorder or stay untouched depending on inputs.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/personalize.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

/**
 * Re-evaluating the IIFE wipes any prior window.TechEconPersonalize binding,
 * which gives us isolation between tests. Skips the requestIdleCallback /
 * setTimeout schedule path because the IIFE checks document.readyState; in
 * jsdom this is 'complete' so schedule() runs immediately. Tests that don't
 * want auto-init mock document.querySelectorAll to return [] before loading.
 */
function loadScript() {
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

const sampleMetadata = {
  items: [
    { id: 'package-foo', type: 'package', name: 'Foo Package', url: 'https://example.com/foo' },
    { id: 'package-bar', type: 'package', name: 'Bar Package', url: 'https://example.com/bar' },
    { id: 'package-baz', type: 'package', name: 'Baz Package', url: 'https://example.com/baz' },
    { id: 'package-qux', type: 'package', name: 'Qux Package', url: 'https://example.com/qux' },
    { id: 'paper-zed', type: 'paper', name: 'Zed Paper', url: 'https://example.com/zed' },
    { id: 'package-collide', type: 'package', name: 'Collide', url: 'https://example.com/c1' },
    { id: 'paper-collide', type: 'paper', name: 'Collide', url: 'https://example.com/c2' },
  ],
};

const sampleRelated = {
  items: {
    'package-foo': [
      { id: 'package-bar', score: 0.9 },
      { id: 'package-baz', score: 0.8 },
      { id: 'package-qux', score: 0.7 },
      { id: 'paper-zed', score: 0.6 },
    ],
    'package-bar': [
      { id: 'package-baz', score: 0.85 }, // shared neighbour with package-foo (rank 1)
      { id: 'package-qux', score: 0.75 },
    ],
    'paper-zed': [],
  },
};

describe('findItemId', () => {
  beforeEach(() => loadScript());

  it('returns null for empty inputs', () => {
    const { findItemId } = window.TechEconPersonalize;
    expect(findItemId([], { name: 'Foo Package', type: 'package' })).toBeNull();
    expect(findItemId(sampleMetadata.items, null)).toBeNull();
    expect(findItemId(sampleMetadata.items, { name: '' })).toBeNull();
  });

  it('matches by exact name + type', () => {
    const { findItemId } = window.TechEconPersonalize;
    expect(findItemId(sampleMetadata.items, { name: 'Collide', type: 'paper' })).toBe('paper-collide');
    expect(findItemId(sampleMetadata.items, { name: 'Collide', type: 'package' })).toBe('package-collide');
  });

  it('falls back to first name match when type is "item"', () => {
    const { findItemId } = window.TechEconPersonalize;
    // Legacy history entries have type='item'; the function should still
    // return *some* matching id (first wins by iteration order).
    expect(findItemId(sampleMetadata.items, { name: 'Collide', type: 'item' })).toBe('package-collide');
  });

  it('returns null when no name match exists', () => {
    const { findItemId } = window.TechEconPersonalize;
    expect(findItemId(sampleMetadata.items, { name: 'Nonexistent', type: 'package' })).toBeNull();
  });
});

describe('buildBoostMap', () => {
  beforeEach(() => loadScript());

  it('rank-decays neighbour weights from 1.0 down to 0.6', () => {
    const { buildBoostMap } = window.TechEconPersonalize;
    const history = [{ name: 'Foo Package', type: 'package' }];
    const boost = buildBoostMap(sampleMetadata.items, sampleRelated.items, history);
    // package-bar is rank 0 -> 1.0; package-baz rank 1 -> 0.9; package-qux rank 2 -> 0.8; paper-zed rank 3 -> 0.7.
    expect(boost['package-bar']).toBeCloseTo(1.0, 6);
    expect(boost['package-baz']).toBeCloseTo(0.9, 6);
    expect(boost['package-qux']).toBeCloseTo(0.8, 6);
    expect(boost['paper-zed']).toBeCloseTo(0.7, 6);
  });

  it('reinforces shared neighbours via max(), not sum', () => {
    const { buildBoostMap } = window.TechEconPersonalize;
    const history = [
      { name: 'Foo Package', type: 'package' }, // package-baz at rank 1 -> 0.9
      { name: 'Bar Package', type: 'package' }, // package-baz at rank 0 -> 1.0
    ];
    const boost = buildBoostMap(sampleMetadata.items, sampleRelated.items, history);
    // max(0.9, 1.0) = 1.0; explicitly NOT 0.9 + 1.0 = 1.9.
    expect(boost['package-baz']).toBeCloseTo(1.0, 6);
  });

  it('ignores history items not in metadata', () => {
    const { buildBoostMap } = window.TechEconPersonalize;
    const history = [
      { name: 'Ghost Item', type: 'package' }, // not in metadata
      { name: 'Foo Package', type: 'package' }, // valid
    ];
    const boost = buildBoostMap(sampleMetadata.items, sampleRelated.items, history);
    // Only Foo's neighbours should appear.
    expect(boost['package-bar']).toBeCloseTo(1.0, 6);
    expect(Object.keys(boost).sort()).toEqual(['package-bar', 'package-baz', 'package-qux', 'paper-zed']);
  });

  it('handles items with empty neighbour lists', () => {
    const { buildBoostMap } = window.TechEconPersonalize;
    const history = [{ name: 'Zed Paper', type: 'paper' }];
    const boost = buildBoostMap(sampleMetadata.items, sampleRelated.items, history);
    expect(Object.keys(boost)).toEqual([]);
  });

  it('returns empty map for empty history', () => {
    const { buildBoostMap } = window.TechEconPersonalize;
    expect(Object.keys(window.TechEconPersonalize.buildBoostMap(sampleMetadata.items, sampleRelated.items, []))).toEqual([]);
  });

  it('returns empty map when related-items missing', () => {
    const { buildBoostMap } = window.TechEconPersonalize;
    const history = [{ name: 'Foo Package', type: 'package' }];
    const boost = buildBoostMap(sampleMetadata.items, {}, history);
    expect(Object.keys(boost)).toEqual([]);
  });
});

describe('buildNameToIdMap', () => {
  beforeEach(() => loadScript());

  it('keys lookup by lowercased name', () => {
    const { buildNameToIdMap } = window.TechEconPersonalize;
    const m = buildNameToIdMap(sampleMetadata.items);
    expect(m['foo package']).toBe('package-foo');
    expect(m['zed paper']).toBe('paper-zed');
    expect(m['Foo Package']).toBeUndefined(); // case-sensitive miss
  });

  it('first-write-wins on name collisions across types', () => {
    const { buildNameToIdMap } = window.TechEconPersonalize;
    const m = buildNameToIdMap(sampleMetadata.items);
    // package-collide appears first in the metadata array, so it wins.
    expect(m['collide']).toBe('package-collide');
  });

  it('skips items missing id or name', () => {
    const { buildNameToIdMap } = window.TechEconPersonalize;
    const items = [
      { name: 'has both', id: 'x' },
      { name: 'no id' },
      { id: 'no-name' },
      null,
    ];
    const m = buildNameToIdMap(items);
    expect(Object.keys(m)).toEqual(['has both']);
  });
});

describe('buildDampenSet', () => {
  beforeEach(() => loadScript());

  it('returns empty set for empty history', () => {
    const { buildDampenSet } = window.TechEconPersonalize;
    expect(Object.keys(buildDampenSet(sampleMetadata.items, []))).toEqual([]);
  });

  it('returns empty set for null history', () => {
    const { buildDampenSet } = window.TechEconPersonalize;
    expect(Object.keys(buildDampenSet(sampleMetadata.items, null))).toEqual([]);
  });

  it('contains the source ids of all matched history items', () => {
    const { buildDampenSet } = window.TechEconPersonalize;
    const history = [
      { name: 'Foo Package', type: 'package' },
      { name: 'Zed Paper', type: 'paper' },
    ];
    const set = buildDampenSet(sampleMetadata.items, history);
    expect(set['package-foo']).toBe(true);
    expect(set['paper-zed']).toBe(true);
    expect(Object.keys(set).sort()).toEqual(['package-foo', 'paper-zed']);
  });

  it('silently skips history items not in metadata', () => {
    const { buildDampenSet } = window.TechEconPersonalize;
    const history = [
      { name: 'Ghost Item', type: 'package' },
      { name: 'Foo Package', type: 'package' },
    ];
    const set = buildDampenSet(sampleMetadata.items, history);
    expect(Object.keys(set)).toEqual(['package-foo']);
  });

  it('disambiguates same-name items by type', () => {
    const { buildDampenSet } = window.TechEconPersonalize;
    const history = [{ name: 'Collide', type: 'paper' }];
    const set = buildDampenSet(sampleMetadata.items, history);
    expect(set['paper-collide']).toBe(true);
    expect(set['package-collide']).toBeUndefined();
  });
});

describe('reorderRow', () => {
  let row;

  beforeEach(() => {
    loadScript();
    row = document.createElement('div');
    row.className = 'cards-row';
    document.body.appendChild(row);
  });

  afterEach(() => {
    if (row.parentNode) row.parentNode.removeChild(row);
  });

  /**
   * Append cards with given lowercased data-name values, returning the
   * array of DOM elements in original order.
   */
  function makeCards(names) {
    return names.map((name) => {
      const el = document.createElement('div');
      el.className = 'package-card';
      el.setAttribute('data-name', name);
      el.textContent = name;
      row.appendChild(el);
      return el;
    });
  }

  it('returns false when nothing is boosted', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta', 'gamma']);
    const moved = reorderRow(row, { alpha: 'a', beta: 'b', gamma: 'g' }, {});
    expect(moved).toBe(false);
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['alpha', 'beta', 'gamma']);
  });

  it('returns false when the row has fewer than 2 cards', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha']);
    const moved = reorderRow(row, { alpha: 'a' }, { a: 1.0 });
    expect(moved).toBe(false);
  });

  it('moves boosted cards to the top, stable on the rest', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta', 'gamma', 'delta']);
    const nameToId = { alpha: 'a', beta: 'b', gamma: 'g', delta: 'd' };
    const boost = { g: 0.8 }; // boost gamma only
    const moved = reorderRow(row, nameToId, boost);
    expect(moved).toBe(true);
    const order = [...row.children].map((c) => c.getAttribute('data-name'));
    expect(order[0]).toBe('gamma');
    // The non-boosted cards should retain their relative order.
    expect(order.slice(1)).toEqual(['alpha', 'beta', 'delta']);
  });

  it('orders multiple boosted cards by descending boost', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta', 'gamma', 'delta']);
    const nameToId = { alpha: 'a', beta: 'b', gamma: 'g', delta: 'd' };
    const boost = { a: 0.4, g: 1.0, d: 0.7 };
    const moved = reorderRow(row, nameToId, boost);
    expect(moved).toBe(true);
    const order = [...row.children].map((c) => c.getAttribute('data-name'));
    // gamma (1.0) > delta (0.7) > alpha (0.4) > beta (0)
    expect(order).toEqual(['gamma', 'delta', 'alpha', 'beta']);
  });

  it('treats cards with unknown names as no-boost', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['known', 'unknown']);
    const nameToId = { known: 'k' };
    const boost = { k: 1.0 };
    const moved = reorderRow(row, nameToId, boost);
    expect(moved).toBe(true);
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['known', 'unknown']);
  });

  it('ignores cards missing data-name', () => {
    const { reorderRow } = window.TechEconPersonalize;
    const a = document.createElement('div');
    a.className = 'package-card';
    a.textContent = 'a';
    row.appendChild(a);
    const b = document.createElement('div');
    b.className = 'package-card';
    b.setAttribute('data-name', 'beta');
    b.textContent = 'b';
    row.appendChild(b);
    const moved = reorderRow(row, { beta: 'B' }, { B: 1.0 });
    expect(moved).toBe(true);
    expect(row.children[0].getAttribute('data-name')).toBe('beta');
  });

  it('LAMBDA stays in [0, 1] so multiplier never exceeds 1 + LAMBDA', () => {
    const { LAMBDA } = window.TechEconPersonalize;
    expect(LAMBDA).toBeGreaterThanOrEqual(0);
    expect(LAMBDA).toBeLessThanOrEqual(1);
  });

  it('DAMPEN stays in [0, 1] so multiplier never drops below 1 - DAMPEN', () => {
    const { DAMPEN } = window.TechEconPersonalize;
    expect(DAMPEN).toBeGreaterThanOrEqual(0);
    expect(DAMPEN).toBeLessThanOrEqual(1);
  });

  it('pushes dampened cards to the bottom of the row', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta', 'gamma']);
    const nameToId = { alpha: 'a', beta: 'b', gamma: 'g' };
    const dampen = { b: true }; // dampen beta
    const moved = reorderRow(row, nameToId, {}, dampen);
    expect(moved).toBe(true);
    const order = [...row.children].map((c) => c.getAttribute('data-name'));
    // beta dampened (0.8), alpha + gamma untouched (1.0). Beta last.
    expect(order).toEqual(['alpha', 'gamma', 'beta']);
  });

  it('dampening trumps boosting (already-seen wins over similar-to-seen)', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta']);
    const nameToId = { alpha: 'a', beta: 'b' };
    const boost = { a: 1.0 }; // alpha would normally boost to 1.2
    const dampen = { a: true }; // but alpha is also dampened to 0.8
    const moved = reorderRow(row, nameToId, boost, dampen);
    expect(moved).toBe(true);
    const order = [...row.children].map((c) => c.getAttribute('data-name'));
    // alpha dampened wins over its own boost: 0.8 < 1.0 (beta's untouched).
    expect(order).toEqual(['beta', 'alpha']);
  });

  it('three-arg call (no dampen) still works for backwards compatibility', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta', 'gamma']);
    const nameToId = { alpha: 'a', beta: 'b', gamma: 'g' };
    const boost = { g: 1.0 };
    const moved = reorderRow(row, nameToId, boost);
    expect(moved).toBe(true);
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['gamma', 'alpha', 'beta']);
  });

  it('returns false when only dampen ids match no cards', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta']);
    const nameToId = { alpha: 'a', beta: 'b' };
    const moved = reorderRow(row, nameToId, {}, { ghost: true });
    expect(moved).toBe(false);
  });

  it('orders multiple dampened cards stably on tie', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta', 'gamma']);
    const nameToId = { alpha: 'a', beta: 'b', gamma: 'g' };
    const dampen = { a: true, g: true };
    const moved = reorderRow(row, nameToId, {}, dampen);
    expect(moved).toBe(true);
    // Both alpha and gamma dampened (0.8); beta untouched (1.0).
    // Stable on dampen tie: alpha before gamma (original idx 0 < 2).
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['beta', 'alpha', 'gamma']);
  });

  it('mixes boost + dampen + untouched correctly', () => {
    const { reorderRow } = window.TechEconPersonalize;
    makeCards(['alpha', 'beta', 'gamma', 'delta']);
    const nameToId = { alpha: 'a', beta: 'b', gamma: 'g', delta: 'd' };
    const boost = { g: 1.0, d: 0.5 };
    const dampen = { a: true };
    const moved = reorderRow(row, nameToId, boost, dampen);
    expect(moved).toBe(true);
    // gamma 1.2 > delta 1.1 > beta 1.0 > alpha 0.8
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['gamma', 'delta', 'beta', 'alpha']);
  });
});

describe('init() — end to end', () => {
  let cardsView;
  let row;
  let fetchSpy;

  beforeEach(() => {
    cardsView = document.createElement('div');
    cardsView.id = 'cards-view';
    row = document.createElement('div');
    row.className = 'cards-row';
    cardsView.appendChild(row);
    document.body.appendChild(cardsView);
  });

  afterEach(() => {
    if (cardsView.parentNode) cardsView.parentNode.removeChild(cardsView);
    if (fetchSpy) fetchSpy.mockRestore();
    delete window.TechEconHistory;
    delete window.TechEconPersonalize;
  });

  function addCards(names) {
    return names.map((name) => {
      const el = document.createElement('div');
      el.className = 'package-card';
      el.setAttribute('data-name', name);
      el.textContent = name;
      row.appendChild(el);
      return el;
    });
  }

  function mockFetchWith(metadata, related) {
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const body =
        typeof url === 'string' && url.includes('search-metadata') ? metadata : related;
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    });
  }

  it('does nothing with empty history', async () => {
    addCards(['foo package', 'bar package']);
    window.TechEconHistory = { getRecent: () => [] };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.TechEconPersonalize.init();
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['foo package', 'bar package']);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('does nothing with history below MIN_HISTORY (3)', async () => {
    addCards(['foo package', 'bar package']);
    window.TechEconHistory = {
      getRecent: () => [
        { name: 'Foo Package', type: 'package' },
        { name: 'Bar Package', type: 'package' },
      ],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.TechEconPersonalize.init();
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['foo package', 'bar package']);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('reorders cards: boost neighbours up, dampen sources down', async () => {
    addCards(['foo package', 'bar package', 'baz package', 'qux package']);
    window.TechEconHistory = {
      getRecent: () => [
        { name: 'Foo Package', type: 'package' },
        { name: 'Bar Package', type: 'package' },
        { name: 'Zed Paper', type: 'paper' },
      ],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.TechEconPersonalize.init();
    // Sources (dampened to 1-DAMPEN=0.8): foo, bar, zed.
    // Foo's neighbours: bar(1.0), baz(0.9), qux(0.8), zed(0.7).
    // Bar's neighbours: baz(1.0), qux(0.9). Zed has none.
    // Boost map after max(): bar=1.0, baz=1.0, qux=0.9, zed=0.7. But:
    //   bar is in dampen set -> hard-set to 0.8 (dampening trumps boost)
    //   foo is in dampen set -> hard-set to 0.8
    //   baz: 1 + 0.2 * 1.0 = 1.2
    //   qux: 1 + 0.2 * 0.9 = 1.18
    // Sort descending: baz (1.2), qux (1.18), foo (0.8 idx 0), bar (0.8 idx 1).
    const order = [...row.children].map((c) => c.getAttribute('data-name'));
    expect(order).toEqual(['baz package', 'qux package', 'foo package', 'bar package']);
  });

  it('silently no-ops when fetch fails', async () => {
    addCards(['foo package', 'bar package', 'baz package']);
    window.TechEconHistory = {
      getRecent: () => [
        { name: 'Foo Package', type: 'package' },
        { name: 'Bar Package', type: 'package' },
        { name: 'Baz Package', type: 'package' },
      ],
    };
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.reject(new Error('network')));
    loadScript();
    await window.TechEconPersonalize.init();
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['foo package', 'bar package', 'baz package']);
  });

  it('no-ops when no rows present', async () => {
    cardsView.removeChild(row);
    window.TechEconHistory = {
      getRecent: () => [
        { name: 'Foo Package', type: 'package' },
        { name: 'Bar Package', type: 'package' },
        { name: 'Baz Package', type: 'package' },
      ],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.TechEconPersonalize.init();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('no-ops when boost map is empty (history items have no neighbours)', async () => {
    addCards(['foo package', 'bar package']);
    window.TechEconHistory = {
      getRecent: () => [
        { name: 'Zed Paper', type: 'paper' }, // empty neighbour list
        { name: 'Zed Paper', type: 'paper' },
        { name: 'Zed Paper', type: 'paper' },
      ],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.TechEconPersonalize.init();
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['foo package', 'bar package']);
  });

  it('handles multiple rows independently', async () => {
    // Add a second row.
    const row2 = document.createElement('div');
    row2.className = 'cards-row';
    cardsView.appendChild(row2);
    addCards(['bar package', 'foo package']); // row 1: bar at idx 0, foo at idx 1
    ['qux package', 'baz package'].forEach((name) => {
      const el = document.createElement('div');
      el.className = 'package-card';
      el.setAttribute('data-name', name);
      el.textContent = name;
      row2.appendChild(el);
    });

    window.TechEconHistory = {
      getRecent: () => [
        { name: 'Foo Package', type: 'package' },
        { name: 'Bar Package', type: 'package' },
        { name: 'Bar Package', type: 'package' },
      ],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.TechEconPersonalize.init();
    // Sources (dampened to 0.8): foo, bar.
    // Row 1 with bar (idx 0) and foo (idx 1): both dampened to 0.8 -> tie -> stable on idx -> bar, foo.
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['bar package', 'foo package']);
    // Row 2 with qux and baz: baz gets max(0.9 from foo, 1.0 from bar) = 1.0 -> 1.2; qux gets max(0.8 from foo, 0.9 from bar) = 0.9 -> 1.18.
    // baz first.
    expect([...row2.children].map((c) => c.getAttribute('data-name'))).toEqual(['baz package', 'qux package']);
  });
});
