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

  it('reorders cards when ≥3 history items have boostable neighbours', async () => {
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
    // Foo's neighbours are bar(1.0), baz(0.9), qux(0.8), zed(0.7).
    // Bar's neighbours are baz(1.0), qux(0.9). Zed has none.
    // After max(): bar=1.0, baz=1.0, qux=0.9, zed=0.7. Foo card itself is not in metadata's neighbour set so is no-boost.
    // Expected order in row: bar (1.0) > baz (1.0, stable on tie via original idx 2) > qux (0.9) > foo (0).
    const order = [...row.children].map((c) => c.getAttribute('data-name'));
    expect(order[0]).toBe('bar package');
    expect(order[1]).toBe('baz package');
    expect(order[2]).toBe('qux package');
    expect(order[3]).toBe('foo package');
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
    // Row 1 with bar and foo: bar gets boost 1.0 (rank 0 of foo), foo gets 0 (it's the source). bar stays at top.
    expect([...row.children].map((c) => c.getAttribute('data-name'))).toEqual(['bar package', 'foo package']);
    // Row 2 with qux and baz: baz gets max(0.9 from foo, 1.0 from bar) = 1.0; qux gets max(0.8 from foo, 0.9 from bar) = 0.9.
    // baz first.
    expect([...row2.children].map((c) => c.getAttribute('data-name'))).toEqual(['baz package', 'qux package']);
  });
});
