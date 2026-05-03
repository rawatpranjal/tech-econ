// Smoke test — proves vitest discovery + jsdom env work.
// Replace / supplement once Job 0.2+ adds real tests against static/js/ modules.

import { describe, it, expect } from 'vitest';

describe('vitest plumbing', () => {
  it('runs trivially', () => {
    expect(1 + 1).toBe(2);
  });

  it('jsdom env exposes document', () => {
    expect(typeof document).toBe('object');
    expect(document.createElement('div').tagName).toBe('DIV');
  });

  it('jsdom env exposes window', () => {
    expect(typeof window).toBe('object');
    expect(typeof window.location).toBe('object');
  });
});

// Note: localStorage smoke test is intentionally omitted because Node 22's
// experimental WebStorage interferes with jsdom's polyfill. Modules that
// depend on localStorage (e.g. reading-history.js) will get explicit
// fixtures via window.localStorage in their own test files.
