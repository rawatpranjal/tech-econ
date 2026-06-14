/**
 * Tests for static/js/favorites-local.js
 *
 * IIFE loader pattern: script exposes window.TechEconFavorites.
 * localStorage uses same in-memory mock as reading-history.test.js.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/favorites-local.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

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

let F;

beforeEach(() => {
  storageMock = makeStorageMock();
  vi.stubGlobal('localStorage', storageMock);
  // Stub browser dialogs used by clearAll / exportCSV
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('alert', vi.fn());
  // Stub URL API used by export helpers
  vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:mock'), revokeObjectURL: vi.fn() });
  delete window.TechEconFavorites;
  document.body.innerHTML = '';
  loadScript();
  F = window.TechEconFavorites;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// -----------------------------------------------------------------
// Module surface
// -----------------------------------------------------------------
describe('TechEconFavorites exports', () => {
  it('exposes the public API', () => {
    expect(F).toBeDefined();
    expect(typeof F.get).toBe('function');
    expect(typeof F.add).toBe('function');
    expect(typeof F.remove).toBe('function');
    expect(typeof F.toggle).toBe('function');
    expect(typeof F.isFavorited).toBe('function');
    expect(typeof F.count).toBe('function');
    expect(typeof F.clearAll).toBe('function');
    expect(typeof F.exportJSON).toBe('function');
    expect(typeof F.exportCSV).toBe('function');
    expect(typeof F.updateCount).toBe('function');
  });
});

// -----------------------------------------------------------------
// get / add
// -----------------------------------------------------------------
describe('get and add', () => {
  it('returns empty array when no favorites stored', () => {
    expect(F.get()).toEqual([]);
  });

  it('adds a favorite and retrieves it', () => {
    F.add('package', 'doubleml', { name: 'DoubleML', url: 'https://example.com' });
    const favs = F.get();
    expect(favs).toHaveLength(1);
    expect(favs[0].type).toBe('package');
    expect(favs[0].id).toBe('doubleml');
    expect(favs[0].data.name).toBe('DoubleML');
  });

  it('returns false when adding a duplicate (same type + id)', () => {
    F.add('package', 'pkg-a', {});
    const result = F.add('package', 'pkg-a', {});
    expect(result).toBe(false);
    expect(F.get()).toHaveLength(1);
  });

  it('returns true on successful add', () => {
    const result = F.add('package', 'pkg-a', {});
    expect(result).toBe(true);
  });

  it('stores an addedAt timestamp', () => {
    const before = Date.now();
    F.add('package', 'x', {});
    const after = Date.now();
    const ts = F.get()[0].addedAt;
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });

  it('same id with different type is treated as distinct', () => {
    F.add('package', 'xyz', {});
    F.add('dataset', 'xyz', {});
    expect(F.get()).toHaveLength(2);
  });

  it('itemData defaults to empty object when omitted', () => {
    F.add('package', 'no-data');
    expect(F.get()[0].data).toEqual({});
  });
});

// -----------------------------------------------------------------
// remove
// -----------------------------------------------------------------
describe('remove', () => {
  it('removes a favorited item', () => {
    F.add('package', 'pkg-a', {});
    F.remove('package', 'pkg-a');
    expect(F.get()).toHaveLength(0);
  });

  it('only removes the matching (type, id) pair', () => {
    F.add('package', 'pkg-a', {});
    F.add('dataset', 'ds-b', {});
    F.remove('package', 'pkg-a');
    expect(F.get()).toHaveLength(1);
    expect(F.get()[0].id).toBe('ds-b');
  });

  it('no-ops gracefully when item not present', () => {
    expect(() => F.remove('package', 'nonexistent')).not.toThrow();
    expect(F.get()).toHaveLength(0);
  });
});

// -----------------------------------------------------------------
// toggle
// -----------------------------------------------------------------
describe('toggle', () => {
  it('adds when not favorited, returns true', () => {
    expect(F.toggle('package', 'pkg', {})).toBe(true);
    expect(F.isFavorited('package', 'pkg')).toBe(true);
  });

  it('removes when already favorited, returns false', () => {
    F.add('package', 'pkg', {});
    expect(F.toggle('package', 'pkg', {})).toBe(false);
    expect(F.isFavorited('package', 'pkg')).toBe(false);
  });
});

// -----------------------------------------------------------------
// isFavorited / count
// -----------------------------------------------------------------
describe('isFavorited and count', () => {
  it('returns false when not favorited', () => {
    expect(F.isFavorited('package', 'x')).toBe(false);
  });

  it('returns true after adding', () => {
    F.add('package', 'x', {});
    expect(F.isFavorited('package', 'x')).toBe(true);
  });

  it('count reflects number of favorites', () => {
    expect(F.count()).toBe(0);
    F.add('package', 'a', {});
    F.add('dataset', 'b', {});
    expect(F.count()).toBe(2);
    F.remove('package', 'a');
    expect(F.count()).toBe(1);
  });
});

// -----------------------------------------------------------------
// clearAll
// -----------------------------------------------------------------
describe('clearAll', () => {
  it('removes all favorites when user confirms', () => {
    F.add('package', 'a', {});
    F.add('dataset', 'b', {});
    vi.stubGlobal('confirm', vi.fn(() => true));
    F.clearAll();
    expect(F.get()).toHaveLength(0);
  });

  it('does nothing when user cancels', () => {
    F.add('package', 'a', {});
    vi.stubGlobal('confirm', vi.fn(() => false));
    F.clearAll();
    expect(F.get()).toHaveLength(1);
  });
});

// -----------------------------------------------------------------
// updateCount badge rendering
// -----------------------------------------------------------------
describe('updateCount badge', () => {
  it('hides badges when count is zero', () => {
    document.body.innerHTML = '<span class="favorites-count">3</span>';
    F.updateCount();
    const badge = document.querySelector('.favorites-count');
    expect(badge.style.display).toBe('none');
  });

  it('shows badges and sets text when count > 0', () => {
    document.body.innerHTML = '<span class="favorites-count"></span>';
    F.add('package', 'x', {});
    F.updateCount();
    const badge = document.querySelector('.favorites-count');
    expect(badge.style.display).toBe('inline-flex');
    expect(badge.textContent).toBe('1');
  });

  it('does not throw when no badges in DOM', () => {
    document.body.innerHTML = '';
    expect(() => F.updateCount()).not.toThrow();
  });
});

// -----------------------------------------------------------------
// localStorage resilience
// -----------------------------------------------------------------
describe('localStorage resilience', () => {
  it('returns empty array when localStorage contains invalid JSON', () => {
    storageMock.setItem('techEconFavorites', 'not-json{{{');
    expect(F.get()).toEqual([]);
  });

  it('continues working after a corrupted storage entry', () => {
    storageMock.setItem('techEconFavorites', 'CORRUPT');
    F.add('package', 'healthy', {});
    expect(F.get()[0].id).toBe('healthy');
  });
});

// -----------------------------------------------------------------
// exportJSON
// -----------------------------------------------------------------
describe('exportJSON', () => {
  function makeBlobCapture() {
    let capturedContent = null;
    // Must be a real class (not arrow fn) so `new Blob(...)` works as constructor
    window.Blob = class BlobCapture { constructor(parts) { capturedContent = parts[0]; } };
    return () => capturedContent;
  }

  it('calls downloadFile (triggers Blob) when favorites exist', () => {
    const getContent = makeBlobCapture();
    F.add('package', 'econml', { name: 'EconML', url: 'https://econml.org' });
    F.exportJSON();
    expect(getContent()).not.toBeNull();
  });

  it('serializes JSON with the correct favorite data', () => {
    const getContent = makeBlobCapture();
    F.add('package', 'econml', { name: 'EconML' });
    F.exportJSON();
    const parsed = JSON.parse(getContent());
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed[0].id).toBe('econml');
    expect(parsed[0].type).toBe('package');
  });

  it('exports empty array JSON when no favorites', () => {
    const getContent = makeBlobCapture();
    F.exportJSON();
    expect(JSON.parse(getContent())).toEqual([]);
  });
});

// -----------------------------------------------------------------
// exportCSV
// -----------------------------------------------------------------
describe('exportCSV', () => {
  function makeBlobCapture() {
    let capturedContent = null;
    window.Blob = class BlobCapture { constructor(parts) { capturedContent = parts[0]; } };
    return () => capturedContent;
  }

  it('calls alert when no favorites to export', () => {
    const alertSpy = vi.fn();
    vi.stubGlobal('alert', alertSpy);
    F.exportCSV();
    expect(alertSpy).toHaveBeenCalledWith('No favorites to export');
  });

  it('includes CSV header row', () => {
    const getContent = makeBlobCapture();
    F.add('package', 'test', { name: 'Test Pkg' });
    F.exportCSV();
    expect(getContent()).toContain('Type,Name,Category,URL,Added Date');
  });

  it('escapes double-quotes in field values', () => {
    const getContent = makeBlobCapture();
    F.add('package', 'evil', { name: 'Say "hello"', url: '' });
    F.exportCSV();
    expect(getContent()).toContain('Say ""hello""');
  });

  it('includes type and name in the CSV row', () => {
    const getContent = makeBlobCapture();
    F.add('dataset', 'cps', { name: 'CPS Survey', url: 'https://bls.gov' });
    F.exportCSV();
    expect(getContent()).toContain('"dataset"');
    expect(getContent()).toContain('"CPS Survey"');
  });
});
