/**
 * Tests for pure helper functions in analytics-worker/index.js:
 *   sortAndLimit, hashIP, isAllowedOrigin, aggregateKVEvents
 *
 * Strategy: strip the `export default { ... }` from the source (it's the last
 * few hundred lines), replace it with a block that exposes the pure helpers to
 * window so we can test them from jsdom without any Cloudflare-specific globals.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const WORKER_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../analytics-worker/index.js'
);
const RAW = fs.readFileSync(WORKER_PATH, 'utf8');

// Replace just the `export default { async fetch(...) { ... } };` block (lines ~27-179).
// Helper functions (sortAndLimit, hashIP, etc.) are module-level, defined AFTER the
// export block, so they must NOT be stripped. We also append an exposure block at the end.
const WORKER_TESTABLE = RAW
  // Strip just the export default object literal (greedy match up to first bare `};`)
  .replace(/^export default \{[\s\S]*?\n\};/m, '/* export default stripped */')
  // Append test surface at the very end
  + `
if (typeof window !== 'undefined') {
  window._workerHelpers = {
    sortAndLimit,
    hashIP,
    isAllowedOrigin,
    aggregateKVEvents,
    jsonResponse,
    corsHeaders,
  };
}
`;

function loadWorker() {
  // Provide minimal Response stub so the source can reference it at definition time
  if (!window.Response) {
    window.Response = class Response {
      constructor(body, init) { this.body = body; this.status = (init || {}).status || 200; }
    };
  }
  // eslint-disable-next-line no-new-func
  new Function(WORKER_TESTABLE).call(window);
}

beforeEach(() => {
  delete window._workerHelpers;
  loadWorker();
});

afterEach(() => {
  delete window._workerHelpers;
});

// ──────────────────────────────────────────────
// sortAndLimit
// ──────────────────────────────────────────────
describe('sortAndLimit', () => {
  it('returns sorted array by count descending', () => {
    const obj = { beta: 3, alpha: 7, gamma: 1 };
    const result = window._workerHelpers.sortAndLimit(obj, 10);
    expect(result[0]).toEqual({ name: 'alpha', count: 7 });
    expect(result[1]).toEqual({ name: 'beta', count: 3 });
    expect(result[2]).toEqual({ name: 'gamma', count: 1 });
  });

  it('respects limit', () => {
    const obj = { a: 5, b: 4, c: 3, d: 2, e: 1 };
    const result = window._workerHelpers.sortAndLimit(obj, 3);
    expect(result).toHaveLength(3);
    expect(result.map(r => r.name)).toEqual(['a', 'b', 'c']);
  });

  it('returns empty array for empty object', () => {
    expect(window._workerHelpers.sortAndLimit({}, 10)).toEqual([]);
  });

  it('handles fewer items than limit', () => {
    const obj = { x: 10 };
    const result = window._workerHelpers.sortAndLimit(obj, 5);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ name: 'x', count: 10 });
  });

  it('ties: stable but order not guaranteed (just checks length + correctness)', () => {
    const obj = { a: 2, b: 2 };
    const result = window._workerHelpers.sortAndLimit(obj, 10);
    expect(result).toHaveLength(2);
    const counts = result.map(r => r.count);
    expect(counts).toEqual([2, 2]);
  });
});

// ──────────────────────────────────────────────
// hashIP
// ──────────────────────────────────────────────
describe('hashIP', () => {
  it('returns a string', () => {
    expect(typeof window._workerHelpers.hashIP('1.2.3.4')).toBe('string');
  });

  it('is deterministic', () => {
    const ip = '192.168.0.1';
    expect(window._workerHelpers.hashIP(ip)).toBe(window._workerHelpers.hashIP(ip));
  });

  it('different IPs produce different hashes (usually)', () => {
    const h1 = window._workerHelpers.hashIP('1.1.1.1');
    const h2 = window._workerHelpers.hashIP('8.8.8.8');
    expect(h1).not.toBe(h2);
  });

  it('handles empty string without throwing', () => {
    expect(() => window._workerHelpers.hashIP('')).not.toThrow();
  });

  it('returns base-36 string (only [0-9a-z] chars)', () => {
    const result = window._workerHelpers.hashIP('10.0.0.1');
    // Negative hash is possible due to bitwise ops; strip minus sign
    const stripped = result.replace(/^-/, '');
    expect(/^[0-9a-z]+$/.test(stripped)).toBe(true);
  });
});

// ──────────────────────────────────────────────
// isAllowedOrigin
// ──────────────────────────────────────────────
describe('isAllowedOrigin', () => {
  it('allows tech-econ.com', () => {
    expect(window._workerHelpers.isAllowedOrigin('https://tech-econ.com')).toBe(true);
  });

  it('allows www.tech-econ.com', () => {
    expect(window._workerHelpers.isAllowedOrigin('https://www.tech-econ.com')).toBe(true);
  });

  it('allows localhost:1313', () => {
    expect(window._workerHelpers.isAllowedOrigin('http://localhost:1313')).toBe(true);
  });

  it('rejects unknown origin', () => {
    expect(window._workerHelpers.isAllowedOrigin('https://evil.com')).toBe(false);
  });

  it('rejects null', () => {
    expect(window._workerHelpers.isAllowedOrigin(null)).toBe(false);
  });

  it('rejects empty string', () => {
    expect(window._workerHelpers.isAllowedOrigin('')).toBe(false);
  });

  it('rejects partial origin match from wrong domain', () => {
    expect(window._workerHelpers.isAllowedOrigin('https://not-tech-econ.com')).toBe(false);
  });
});

// ──────────────────────────────────────────────
// aggregateKVEvents
// ──────────────────────────────────────────────
describe('aggregateKVEvents', () => {
  const NOW = '2026-05-25T10:00:00.000Z';

  it('counts pageviews correctly', () => {
    const events = [
      { t: 'pageview', sid: 's1', ts: 1748167200000, d: { path: '/packages' } },
      { t: 'pageview', sid: 's1', ts: 1748167260000, d: { path: '/datasets' } },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.summary.pageviews).toBe(2);
  });

  it('counts unique sessions', () => {
    const events = [
      { t: 'pageview', sid: 'sess-a', ts: Date.now() },
      { t: 'pageview', sid: 'sess-a', ts: Date.now() },
      { t: 'pageview', sid: 'sess-b', ts: Date.now() },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.summary.sessions).toBe(2);
  });

  it('counts clicks and buckets into correct section', () => {
    const events = [
      { t: 'click', sid: 's1', ts: Date.now(), d: { type: 'card', name: 'DoubleML', section: 'packages' } },
      { t: 'click', sid: 's1', ts: Date.now(), d: { type: 'card', name: 'Stata', section: 'other' } },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.summary.clicks).toBe(2);
    // topClicks is converted to sorted array by sortAndLimit
    const pkgNames = stats.topClicks.packages.map(x => x.name);
    expect(pkgNames).toContain('DoubleML');
  });

  it('counts searches and lowercases query', () => {
    const events = [
      { t: 'search', sid: 's1', ts: Date.now(), d: { q: 'Causal Inference' } },
      { t: 'search', sid: 's1', ts: Date.now(), d: { q: 'causal inference' } },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.summary.searches).toBe(2);
    // Both queries lowercase → same key → count 2
    const sq = stats.topSearches.find(x => x.name === 'causal inference');
    expect(sq?.count).toBe(2);
  });

  it('computes average time on page', () => {
    const events = [
      { t: 'engage', sid: 's1', ts: Date.now(), d: { timeOnPage: 60 } },
      { t: 'engage', sid: 's2', ts: Date.now(), d: { timeOnPage: 120 } },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.summary.avgTimeOnPage).toBe(90);
  });

  it('returns 0 avgTimeOnPage with no engage events', () => {
    const stats = window._workerHelpers.aggregateKVEvents([], NOW);
    expect(stats.summary.avgTimeOnPage).toBe(0);
  });

  it('aggregates country counts', () => {
    const events = [
      { t: 'pageview', sid: 's1', ts: Date.now(), _country: 'US' },
      { t: 'pageview', sid: 's2', ts: Date.now(), _country: 'US' },
      { t: 'pageview', sid: 's3', ts: Date.now(), _country: 'GB' },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    const us = stats.countries.find(c => c.name === 'US');
    expect(us?.count).toBe(2);
  });

  it('ignores unknown country', () => {
    const events = [
      { t: 'pageview', sid: 's1', ts: Date.now(), _country: 'unknown' },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.countries).toHaveLength(0);
  });

  it('empty events returns zero-stats', () => {
    const stats = window._workerHelpers.aggregateKVEvents([], NOW);
    expect(stats.summary.pageviews).toBe(0);
    expect(stats.summary.clicks).toBe(0);
    expect(stats.summary.sessions).toBe(0);
    expect(stats.summary.searches).toBe(0);
  });

  it('dailyPageviews keyed by YYYY-MM-DD from ts', () => {
    const ts = new Date('2026-05-25T14:00:00Z').getTime();
    const events = [{ t: 'pageview', sid: 's1', ts }];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.dailyPageviews['2026-05-25']).toBe(1);
  });

  it('hourlyActivity increments by UTC hour', () => {
    const ts = new Date('2026-05-25T14:00:00Z').getTime(); // hour 14
    const events = [{ t: 'pageview', sid: 's1', ts }];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    expect(stats.hourlyActivity[14]).toBe(1);
  });

  it('topPages populated from path field', () => {
    const events = [
      { t: 'pageview', sid: 's1', ts: Date.now(), d: { path: '/packages' } },
      { t: 'pageview', sid: 's2', ts: Date.now(), d: { path: '/packages' } },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    const pkgPage = stats.topPages.find(p => p.name === '/packages');
    expect(pkgPage?.count).toBe(2);
  });

  it('datasets bucket used for section=datasets clicks', () => {
    const events = [
      { t: 'click', sid: 's1', ts: Date.now(), d: { type: 'card', name: 'CPS Survey', section: 'datasets' } },
    ];
    const stats = window._workerHelpers.aggregateKVEvents(events, NOW);
    const ds = stats.topClicks.datasets.find(x => x.name === 'CPS Survey');
    expect(ds?.count).toBe(1);
  });

  it('source is kv', () => {
    const stats = window._workerHelpers.aggregateKVEvents([], NOW);
    expect(stats._source).toBe('kv');
  });
});

// ──────────────────────────────────────────────
// corsHeaders
// ──────────────────────────────────────────────
describe('corsHeaders', () => {
  it('returns Access-Control-Allow-Origin for given origin', () => {
    const headers = window._workerHelpers.corsHeaders('https://tech-econ.com');
    expect(headers['Access-Control-Allow-Origin']).toBe('https://tech-econ.com');
  });

  it('defaults to * when no origin provided', () => {
    const headers = window._workerHelpers.corsHeaders(null);
    expect(headers['Access-Control-Allow-Origin']).toBe('*');
  });

  it('sets Allow-Credentials to false', () => {
    const headers = window._workerHelpers.corsHeaders('https://tech-econ.com');
    expect(headers['Access-Control-Allow-Credentials']).toBe('false');
  });

  it('returns an object with exactly two keys', () => {
    const headers = window._workerHelpers.corsHeaders('https://example.com');
    expect(Object.keys(headers)).toHaveLength(2);
  });
});

// ──────────────────────────────────────────────
// jsonResponse
// ──────────────────────────────────────────────
describe('jsonResponse', () => {
  it('returns a Response with status 200 by default', () => {
    const res = window._workerHelpers.jsonResponse({ ok: true }, null);
    expect(res.status).toBe(200);
  });

  it('accepts a custom status code', () => {
    const res = window._workerHelpers.jsonResponse({ error: 'not found' }, null, 404);
    expect(res.status).toBe(404);
  });

  it('serializes the data as JSON in the body', async () => {
    const data = { count: 42, items: ['a', 'b'] };
    const res = window._workerHelpers.jsonResponse(data, null);
    const text = await res.text();
    expect(JSON.parse(text)).toEqual(data);
  });

  it('includes Content-Type application/json header', () => {
    const res = window._workerHelpers.jsonResponse({}, 'https://tech-econ.com');
    expect(res.headers.get('Content-Type')).toBe('application/json');
  });
});
