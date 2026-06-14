/**
 * Tests for static/js/search/search-cache.js — pure helpers only.
 *
 * IndexedDB operations (init, get, set, clear) are excluded because they
 * require a full IndexedDB environment not available in jsdom. The three
 * pure helpers (isExpired, isValidVersion, wrapWithMeta) are fully testable.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CACHE_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/search/search-cache.js'
);

let SC;
beforeEach(() => {
  delete require.cache[CACHE_PATH];
  SC = require(CACHE_PATH);
});

afterEach(() => {
  vi.useRealTimers();
});

const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

// -----------------------------------------------------------------
// isExpired
// -----------------------------------------------------------------
describe('isExpired', () => {
  it('returns true for null', () => {
    expect(SC.isExpired(null)).toBe(true);
  });

  it('returns true for undefined', () => {
    expect(SC.isExpired(undefined)).toBe(true);
  });

  it('returns true for item without timestamp', () => {
    expect(SC.isExpired({ version: 3 })).toBe(true);
  });

  it('returns false for a very recent timestamp', () => {
    const item = { timestamp: Date.now() };
    expect(SC.isExpired(item)).toBe(false);
  });

  it('returns true for timestamp older than 7 days', () => {
    const old = Date.now() - CACHE_TTL_MS - 1000;
    expect(SC.isExpired({ timestamp: old })).toBe(true);
  });

  it('returns false for timestamp exactly at boundary (just inside TTL)', () => {
    const recent = Date.now() - CACHE_TTL_MS + 5000;
    expect(SC.isExpired({ timestamp: recent })).toBe(false);
  });
});

// -----------------------------------------------------------------
// isValidVersion
// -----------------------------------------------------------------
describe('isValidVersion', () => {
  it('returns false for null', () => {
    expect(SC.isValidVersion(null)).toBe(false);
  });

  it('returns false for missing version', () => {
    expect(SC.isValidVersion({ timestamp: Date.now() })).toBe(false);
  });

  it('returns false for string version', () => {
    expect(SC.isValidVersion({ version: '3' })).toBe(false);
  });

  it('returns true for current cache version', () => {
    const item = SC.wrapWithMeta('test');
    expect(SC.isValidVersion(item)).toBe(true);
  });

  it('returns false for old version (0)', () => {
    expect(SC.isValidVersion({ version: 0 })).toBe(false);
  });

  it('returns false for future version (9999)', () => {
    expect(SC.isValidVersion({ version: 9999 })).toBe(false);
  });
});

// -----------------------------------------------------------------
// wrapWithMeta
// -----------------------------------------------------------------
describe('wrapWithMeta', () => {
  it('wraps the value under .value', () => {
    const wrapped = SC.wrapWithMeta({ data: 'hello' });
    expect(wrapped.value).toEqual({ data: 'hello' });
  });

  it('includes a numeric version', () => {
    const wrapped = SC.wrapWithMeta('x');
    expect(typeof wrapped.version).toBe('number');
    expect(wrapped.version).toBeGreaterThan(0);
  });

  it('includes a timestamp near now', () => {
    const before = Date.now();
    const wrapped = SC.wrapWithMeta('x');
    const after = Date.now();
    expect(wrapped.timestamp).toBeGreaterThanOrEqual(before);
    expect(wrapped.timestamp).toBeLessThanOrEqual(after);
  });

  it('round-trips: isValidVersion(wrapWithMeta(x)) is true', () => {
    expect(SC.isValidVersion(SC.wrapWithMeta('anything'))).toBe(true);
  });

  it('round-trips: isExpired(wrapWithMeta(x)) is false immediately', () => {
    expect(SC.isExpired(SC.wrapWithMeta('anything'))).toBe(false);
  });

  it('wraps null value', () => {
    const wrapped = SC.wrapWithMeta(null);
    expect(wrapped.value).toBeNull();
    expect(typeof wrapped.version).toBe('number');
  });

  it('wraps ArrayBuffer-like value', () => {
    const buf = new Float32Array([1.0, 2.0, 3.0]);
    const wrapped = SC.wrapWithMeta(buf);
    expect(wrapped.value).toBe(buf);
  });
});

// -----------------------------------------------------------------
// KEYS constant
// -----------------------------------------------------------------
describe('KEYS', () => {
  it('exposes KEYS object with at least embeddings and search_index', () => {
    expect(SC.KEYS).toBeDefined();
    expect(typeof SC.KEYS.EMBEDDINGS).toBe('string');
    expect(typeof SC.KEYS.SEARCH_INDEX).toBe('string');
  });

  it('KEYS values are distinct', () => {
    const values = Object.values(SC.KEYS);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });
});
