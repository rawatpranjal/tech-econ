/**
 * Tests for pure helpers in tracker.js:
 *   _hasAnyAssignment, _getWordCount, _jaccard, _hash, _truncate, _getReferrerSource
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const TRACKER_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/tracker.js'
);
const RAW = fs.readFileSync(TRACKER_PATH, 'utf8');

function loadTracker() {
  // tracker.js calls init() immediately; stub document.addEventListener
  if (!window.document.cookie) {
    Object.defineProperty(window.document, 'cookie', {
      writable: true,
      value: '',
    });
  }
  // eslint-disable-next-line no-new-func
  try { new Function('window', RAW)(window); } catch (_) {}
}

beforeEach(() => {
  delete window.Tracker;
  loadTracker();
});

afterEach(() => {
  delete window.Tracker;
});

// ──────────────────────────────────────────────
// _hasAnyAssignment
// ──────────────────────────────────────────────
describe('_hasAnyAssignment', () => {
  it('returns false for null', () => {
    expect(window.Tracker._hasAnyAssignment(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(window.Tracker._hasAnyAssignment(undefined)).toBe(false);
  });

  it('returns false for empty object', () => {
    expect(window.Tracker._hasAnyAssignment({})).toBe(false);
  });

  it('returns true for one-entry object', () => {
    expect(window.Tracker._hasAnyAssignment({ exp_1: 'control' })).toBe(true);
  });

  it('returns true for multi-entry object', () => {
    expect(window.Tracker._hasAnyAssignment({ a: '1', b: '2' })).toBe(true);
  });
});

// ──────────────────────────────────────────────
// _getWordCount
// ──────────────────────────────────────────────
describe('_getWordCount', () => {
  function makeEl(text) {
    const el = window.document.createElement('p');
    el.textContent = text;
    return el;
  }

  it('counts single word', () => {
    expect(window.Tracker._getWordCount(makeEl('hello'))).toBe(1);
  });

  it('counts multiple words', () => {
    expect(window.Tracker._getWordCount(makeEl('hello world foo'))).toBe(3);
  });

  it('collapses multiple spaces', () => {
    expect(window.Tracker._getWordCount(makeEl('a  b   c'))).toBe(3);
  });

  it('handles empty string', () => {
    expect(window.Tracker._getWordCount(makeEl(''))).toBe(0);
  });

  it('handles newlines as whitespace', () => {
    expect(window.Tracker._getWordCount(makeEl('line one\nline two'))).toBe(4);
  });

  it('ignores leading/trailing whitespace', () => {
    expect(window.Tracker._getWordCount(makeEl('  trimmed  '))).toBe(1);
  });
});

// ──────────────────────────────────────────────
// _jaccard
// ──────────────────────────────────────────────
describe('_jaccard', () => {
  it('identical strings return 1', () => {
    expect(window.Tracker._jaccard('hello world', 'hello world')).toBe(1);
  });

  it('completely different strings return 0', () => {
    expect(window.Tracker._jaccard('apple banana', 'carrot dog')).toBe(0);
  });

  it('partial overlap returns value in (0,1)', () => {
    const j = window.Tracker._jaccard('hello world', 'hello foo');
    expect(j).toBeGreaterThan(0);
    expect(j).toBeLessThan(1);
  });

  it('is case-insensitive', () => {
    const lower = window.Tracker._jaccard('Hello World', 'hello world');
    expect(lower).toBe(1);
  });

  it('single shared word gives 1/3 (union=3)', () => {
    // a={hello,world} b={hello,foo} → intersection={hello} union={hello,world,foo}
    const j = window.Tracker._jaccard('hello world', 'hello foo');
    expect(Math.abs(j - 1 / 3)).toBeLessThan(0.001);
  });
});

// ──────────────────────────────────────────────
// _hash
// ──────────────────────────────────────────────
describe('_hash', () => {
  it('returns a string', () => {
    expect(typeof window.Tracker._hash('hello')).toBe('string');
  });

  it('is deterministic', () => {
    expect(window.Tracker._hash('abc')).toBe(window.Tracker._hash('abc'));
  });

  it('different inputs produce different hashes (usually)', () => {
    expect(window.Tracker._hash('abc')).not.toBe(window.Tracker._hash('xyz'));
  });

  it('empty string does not throw', () => {
    expect(() => window.Tracker._hash('')).not.toThrow();
  });

  it('returns base-36 string', () => {
    const h = window.Tracker._hash('test-string');
    const stripped = h.replace(/^-/, '');
    expect(/^[0-9a-z]+$/.test(stripped)).toBe(true);
  });
});

// ──────────────────────────────────────────────
// _truncate
// ──────────────────────────────────────────────
describe('_truncate', () => {
  it('returns empty string for null', () => {
    expect(window.Tracker._truncate(null, 10)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(window.Tracker._truncate(undefined, 10)).toBe('');
  });

  it('returns string unchanged when shorter than limit', () => {
    expect(window.Tracker._truncate('hi', 10)).toBe('hi');
  });

  it('returns string unchanged when exactly at limit', () => {
    expect(window.Tracker._truncate('hello', 5)).toBe('hello');
  });

  it('truncates and appends ellipsis when over limit', () => {
    expect(window.Tracker._truncate('hello world', 5)).toBe('hello...');
  });

  it('coerces numbers to string', () => {
    const result = window.Tracker._truncate(12345678, 5);
    expect(result).toBe('12345...');
  });
});

// ──────────────────────────────────────────────
// _getReferrerSource
// ──────────────────────────────────────────────
describe('_getReferrerSource', () => {
  function withReferrer(url, fn) {
    // jsdom allows setting document.referrer via defineProperty only once per test
    Object.defineProperty(window.document, 'referrer', {
      configurable: true,
      get: () => url,
    });
    try { return fn(); } finally {
      Object.defineProperty(window.document, 'referrer', {
        configurable: true,
        get: () => '',
      });
    }
  }

  it('returns direct when no referrer', () => {
    withReferrer('', () => {
      expect(window.Tracker._getReferrerSource()).toBe('direct');
    });
  });

  it('identifies google', () => {
    withReferrer('https://www.google.com/search?q=test', () => {
      expect(window.Tracker._getReferrerSource()).toBe('google');
    });
  });

  it('identifies twitter', () => {
    withReferrer('https://twitter.com/user/status/123', () => {
      expect(window.Tracker._getReferrerSource()).toBe('twitter');
    });
  });

  it('identifies x.com as twitter', () => {
    withReferrer('https://x.com/user/status/123', () => {
      expect(window.Tracker._getReferrerSource()).toBe('twitter');
    });
  });

  it('identifies hackernews', () => {
    withReferrer('https://news.ycombinator.com/item?id=123', () => {
      expect(window.Tracker._getReferrerSource()).toBe('hackernews');
    });
  });

  it('identifies github', () => {
    withReferrer('https://github.com/anthropics/claude', () => {
      expect(window.Tracker._getReferrerSource()).toBe('github');
    });
  });

  it('identifies linkedin', () => {
    withReferrer('https://www.linkedin.com/posts/abc', () => {
      expect(window.Tracker._getReferrerSource()).toBe('linkedin');
    });
  });

  it('identifies internal traffic from tech-econ.com', () => {
    withReferrer('https://tech-econ.com/packages', () => {
      expect(window.Tracker._getReferrerSource()).toBe('internal');
    });
  });

  it('returns referral for unknown domain', () => {
    withReferrer('https://someotherblog.com/article', () => {
      expect(window.Tracker._getReferrerSource()).toBe('referral');
    });
  });
});
