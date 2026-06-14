/**
 * Tests for static/js/reading-history.js
 *
 * Uses the IIFE loader pattern. Script exposes window.TechEconHistory.
 * localStorage is provided by jsdom; cleared before each test.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/reading-history.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

// jsdom requires a real origin for localStorage. Provide a simple in-memory mock.
function makeStorageMock() {
  let store = {};
  return {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    clear: () => { store = {}; },
    get length() { return Object.keys(store).length; },
  };
}

let storageMock;

function loadScript() {
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

let H;

beforeEach(() => {
  storageMock = makeStorageMock();
  vi.stubGlobal('localStorage', storageMock);
  delete window.TechEconHistory;
  document.body.innerHTML = '';
  loadScript();
  H = window.TechEconHistory;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// -----------------------------------------------------------------
// Module surface
// -----------------------------------------------------------------
describe('TechEconHistory exports', () => {
  it('exposes the public API', () => {
    expect(H).toBeDefined();
    expect(typeof H.get).toBe('function');
    expect(typeof H.getRecent).toBe('function');
    expect(typeof H.add).toBe('function');
    expect(typeof H.clear).toBe('function');
    expect(typeof H.render).toBe('function');
  });
});

// -----------------------------------------------------------------
// get / add
// -----------------------------------------------------------------
describe('get and add', () => {
  it('returns empty array when localStorage is empty', () => {
    expect(H.get()).toEqual([]);
  });

  it('adds an item and retrieves it', () => {
    H.add({ name: 'DoubleML', url: 'https://example.com', type: 'package' });
    const history = H.get();
    expect(history).toHaveLength(1);
    expect(history[0].name).toBe('DoubleML');
    expect(history[0].url).toBe('https://example.com');
    expect(history[0].type).toBe('package');
  });

  it('adds to the FRONT (most-recently-viewed first)', () => {
    H.add({ name: 'Alpha', url: 'https://a.com' });
    H.add({ name: 'Beta', url: 'https://b.com' });
    const history = H.get();
    expect(history[0].name).toBe('Beta');
    expect(history[1].name).toBe('Alpha');
  });

  it('de-duplicates: re-adding an item moves it to the front', () => {
    H.add({ name: 'Alpha', url: 'https://a.com' });
    H.add({ name: 'Beta', url: 'https://b.com' });
    H.add({ name: 'Alpha', url: 'https://a.com' }); // re-add Alpha
    const history = H.get();
    expect(history[0].name).toBe('Alpha');
    expect(history).toHaveLength(2); // no duplicate
  });

  it('caps at MAX_ITEMS (10)', () => {
    for (let i = 0; i < 15; i++) {
      H.add({ name: `Item ${i}`, url: `https://example.com/${i}` });
    }
    expect(H.get()).toHaveLength(10);
  });

  it('ignores items missing name or url', () => {
    H.add({ url: 'https://example.com' }); // no name
    H.add({ name: 'Nameless' });           // no url
    expect(H.get()).toHaveLength(0);
  });

  it('stores a viewedAt timestamp', () => {
    const before = Date.now();
    H.add({ name: 'X', url: 'https://x.com' });
    const after = Date.now();
    const ts = H.get()[0].viewedAt;
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });

  it('defaults missing type, category, description to sensible values', () => {
    H.add({ name: 'X', url: 'https://x.com' });
    const item = H.get()[0];
    expect(item.type).toBe('item');
    expect(item.category).toBe('');
    expect(item.description).toBe('');
  });
});

// -----------------------------------------------------------------
// getRecent
// -----------------------------------------------------------------
describe('getRecent', () => {
  beforeEach(() => {
    for (let i = 0; i < 7; i++) {
      H.add({ name: `Item ${i}`, url: `https://example.com/${i}` });
    }
  });

  it('returns at most count items', () => {
    expect(H.getRecent(3)).toHaveLength(3);
    expect(H.getRecent(5)).toHaveLength(5);
  });

  it('returns all items when count > stored', () => {
    expect(H.getRecent(20)).toHaveLength(7);
  });

  it('defaults to MAX_ITEMS (10) when count is omitted', () => {
    expect(H.getRecent()).toHaveLength(7); // only 7 stored
  });
});

// -----------------------------------------------------------------
// clear
// -----------------------------------------------------------------
describe('clear', () => {
  it('empties the history', () => {
    H.add({ name: 'X', url: 'https://x.com' });
    H.clear();
    expect(H.get()).toHaveLength(0);
  });

  it('works when history is already empty', () => {
    expect(() => H.clear()).not.toThrow();
    expect(H.get()).toHaveLength(0);
  });
});

// -----------------------------------------------------------------
// localStorage resilience
// -----------------------------------------------------------------
describe('localStorage resilience', () => {
  it('returns empty array when localStorage contains invalid JSON', () => {
    storageMock.setItem('techEconHistory', 'not-json{{{');
    expect(H.get()).toEqual([]);
  });

  it('continues working after a corrupted storage entry', () => {
    storageMock.setItem('techEconHistory', 'CORRUPT');
    H.add({ name: 'Healthy', url: 'https://ok.com' });
    expect(H.get()[0].name).toBe('Healthy');
  });
});

// -----------------------------------------------------------------
// renderHistorySection
// -----------------------------------------------------------------
describe('renderHistorySection', () => {
  it('hides the section when history is empty', () => {
    document.body.innerHTML = '<div id="reading-history-section" style="display:block"></div>';
    H.render();
    const el = document.getElementById('reading-history-section');
    expect(el.style.display).toBe('none');
  });

  it('shows the section when history has items', () => {
    document.body.innerHTML = '<div id="reading-history-section" style="display:none"></div>';
    H.add({ name: 'CausalML', url: 'https://causalml.com', type: 'package' });
    H.render();
    const el = document.getElementById('reading-history-section');
    expect(el.style.display).toBe('block');
  });

  it('renders item names in the section', () => {
    document.body.innerHTML = '<div id="reading-history-section"></div>';
    H.add({ name: 'EconML', url: 'https://econml.com', type: 'package' });
    H.render();
    expect(document.getElementById('reading-history-section').innerHTML).toContain('EconML');
  });

  it('shows at most 5 items in the rendered section', () => {
    document.body.innerHTML = '<div id="reading-history-section"></div>';
    for (let i = 0; i < 8; i++) {
      H.add({ name: `Item ${i}`, url: `https://example.com/${i}` });
    }
    H.render();
    const cards = document.querySelectorAll('.history-card');
    expect(cards.length).toBe(5);
  });

  it('does nothing when the container element is absent', () => {
    document.body.innerHTML = '<div>no container here</div>';
    expect(() => H.render()).not.toThrow();
  });
});

// -----------------------------------------------------------------
// XSS — escapeHtml is used in renderHistorySection
// -----------------------------------------------------------------
describe('XSS safety in renderHistorySection', () => {
  it('escapes malicious name in history cards', () => {
    document.body.innerHTML = '<div id="reading-history-section"></div>';
    H.add({ name: '<script>alert(1)</script>', url: 'https://x.com', type: 'package' });
    H.render();
    const html = document.getElementById('reading-history-section').innerHTML;
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('escapes malicious category in history cards', () => {
    document.body.innerHTML = '<div id="reading-history-section"></div>';
    H.add({ name: 'Safe Name', url: 'https://x.com', category: '"><img src=x onerror=alert(1)>' });
    H.render();
    const html = document.getElementById('reading-history-section').innerHTML;
    expect(html).not.toContain('<img');
  });
});
