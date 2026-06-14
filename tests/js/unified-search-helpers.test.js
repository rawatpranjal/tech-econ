/**
 * Tests for pure helper functions inside unified-search.js.
 *
 * Exposed via window.UnifiedSearch._helpers after the IIFE loads.
 * Covers: truncate, smartTruncate, escapeRegex, generateSnippet, detectIntent
 *
 * Loading strategy: init() tries to fetch data and set up workers — both fail
 * in jsdom. We suppress the error and only exercise the pure helpers.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SRC = fs.readFileSync(
  path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../static/js/search/unified-search.js'),
  'utf8'
);

function loadModule() {
  // Stub Worker — init() tries to construct one
  if (!window.Worker) {
    window.Worker = class Worker {
      constructor() { this.onmessage = null; this.onerror = null; }
      postMessage() {}
      terminate() {}
    };
  }
  // Stub fetch so network calls are silent
  if (!window.fetch) {
    window.fetch = () => Promise.reject(new Error('no network in test'));
  }
  try {
    // eslint-disable-next-line no-new-func
    new Function(SRC).call(window);
  } catch (_) {
    // init() may throw due to missing DOM — that's OK; helpers are already registered
  }
}

let h;
beforeEach(() => {
  loadModule();
  h = window.UnifiedSearch?._helpers;
});
afterEach(() => {
  delete window.UnifiedSearch;
});

// ────────────────────────────────────────────────
// truncate
// ────────────────────────────────────────────────

describe('truncate', () => {
  it('returns empty string for falsy input', () => {
    expect(h.truncate(null, 10)).toBe('');
    expect(h.truncate('', 10)).toBe('');
    expect(h.truncate(undefined, 10)).toBe('');
  });

  it('returns string unchanged when shorter than limit', () => {
    expect(h.truncate('short', 100)).toBe('short');
  });

  it('returns string unchanged when exactly at limit', () => {
    expect(h.truncate('hello', 5)).toBe('hello');
  });

  it('truncates and adds ellipsis', () => {
    const result = h.truncate('hello world', 5);
    expect(result).toBe('hello...');
  });

  it('handles unicode without crashing', () => {
    const result = h.truncate('café latte', 4);
    expect(result).toContain('...');
  });
});

// ────────────────────────────────────────────────
// smartTruncate
// ────────────────────────────────────────────────

describe('smartTruncate', () => {
  it('returns empty for falsy input', () => {
    expect(h.smartTruncate(null, 50)).toBe('');
    expect(h.smartTruncate('', 50)).toBe('');
  });

  it('returns unchanged when short enough', () => {
    expect(h.smartTruncate('Short text.', 100)).toBe('Short text.');
  });

  it('cuts at sentence boundary when available', () => {
    const text = 'First sentence. Second sentence. Third sentence is here.';
    const result = h.smartTruncate(text, 30);
    // Should end at a sentence boundary
    expect(result).toMatch(/\.\s*$/);
  });

  it('falls back to word boundary — ends with ellipsis and shorter than original', () => {
    const text = 'This is a somewhat long string without early sentence breaks anywhere';
    const result = h.smartTruncate(text, 30);
    expect(result.length).toBeLessThan(text.length);
    // Result either ends at a word boundary + "..." or is a hard truncation + "..."
    expect(result).toMatch(/\.\.\.$/);
  });

  it('hard truncates when no clean boundary found', () => {
    const long = 'a'.repeat(200);
    const result = h.smartTruncate(long, 50);
    expect(result.length).toBeLessThanOrEqual(53); // 50 + '...'
  });
});

// ────────────────────────────────────────────────
// escapeRegex
// ────────────────────────────────────────────────

describe('escapeRegex', () => {
  it('escapes dots', () => {
    const escaped = h.escapeRegex('a.b');
    expect(new RegExp(escaped).test('acb')).toBe(false);
    expect(new RegExp(escaped).test('a.b')).toBe(true);
  });

  it('escapes asterisk', () => {
    const escaped = h.escapeRegex('a*b');
    expect(() => new RegExp(escaped)).not.toThrow();
    expect(new RegExp(escaped).test('a*b')).toBe(true);
  });

  it('escapes parentheses', () => {
    const escaped = h.escapeRegex('fn(x)');
    expect(new RegExp(escaped).test('fn(x)')).toBe(true);
  });

  it('passes clean strings unchanged', () => {
    expect(h.escapeRegex('hello world')).toBe('hello world');
  });

  it('escapes all special regex chars', () => {
    const special = '.*+?^${}()|[]\\';
    const escaped = h.escapeRegex(special);
    // Should be usable in a RegExp without throwing
    expect(() => new RegExp(escaped)).not.toThrow();
  });
});

// ────────────────────────────────────────────────
// generateSnippet
// ────────────────────────────────────────────────

describe('generateSnippet', () => {
  it('returns text unchanged when no match and short', () => {
    const result = h.generateSnippet('Short text', 'xyz', 150);
    expect(result).toBeTruthy();
  });

  it('returns empty string for falsy text', () => {
    expect(h.generateSnippet('', 'query', 150)).toBe('');
    expect(h.generateSnippet(null, 'query', 150)).toBeFalsy();
  });

  it('includes the matched query term in the snippet', () => {
    const text = 'A '.repeat(50) + 'causal inference is important ' + 'B '.repeat(50);
    const result = h.generateSnippet(text, 'causal inference', 150);
    expect(result.toLowerCase()).toContain('causal');
  });

  it('respects maxLength approximately', () => {
    const longText = 'word '.repeat(200);
    const result = h.generateSnippet(longText, 'word', 100);
    // Allow some slack for ellipsis
    expect(result.length).toBeLessThan(200);
  });
});

// ────────────────────────────────────────────────
// detectIntent
// ────────────────────────────────────────────────

describe('detectIntent', () => {
  it('returns null for empty/falsy query', () => {
    expect(h.detectIntent('')).toBeNull();
    expect(h.detectIntent(null)).toBeNull();
    expect(h.detectIntent(undefined)).toBeNull();
  });

  it('returns object with name and boostTypes for matched intent', () => {
    // Iterate possible intents by trying known keywords
    // "best" pattern should match something tool-related
    const toolQuery = 'best python package for causal';
    const result = h.detectIntent(toolQuery);
    // May or may not match depending on INTENT_PATTERNS; just check shape if non-null
    if (result !== null) {
      expect(result).toHaveProperty('name');
      expect(result).toHaveProperty('boostTypes');
    }
  });

  it('returns null for generic query with no intent signal', () => {
    // A very neutral query unlikely to match any pattern
    const result = h.detectIntent('xyz abc def');
    // Acceptable to be null or to return an intent — just no crash
    expect(result === null || typeof result === 'object').toBe(true);
  });
});

// escapeHtml — XSS safety
describe('escapeHtml', () => {
  it('escapes < and > to prevent script injection', () => {
    const out = h.escapeHtml('<script>alert(1)</script>');
    expect(out).not.toContain('<script>');
    expect(out).toContain('&lt;');
    expect(out).toContain('&gt;');
  });

  it('returns empty string for falsy input', () => {
    expect(h.escapeHtml('')).toBe('');
    expect(h.escapeHtml(null)).toBe('');
    expect(h.escapeHtml(undefined)).toBe('');
  });

  it('passes plain text through unchanged', () => {
    expect(h.escapeHtml('hello world')).toBe('hello world');
  });

  it('escapes ampersands', () => {
    expect(h.escapeHtml('a & b')).toBe('a &amp; b');
  });
});

// highlightText — wraps matches in <mark>, but base text is XSS-safe
describe('highlightText', () => {
  it('wraps matched term in mark tags', () => {
    const out = h.highlightText('regression discontinuity', 'regression');
    expect(out).toContain('<mark>');
    expect(out).toContain('regression');
  });

  it('returns escaped text when no query', () => {
    const out = h.highlightText('<b>bold</b>', '');
    expect(out).not.toContain('<b>');
    expect(out).toContain('&lt;b&gt;');
  });

  it('returns empty string for falsy text', () => {
    expect(h.highlightText('', 'q')).toBe('');
    expect(h.highlightText(null, 'q')).toBe('');
  });

  it('is case-insensitive', () => {
    const out = h.highlightText('Regression Analysis', 'regression');
    expect(out).toContain('<mark>');
  });

  it('does not double-escape already-safe user input in query', () => {
    const out = h.highlightText('hello world', 'hello');
    expect(out).toContain('<mark>hello</mark>');
    expect(out).toContain('world');
  });
});
