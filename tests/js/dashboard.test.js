/**
 * Tests for static/js/dashboard.js pure helpers and render functions.
 *
 * Uses the same IIFE loader pattern as debug-score.test.js.
 * dashboard.js exposes window.Dashboard with pure functions for testing.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/dashboard.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

function loadScript() {
  // Stub DOMContentLoaded so event listener registration doesn't fire during load
  vi.spyOn(document, 'addEventListener').mockImplementation((event, cb) => {
    if (event !== 'DOMContentLoaded') document.addEventListener.__original(event, cb);
  });
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

let D;
beforeEach(() => {
  delete window.Dashboard;
  document.body.innerHTML = '';
  loadScript();
  D = window.Dashboard;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// -----------------------------------------------------------------
// Module surface
// -----------------------------------------------------------------
describe('Dashboard exports', () => {
  it('exposes the public test API', () => {
    expect(D).toBeDefined();
    expect(typeof D.fmtNum).toBe('function');
    expect(typeof D.pct).toBe('function');
    expect(typeof D.escHtml).toBe('function');
    expect(typeof D.skeletonHTML).toBe('function');
    expect(typeof D.renderTraffic).toBe('function');
    expect(typeof D.renderTopContent).toBe('function');
    expect(typeof D.renderSearch).toBe('function');
    expect(typeof D.renderModels).toBe('function');
    expect(typeof D.renderExperiments).toBe('function');
  });
});

// -----------------------------------------------------------------
// fmtNum
// -----------------------------------------------------------------
describe('fmtNum', () => {
  it('formats small numbers as strings', () => {
    expect(D.fmtNum(0)).toBe('0');
    expect(D.fmtNum(42)).toBe('42');
    expect(D.fmtNum(999)).toBe('999');
  });

  it('formats thousands with k suffix', () => {
    expect(D.fmtNum(1000)).toBe('1.0k');
    expect(D.fmtNum(1500)).toBe('1.5k');
    expect(D.fmtNum(999999)).toBe('1000.0k');
  });

  it('formats millions with M suffix', () => {
    expect(D.fmtNum(1000000)).toBe('1.0M');
    expect(D.fmtNum(2500000)).toBe('2.5M');
  });

  it('returns -- for null and undefined', () => {
    expect(D.fmtNum(null)).toBe('--');
    expect(D.fmtNum(undefined)).toBe('--');
  });
});

// -----------------------------------------------------------------
// pct
// -----------------------------------------------------------------
describe('pct', () => {
  it('computes percentage as rounded string', () => {
    expect(D.pct(1, 4)).toBe('25%');
    expect(D.pct(1, 3)).toBe('33%');
    expect(D.pct(10, 100)).toBe('10%');
  });

  it('returns 0% for zero denominator', () => {
    expect(D.pct(5, 0)).toBe('0%');
    expect(D.pct(0, 0)).toBe('0%');
  });
});

// -----------------------------------------------------------------
// escHtml
// -----------------------------------------------------------------
describe('escHtml', () => {
  it('escapes all five dangerous characters', () => {
    expect(D.escHtml('&')).toBe('&amp;');
    expect(D.escHtml('<')).toBe('&lt;');
    expect(D.escHtml('>')).toBe('&gt;');
    expect(D.escHtml('"')).toBe('&quot;');
    expect(D.escHtml("'")).toBe('&#39;');
  });

  it('escapes a realistic XSS payload', () => {
    const raw = '<script>alert("xss")</script>';
    const escaped = D.escHtml(raw);
    expect(escaped).not.toContain('<script>');
    expect(escaped).toContain('&lt;script&gt;');
  });

  it('returns empty string for falsy inputs', () => {
    expect(D.escHtml(null)).toBe('');
    expect(D.escHtml(undefined)).toBe('');
    expect(D.escHtml('')).toBe('');
  });
});

// -----------------------------------------------------------------
// skeletonHTML
// -----------------------------------------------------------------
describe('skeletonHTML', () => {
  it('returns an outer wrapper with n skel-row divs', () => {
    const html = D.skeletonHTML(3);
    expect(html).toContain('dashboard-skeleton');
    const matches = html.match(/skel-row/g) || [];
    expect(matches.length).toBe(3);
  });

  it('returns an empty skeleton for n=0', () => {
    const html = D.skeletonHTML(0);
    expect(html).toContain('dashboard-skeleton');
    expect(html).not.toContain('skel-row');
  });
});

// -----------------------------------------------------------------
// renderTraffic — null-safety
// -----------------------------------------------------------------
describe('renderTraffic', () => {
  it('renders without throwing when all args are null', () => {
    expect(() => D.renderTraffic(null, null, null)).not.toThrow();
  });

  it('shows -- placeholders when data is unavailable', () => {
    const html = D.renderTraffic(null, null, null);
    expect(html).toContain('--');
  });

  it('shows healthy pill when health.status is ok', () => {
    const health = { status: 'ok', last_write_age_seconds: 60, events_24h: 100 };
    const html = D.renderTraffic(null, null, health);
    expect(html).toContain('Healthy');
  });

  it('shows degraded pill when last_write_age_seconds exceeds 24h', () => {
    const health = { status: 'ok', last_write_age_seconds: 86401, events_24h: 0 };
    const html = D.renderTraffic(null, null, health);
    expect(html).toContain('Degraded');
  });

  it('renders 30-day bar chart when timeseries data is present', () => {
    const timeseries = {
      data: [
        { date: '2026-05-01', pageviews: 100, clicks: 10, searches: 5 },
        { date: '2026-05-02', pageviews: 120, clicks: 12, searches: 7 },
      ],
    };
    const html = D.renderTraffic(null, timeseries, null);
    expect(html).toContain('dashboard-bar');
    expect(html).toContain('2026-05-01');
  });

  it('reads today stats from last timeseries entry (not /stats)', () => {
    const timeseries = {
      data: [
        { date: '2026-05-24', pageviews: 50, clicks: 5, searches: 2 },
        { date: '2026-05-25', pageviews: 80, clicks: 9, searches: 3, sessions: 40 },
      ],
    };
    const html = D.renderTraffic(null, timeseries, null);
    // pageviewsToday and clicksToday should come from the last entry (2026-05-25)
    expect(html).toContain('80');   // pageviews today
    expect(html).toContain('40');   // sessions today
    expect(html).toContain('Clicks today');
    expect(html).toContain('Pageviews today');
  });

  it('shows 0 for missing pageviews/sessions/clicks fields in today entry', () => {
    const timeseries = {
      data: [{ date: '2026-05-25' }],  // fields missing
    };
    const html = D.renderTraffic(null, timeseries, null);
    // fmtNum(0) should render as '0', not '--'
    expect(html).not.toMatch(/--.*Pageviews today/);
  });

  it('shows -- when timeseries is empty', () => {
    const html = D.renderTraffic(null, { data: [] }, null);
    expect(html).toContain('--');
    expect(html).toContain('Pageviews today');
  });
});

// -----------------------------------------------------------------
// renderTopContent
// -----------------------------------------------------------------
describe('renderTopContent', () => {
  it('shows empty state for empty array', () => {
    const html = D.renderTopContent([]);
    expect(html).toContain('No click data');
  });

  it('renders a ranked table for valid data', () => {
    const data = [
      { name: 'DoubleML', section: 'package', click_count: 42 },
      { name: 'CausalML', section: 'package', click_count: 30 },
    ];
    const html = D.renderTopContent(data);
    expect(html).toContain('DoubleML');
    expect(html).toContain('42');
  });

  it('does not XSS on malicious item names', () => {
    const data = [{ name: '<script>alert(1)</script>', section: 'evil', click_count: 1 }];
    const html = D.renderTopContent(data);
    expect(html).not.toContain('<script>');
  });

  it('handles data wrapped in a data property', () => {
    const data = { data: [{ name: 'Item A', section: 'package', click_count: 5 }] };
    const html = D.renderTopContent(data);
    expect(html).toContain('Item A');
  });
});

// -----------------------------------------------------------------
// renderSearch
// -----------------------------------------------------------------
describe('renderSearch', () => {
  it('shows empty state for empty array', () => {
    const html = D.renderSearch([]);
    expect(html).toContain('No search data');
  });

  it('renders search queries in a table', () => {
    const queries = [
      { query: 'causal inference', count: 10 },
      { query: 'machine learning', count: 8 },
    ];
    const html = D.renderSearch(queries);
    expect(html).toContain('causal inference');
    expect(html).toContain('10');
  });

  it('highlights zero-result queries in a callout', () => {
    const queries = [
      { query: 'obscure topic xyz', count: 2, result_count: 0 },
      { query: 'machine learning', count: 5 },
    ];
    const html = D.renderSearch(queries);
    expect(html).toContain('obscure topic xyz');
    expect(html).toContain('0 results');
  });

  it('does not XSS on malicious query strings', () => {
    const queries = [{ query: '"><img src=x onerror=alert(1)>', count: 1 }];
    const html = D.renderSearch(queries);
    expect(html).not.toContain('<img');
  });
});

// -----------------------------------------------------------------
// renderModels — reads from scoreboard JSON shape
// -----------------------------------------------------------------
const MOCK_SCOREBOARD = {
  generated_at: '2026-05-25T00:00:00Z',
  metrics: {
    latest: {
      ndcg_at_10: 0.2275,
      hit_rate_at_10: 0.65,
      map_at_10: 0.18,
      n_evaluable_sessions: 39,
    },
    history: [
      { date: '2026-05-23', ndcg_at_10: 0.2275, hit_rate_at_10: 0.65, map_at_10: 0.18, n_evaluable_sessions: 39 },
    ],
  },
  replays: {
    latest: {
      baseline_ndcg_at_10: 0.21,
      delta_ndcg_at_10: 0.0175,
      n_evaluable: 39,
    },
  },
  experiments: [
    {
      id: 'harness_aa_v1',
      status: 'paused',
      kind: 'A/A',
      started_at: '2026-05-04',
      ended_at: '2026-05-23',
      verdict: 'BROKEN — cookie timing contamination',
      summary: 'Bug found. See A.5 audit.',
    },
    {
      id: 'harness_aa_v2',
      status: 'active',
      kind: 'A/A',
      started_at: '2026-05-24',
      summary: 'Clean run post tracker.js fix.',
      results: {
        control_a: { ctr: 0.038, impressions: 1200, clicks: 46, ci_low: 0.028, ci_high: 0.048 },
        control_b: { ctr: 0.041, impressions: 1150, clicks: 47, ci_low: 0.030, ci_high: 0.052 },
      },
    },
  ],
};

describe('renderModels', () => {
  it('renders NDCG@10 stat card from scoreboard', () => {
    const html = D.renderModels(MOCK_SCOREBOARD);
    expect(html).toContain('22.8%'); // 0.2275 → 22.8
    expect(html).toContain('NDCG@10');
  });

  it('shows empty state when no latest metrics', () => {
    const html = D.renderModels({ metrics: { latest: null, history: [] }, replays: null, experiments: [] });
    expect(html).toContain('No eval runs');
  });

  it('renders history table row', () => {
    const html = D.renderModels(MOCK_SCOREBOARD);
    expect(html).toContain('2026-05-23');
  });

  it('renders replay delta when replays.latest is present', () => {
    const html = D.renderModels(MOCK_SCOREBOARD);
    expect(html).toContain('+1.75%'); // delta 0.0175 * 100 = 1.75
  });

  it('renders a sparkline for single-row history', () => {
    const html = D.renderModels(MOCK_SCOREBOARD);
    expect(html).toContain('dashboard-sparkline');
  });
});

// -----------------------------------------------------------------
// renderExperiments
// -----------------------------------------------------------------
describe('renderExperiments', () => {
  it('shows empty state for empty experiments list', () => {
    const html = D.renderExperiments({ experiments: [] });
    expect(html).toContain('No experiments');
  });

  it('renders active experiment callout', () => {
    const html = D.renderExperiments(MOCK_SCOREBOARD);
    expect(html).toContain('harness_aa_v2');
    expect(html).toContain('Active');
  });

  it('renders past experiment table row', () => {
    const html = D.renderExperiments(MOCK_SCOREBOARD);
    expect(html).toContain('harness_aa_v1');
    expect(html).toContain('paused');
  });

  it('renders per-variant CTR in active experiment', () => {
    const html = D.renderExperiments(MOCK_SCOREBOARD);
    expect(html).toContain('control_a');
    expect(html).toContain('3.80%'); // 0.038 * 100
  });

  it('shows collecting message when results are absent', () => {
    const scb = {
      experiments: [{
        id: 'no-results-exp',
        status: 'active',
        kind: 'A/B',
        started_at: '2026-05-25',
        summary: 'Just started.',
      }],
    };
    const html = D.renderExperiments(scb);
    expect(html).toContain('Collecting data');
  });

  it('does not XSS on experiment id or summary', () => {
    const scb = {
      experiments: [{
        id: '<img-bad>',
        status: 'paused',
        kind: 'A/A',
        started_at: '2026-01-01',
        ended_at: '2026-01-02',
        verdict: '<script>evil()</script>',
        summary: 'bad',
      }],
    };
    const html = D.renderExperiments(scb);
    expect(html).not.toContain('<img-bad>');
    expect(html).not.toContain('<script>');
  });
});

// ──────────────────────────────────────────────
// renderVariantStats
// ──────────────────────────────────────────────
describe('renderVariantStats', () => {
  it('shows collecting message when results is null', () => {
    const html = D.renderVariantStats({ results: null });
    expect(html).toContain('Collecting data');
  });

  it('shows collecting message when results is undefined', () => {
    const html = D.renderVariantStats({});
    expect(html).toContain('Collecting data');
  });

  it('renders a block for each variant', () => {
    const exp = {
      results: {
        control: { ctr: 0.12, ci_low: 0.10, ci_high: 0.14, impressions: 1000, clicks: 120 },
        treatment: { ctr: 0.15, ci_low: 0.13, ci_high: 0.17, impressions: 980, clicks: 147 },
      }
    };
    const html = D.renderVariantStats(exp);
    expect(html).toContain('control');
    expect(html).toContain('treatment');
  });

  it('formats CTR as percentage', () => {
    const exp = {
      results: {
        control: { ctr: 0.1234, impressions: 100, clicks: 12 },
      }
    };
    const html = D.renderVariantStats(exp);
    expect(html).toContain('12.34%');
  });

  it('shows -- for missing CTR', () => {
    const exp = {
      results: {
        v1: { impressions: 50, clicks: 5 },
      }
    };
    const html = D.renderVariantStats(exp);
    expect(html).toContain('--');
  });

  it('escapes XSS in variant id', () => {
    const exp = {
      results: {
        '<script>evil()</script>': { ctr: 0.1, impressions: 100, clicks: 10 },
      }
    };
    const html = D.renderVariantStats(exp);
    expect(html).not.toContain('<script>');
  });

  it('renders impressions and clicks counts', () => {
    const exp = {
      results: {
        control: { ctr: 0.1, impressions: 5000, clicks: 500 },
      }
    };
    const html = D.renderVariantStats(exp);
    expect(html).toContain('5.0k');
    expect(html).toContain('500');
  });
});
