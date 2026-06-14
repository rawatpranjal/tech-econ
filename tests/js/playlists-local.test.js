/**
 * Tests for static/js/playlists-local.js
 *
 * IIFE loader pattern; script exposes window.TechEconPlaylists.
 * localStorage uses the same in-memory mock as reading-history.test.js.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/playlists-local.js'
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

let P;

beforeEach(() => {
  storageMock = makeStorageMock();
  vi.stubGlobal('localStorage', storageMock);
  vi.stubGlobal('alert', vi.fn());
  vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:mock'), revokeObjectURL: vi.fn() });
  delete window.TechEconPlaylists;
  document.body.innerHTML = '';
  loadScript();
  P = window.TechEconPlaylists;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// -----------------------------------------------------------------
// Module surface
// -----------------------------------------------------------------
describe('TechEconPlaylists exports', () => {
  it('exposes the public API', () => {
    expect(P).toBeDefined();
    expect(typeof P.getAll).toBe('function');
    expect(typeof P.create).toBe('function');
    expect(typeof P.delete).toBe('function');
    expect(typeof P.rename).toBe('function');
    expect(typeof P.get).toBe('function');
    expect(typeof P.addItem).toBe('function');
    expect(typeof P.removeItem).toBe('function');
    expect(typeof P.exportCSV).toBe('function');
    expect(typeof P.importCSV).toBe('function');
    expect(typeof P.count).toBe('function');
    expect(typeof P.updateCount).toBe('function');
  });
});

// -----------------------------------------------------------------
// create / getAll / get
// -----------------------------------------------------------------
describe('create and retrieval', () => {
  it('returns empty array before any playlists created', () => {
    expect(P.getAll()).toEqual([]);
  });

  it('creates a playlist and returns its ID', () => {
    const id = P.create('My List');
    expect(typeof id).toBe('string');
    expect(id).toMatch(/^playlist-/);
  });

  it('created playlist has correct shape', () => {
    const id = P.create('Reading Queue');
    const pl = P.get(id);
    expect(pl).not.toBeNull();
    expect(pl.name).toBe('Reading Queue');
    expect(pl.items).toEqual([]);
    expect(typeof pl.createdAt).toBe('number');
  });

  it('defaults name to "Untitled Playlist" when omitted', () => {
    const id = P.create();
    expect(P.get(id).name).toBe('Untitled Playlist');
  });

  it('get returns null for unknown id', () => {
    expect(P.get('no-such-id')).toBeNull();
  });

  it('count reflects number of playlists', () => {
    expect(P.count()).toBe(0);
    P.create('A');
    P.create('B');
    expect(P.count()).toBe(2);
  });
});

// -----------------------------------------------------------------
// delete / rename
// -----------------------------------------------------------------
describe('delete', () => {
  it('removes the specified playlist', () => {
    const id = P.create('To Delete');
    P.delete(id);
    expect(P.get(id)).toBeNull();
    expect(P.count()).toBe(0);
  });

  it('only removes the matching playlist', () => {
    // Use fake timers so the two Date.now() calls produce distinct IDs
    vi.useFakeTimers();
    vi.setSystemTime(1000);
    const a = P.create('A');
    vi.setSystemTime(2000);
    const b = P.create('B');
    vi.useRealTimers();
    P.delete(a);
    expect(P.get(b)).not.toBeNull();
    expect(P.count()).toBe(1);
  });

  it('no-ops when id not found', () => {
    P.create('Keep');
    expect(() => P.delete('nonexistent')).not.toThrow();
    expect(P.count()).toBe(1);
  });
});

describe('rename', () => {
  it('updates the playlist name', () => {
    const id = P.create('Old Name');
    P.rename(id, 'New Name');
    expect(P.get(id).name).toBe('New Name');
  });

  it('does nothing when id not found', () => {
    expect(() => P.rename('bad-id', 'Name')).not.toThrow();
  });
});

// -----------------------------------------------------------------
// addItem / removeItem
// -----------------------------------------------------------------
describe('addItem', () => {
  it('adds an item to the playlist', () => {
    const id = P.create('List');
    P.addItem(id, 'package', 'doubleml', { name: 'DoubleML' });
    expect(P.get(id).items).toHaveLength(1);
    expect(P.get(id).items[0].id).toBe('doubleml');
  });

  it('returns true on successful add', () => {
    const id = P.create('List');
    expect(P.addItem(id, 'package', 'x', {})).toBe(true);
  });

  it('returns false when item already in playlist', () => {
    const id = P.create('List');
    P.addItem(id, 'package', 'x', {});
    expect(P.addItem(id, 'package', 'x', {})).toBe(false);
    expect(P.get(id).items).toHaveLength(1);
  });

  it('returns false when playlist not found', () => {
    expect(P.addItem('bad-id', 'package', 'x', {})).toBe(false);
  });

  it('same id with different type is distinct', () => {
    const id = P.create('List');
    P.addItem(id, 'package', 'x', {});
    P.addItem(id, 'dataset', 'x', {});
    expect(P.get(id).items).toHaveLength(2);
  });

  it('stores an addedAt timestamp', () => {
    const before = Date.now();
    const id = P.create('List');
    P.addItem(id, 'package', 'x', {});
    const after = Date.now();
    const ts = P.get(id).items[0].addedAt;
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });
});

describe('removeItem', () => {
  it('removes the matching item', () => {
    const id = P.create('List');
    P.addItem(id, 'package', 'a', {});
    P.addItem(id, 'package', 'b', {});
    P.removeItem(id, 'package', 'a');
    const items = P.get(id).items;
    expect(items).toHaveLength(1);
    expect(items[0].id).toBe('b');
  });

  it('no-ops when playlist not found', () => {
    expect(() => P.removeItem('bad', 'package', 'x')).not.toThrow();
  });

  it('no-ops when item not in playlist', () => {
    const id = P.create('List');
    expect(() => P.removeItem(id, 'package', 'nonexistent')).not.toThrow();
  });
});

// -----------------------------------------------------------------
// updateCount badge
// -----------------------------------------------------------------
describe('updateCount badge', () => {
  it('hides badges when no playlists exist', () => {
    document.body.innerHTML = '<span class="playlists-count">2</span>';
    P.updateCount();
    expect(document.querySelector('.playlists-count').style.display).toBe('none');
  });

  it('shows badges and sets text when playlists exist', () => {
    document.body.innerHTML = '<span class="playlists-count"></span>';
    P.create('My List');
    P.updateCount();
    const badge = document.querySelector('.playlists-count');
    expect(badge.style.display).toBe('inline-flex');
    expect(badge.textContent).toBe('1');
  });

  it('does not throw when no badges in DOM', () => {
    document.body.innerHTML = '';
    expect(() => P.updateCount()).not.toThrow();
  });
});

// -----------------------------------------------------------------
// localStorage resilience
// -----------------------------------------------------------------
describe('localStorage resilience', () => {
  it('returns empty array when localStorage contains invalid JSON', () => {
    storageMock.setItem('techEconPlaylists', 'not-json{{{');
    expect(P.getAll()).toEqual([]);
  });

  it('continues working after corrupted storage', () => {
    storageMock.setItem('techEconPlaylists', 'CORRUPT');
    const id = P.create('Fresh');
    expect(P.get(id).name).toBe('Fresh');
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

  it('alerts when playlist not found', () => {
    const alertSpy = vi.fn();
    vi.stubGlobal('alert', alertSpy);
    P.exportCSV('nonexistent-id');
    expect(alertSpy).toHaveBeenCalledWith('Playlist not found');
  });

  it('alerts when playlist is empty', () => {
    const alertSpy = vi.fn();
    vi.stubGlobal('alert', alertSpy);
    const id = P.create('Empty List');
    P.exportCSV(id);
    expect(alertSpy).toHaveBeenCalledWith('Playlist is empty');
  });

  it('includes playlist name as header comment', () => {
    const getContent = makeBlobCapture();
    const id = P.create('My Playlist');
    P.addItem(id, 'package', 'econml', { name: 'EconML', url: 'https://econml.org' });
    P.exportCSV(id);
    expect(getContent()).toContain('Playlist: My Playlist');
  });

  it('includes CSV column header row', () => {
    const getContent = makeBlobCapture();
    const id = P.create('Test');
    P.addItem(id, 'package', 'econml', { name: 'EconML', url: 'https://econml.org' });
    P.exportCSV(id);
    expect(getContent()).toContain('Type,Name,URL,Category,Added Date');
  });

  it('includes item type and name in CSV rows', () => {
    const getContent = makeBlobCapture();
    const id = P.create('Econ');
    P.addItem(id, 'dataset', 'cps', { name: 'CPS Survey', url: 'https://bls.gov' });
    P.exportCSV(id);
    expect(getContent()).toContain('"dataset"');
    expect(getContent()).toContain('"CPS Survey"');
  });

  it('escapes double-quotes in item name', () => {
    const getContent = makeBlobCapture();
    const id = P.create('Q');
    P.addItem(id, 'talk', 'q1', { name: 'Ask "why"', url: '' });
    P.exportCSV(id);
    expect(getContent()).toContain('Ask ""why""');
  });
});
