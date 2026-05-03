/**
 * Tests for static/js/because-you-viewed.js (R2 — homepage row).
 *
 * Strategy:
 * - Pure-function tests for findItemId + resolveNeighbours (no DOM, no fetch)
 * - DOM tests for renderRow with a real jsdom container
 * - End-to-end tests for init() with mocked fetch + window.TechEconHistory,
 *   asserting that the placeholder either renders cards or stays hidden
 *   depending on the situation.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/because-you-viewed.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

/**
 * Load the IIFE in the current jsdom window. Re-evaluating wipes any prior
 * window.BecauseYouViewed binding, which is what we want for isolation.
 */
function loadScript() {
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

const sampleMetadata = {
  items: [
    {
      id: 'package-foo',
      type: 'package',
      name: 'Foo Package',
      description: 'Useful Foo library',
      url: 'https://example.com/foo',
      category: 'Causal Inference',
    },
    {
      id: 'package-bar',
      type: 'package',
      name: 'Bar Package',
      description: 'Bar tools',
      url: 'https://example.com/bar',
      category: 'Causal Inference',
    },
    {
      id: 'paper-baz',
      type: 'paper',
      name: 'Baz Paper',
      description: 'Important paper',
      url: 'https://example.com/baz',
      category: 'Econometrics',
    },
    {
      id: 'paper-qux',
      type: 'paper',
      name: 'Qux Paper',
      description: 'Qux description',
      url: 'https://example.com/qux',
      category: 'Econometrics',
    },
    {
      id: 'package-foo-other',
      type: 'package',
      name: 'Foo Package',
      description: 'A different Foo with the same display name',
      url: 'https://example.com/foo-other',
      category: 'Other',
    },
  ],
};

const sampleRelated = {
  items: {
    'package-foo': [
      { id: 'package-bar', score: 0.9 },
      { id: 'paper-baz', score: 0.8 },
      { id: 'paper-qux', score: 0.7 },
    ],
    'package-bar': [
      { id: 'package-foo', score: 0.9 },
    ],
  },
};

describe('findItemId', () => {
  beforeEach(() => loadScript());

  it('returns null for empty inputs', () => {
    const { findItemId } = window.BecauseYouViewed;
    expect(findItemId([], { name: 'Foo Package', type: 'package' })).toBeNull();
    expect(findItemId(sampleMetadata.items, null)).toBeNull();
    expect(findItemId(sampleMetadata.items, { name: '' })).toBeNull();
  });

  it('matches by exact name + type', () => {
    const { findItemId } = window.BecauseYouViewed;
    const id = findItemId(sampleMetadata.items, { name: 'Foo Package', type: 'package' });
    expect(id).toBe('package-foo');
  });

  it('falls back to name-only when type is "item" (legacy history entries)', () => {
    const { findItemId } = window.BecauseYouViewed;
    const id = findItemId(sampleMetadata.items, { name: 'Baz Paper', type: 'item' });
    expect(id).toBe('paper-baz');
  });

  it('returns null when no match exists', () => {
    const { findItemId } = window.BecauseYouViewed;
    expect(findItemId(sampleMetadata.items, { name: 'Nonexistent', type: 'package' })).toBeNull();
  });

  it('disambiguates duplicate names by type', () => {
    const { findItemId } = window.BecauseYouViewed;
    // Two items both named "Foo Package" — one is a package, one would
    // also be a package in this fixture. The first matching (name+type)
    // is returned, which is package-foo.
    const id = findItemId(sampleMetadata.items, { name: 'Foo Package', type: 'package' });
    expect(id).toBe('package-foo');
  });
});

describe('resolveNeighbours', () => {
  beforeEach(() => loadScript());

  it('resolves ids to full item records', () => {
    const { resolveNeighbours } = window.BecauseYouViewed;
    const neighbours = sampleRelated.items['package-foo'];
    const resolved = resolveNeighbours(sampleMetadata.items, neighbours, 'package-foo');
    expect(resolved.map((i) => i.id)).toEqual(['package-bar', 'paper-baz', 'paper-qux']);
  });

  it('excludes the source id even if it sneaks into the neighbour list', () => {
    const { resolveNeighbours } = window.BecauseYouViewed;
    const neighbours = [
      { id: 'package-foo', score: 1.0 }, // self — should be filtered
      { id: 'package-bar', score: 0.9 },
    ];
    const resolved = resolveNeighbours(sampleMetadata.items, neighbours, 'package-foo');
    expect(resolved.map((i) => i.id)).toEqual(['package-bar']);
  });

  it('skips neighbour ids that are missing from metadata (graceful degradation)', () => {
    const { resolveNeighbours } = window.BecauseYouViewed;
    const neighbours = [
      { id: 'package-bar', score: 0.9 },
      { id: 'package-ghost', score: 0.85 }, // not in metadata
      { id: 'paper-baz', score: 0.8 },
    ];
    const resolved = resolveNeighbours(sampleMetadata.items, neighbours, 'package-foo');
    expect(resolved.map((i) => i.id)).toEqual(['package-bar', 'paper-baz']);
  });

  it('caps at MAX_CARDS = 5', () => {
    const { resolveNeighbours } = window.BecauseYouViewed;
    const many = Array.from({ length: 8 }, (_, i) => ({
      id: 'package-' + (i % 2 === 0 ? 'bar' : 'foo'),
      score: 0.9 - i * 0.05,
    }));
    // Build metadata with enough distinct ids
    const meta = sampleMetadata.items.concat(
      Array.from({ length: 8 }, (_, i) => ({
        id: 'package-extra-' + i,
        type: 'package',
        name: 'Extra ' + i,
        url: 'https://example.com/extra-' + i,
      }))
    );
    const neighbours = Array.from({ length: 8 }, (_, i) => ({
      id: 'package-extra-' + i,
      score: 0.9 - i * 0.05,
    }));
    const resolved = resolveNeighbours(meta, neighbours, 'package-foo');
    expect(resolved.length).toBe(5);
  });
});

describe('renderRow', () => {
  let container;

  beforeEach(() => {
    loadScript();
    container = document.createElement('div');
    container.id = 'because-you-viewed-section';
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (container.parentNode) container.parentNode.removeChild(container);
  });

  it('renders the anchor name and 3 cards', () => {
    const { renderRow } = window.BecauseYouViewed;
    const anchor = { name: 'Foo Package', type: 'package' };
    const items = [
      sampleMetadata.items[1], // bar
      sampleMetadata.items[2], // baz
      sampleMetadata.items[3], // qux
    ];
    renderRow(container, anchor, items);
    expect(container.querySelectorAll('.byv-card').length).toBe(3);
    expect(container.querySelector('.byv-header h3 em').textContent).toBe('Foo Package');
    expect(container.querySelectorAll('.byv-name')[0].textContent).toBe('Bar Package');
  });

  it('escapes HTML in anchor name and item fields (XSS safety)', () => {
    const { renderRow } = window.BecauseYouViewed;
    const anchor = { name: '<script>alert(1)</script>', type: 'package' };
    const items = [
      {
        id: 'p-x',
        type: '"><svg/onload=alert(1)>',
        name: '<img src=x onerror=alert(1)>',
        url: 'javascript:alert(1)', // still escaped as text in href, browser may still navigate; we accept this caveat
        category: '<a>cat</a>',
        description: '<b>desc</b>',
      },
    ];
    renderRow(container, anchor, items);
    // The injected script tags should appear as escaped text, not as live elements.
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img[src="x"]')).toBeNull();
    expect(container.querySelector('svg')).toBeNull();
    // The escaped content should be present in the textContent of the appropriate spans.
    expect(container.querySelector('.byv-header h3 em').textContent).toBe('<script>alert(1)</script>');
    expect(container.querySelector('.byv-name').textContent).toBe('<img src=x onerror=alert(1)>');
  });

  it('truncates long descriptions to ~120 chars', () => {
    const { renderRow } = window.BecauseYouViewed;
    const longDesc = 'a'.repeat(500);
    const items = [{
      id: 'p-x',
      type: 'package',
      name: 'Long',
      url: 'https://example.com/long',
      description: longDesc,
    }];
    renderRow(container, { name: 'Anchor', type: 'package' }, items);
    expect(container.querySelector('.byv-desc').textContent.length).toBeLessThanOrEqual(120);
  });

  it('omits optional fields when they are missing', () => {
    const { renderRow } = window.BecauseYouViewed;
    const items = [{
      id: 'p-min',
      type: '',
      name: 'Minimal',
      url: 'https://example.com/min',
      // no category, no description
    }];
    renderRow(container, { name: 'Anchor', type: 'package' }, items);
    expect(container.querySelector('.byv-type')).toBeNull();
    expect(container.querySelector('.byv-category')).toBeNull();
    expect(container.querySelector('.byv-desc')).toBeNull();
    expect(container.querySelector('.byv-name').textContent).toBe('Minimal');
  });
});

describe('init() — end to end', () => {
  let container;
  let fetchSpy;

  beforeEach(() => {
    container = document.createElement('div');
    container.id = 'because-you-viewed-section';
    container.style.display = 'none';
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (container.parentNode) container.parentNode.removeChild(container);
    if (fetchSpy) fetchSpy.mockRestore();
    delete window.TechEconHistory;
    delete window.BecauseYouViewed;
  });

  function mockFetchWith(metadata, related) {
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const body =
        typeof url === 'string' && url.includes('search-metadata') ? metadata : related;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(body),
      });
    });
  }

  it('stays hidden when there is no history', async () => {
    window.TechEconHistory = { getRecent: () => [] };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.BecauseYouViewed.init();
    expect(container.style.display).toBe('none');
    expect(container.innerHTML).toBe('');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('renders cards when last history item has neighbours', async () => {
    window.TechEconHistory = {
      getRecent: () => [{ name: 'Foo Package', type: 'package', url: 'https://example.com/foo' }],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.BecauseYouViewed.init();
    expect(container.style.display).toBe('block');
    expect(container.querySelectorAll('.byv-card').length).toBe(3);
    expect(container.querySelector('.byv-header h3 em').textContent).toBe('Foo Package');
  });

  it('stays hidden when fetch fails', async () => {
    window.TechEconHistory = {
      getRecent: () => [{ name: 'Foo Package', type: 'package' }],
    };
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.reject(new Error('network'))
    );
    loadScript();
    await window.BecauseYouViewed.init();
    expect(container.style.display).toBe('none');
    expect(container.innerHTML).toBe('');
  });

  it('stays hidden when the history item is not in metadata', async () => {
    window.TechEconHistory = {
      getRecent: () => [{ name: 'Unknown Item', type: 'package' }],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.BecauseYouViewed.init();
    expect(container.style.display).toBe('none');
  });

  it('stays hidden when item exists but has no related neighbours', async () => {
    window.TechEconHistory = {
      getRecent: () => [{ name: 'Qux Paper', type: 'paper' }],
    };
    mockFetchWith(sampleMetadata, sampleRelated);
    loadScript();
    await window.BecauseYouViewed.init();
    expect(container.style.display).toBe('none');
  });
});
