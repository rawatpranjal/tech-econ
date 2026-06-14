/**
 * Tests for pure formatting helpers in analytics-dashboard.js:
 *   _formatNumber, _formatTime, _escapeHtml
 *
 * The IIFE calls init() on DOMContentLoaded / document.readyState check.
 * jsdom starts with readyState='complete', so init() runs, but loadAnalytics()
 * immediately does fetch() which we don't stub — that's fine because the
 * helpers are already registered on window before that async path runs.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/analytics-dashboard.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

function loadDashboard() {
  // Stub fetch so loadAnalytics() doesn't throw on the absent DOM elements
  vi.stubGlobal('fetch', () => Promise.resolve({ ok: false, json: () => Promise.resolve({}) }));
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

beforeEach(() => {
  delete window.AnalyticsDashboard;
  delete window.refreshAnalytics;
  // Provide minimal DOM elements loadAnalytics() touches (including <p> for showError)
  document.body.innerHTML = `
    <div id="analytics-content" style="display:none"></div>
    <div id="analytics-error" style="display:none"><p></p></div>
    <div id="analytics-loading" style="display:none"></div>
  `;
  loadDashboard();
});

afterEach(() => {
  vi.restoreAllMocks();
  delete window.AnalyticsDashboard;
  delete window.refreshAnalytics;
  document.body.innerHTML = '';
});

// ──────────────────────────────────────────────
// _formatNumber
// ──────────────────────────────────────────────
describe('AnalyticsDashboard._formatNumber', () => {
  it('formats under 1000 as plain number', () => {
    expect(window.AnalyticsDashboard._formatNumber(0)).toBe('0');
    expect(window.AnalyticsDashboard._formatNumber(999)).toBe('999');
  });

  it('formats 1000 as 1.0K', () => {
    expect(window.AnalyticsDashboard._formatNumber(1000)).toBe('1.0K');
  });

  it('formats 1500 as 1.5K', () => {
    expect(window.AnalyticsDashboard._formatNumber(1500)).toBe('1.5K');
  });

  it('formats 999999 as 999.9K', () => {
    expect(window.AnalyticsDashboard._formatNumber(999999)).toBe('1000.0K');
    // Note: 999999/1000 = 999.999, toFixed(1) = "1000.0"
  });

  it('formats 1000000 as 1.0M', () => {
    expect(window.AnalyticsDashboard._formatNumber(1000000)).toBe('1.0M');
  });

  it('formats 2500000 as 2.5M', () => {
    expect(window.AnalyticsDashboard._formatNumber(2500000)).toBe('2.5M');
  });

  it('formats exactly 1000000 as M not K', () => {
    const result = window.AnalyticsDashboard._formatNumber(1000000);
    expect(result).toContain('M');
    expect(result).not.toContain('K');
  });
});

// ──────────────────────────────────────────────
// _formatTime
// ──────────────────────────────────────────────
describe('AnalyticsDashboard._formatTime', () => {
  it('formats 0 seconds as 0s', () => {
    expect(window.AnalyticsDashboard._formatTime(0)).toBe('0s');
  });

  it('formats 59 seconds as 59s', () => {
    expect(window.AnalyticsDashboard._formatTime(59)).toBe('59s');
  });

  it('formats 60 seconds as 1m 0s', () => {
    expect(window.AnalyticsDashboard._formatTime(60)).toBe('1m 0s');
  });

  it('formats 90 seconds as 1m 30s', () => {
    expect(window.AnalyticsDashboard._formatTime(90)).toBe('1m 30s');
  });

  it('formats 3600 seconds as 60m 0s', () => {
    expect(window.AnalyticsDashboard._formatTime(3600)).toBe('60m 0s');
  });

  it('formats 3661 seconds as 61m 1s', () => {
    expect(window.AnalyticsDashboard._formatTime(3661)).toBe('61m 1s');
  });
});

// ──────────────────────────────────────────────
// _escapeHtml (XSS prevention)
// ──────────────────────────────────────────────
describe('AnalyticsDashboard._escapeHtml', () => {
  it('escapes angle brackets', () => {
    const result = window.AnalyticsDashboard._escapeHtml('<script>alert(1)</script>');
    expect(result).not.toContain('<script>');
    expect(result).toContain('&lt;');
    expect(result).toContain('&gt;');
  });

  it('escapes ampersand', () => {
    const result = window.AnalyticsDashboard._escapeHtml('a & b');
    expect(result).toContain('&amp;');
  });

  it('passes double quotes through unchanged (safe in text nodes)', () => {
    const result = window.AnalyticsDashboard._escapeHtml('"quoted"');
    expect(result).toContain('"quoted"');
  });

  it('passes plain text through unchanged', () => {
    const result = window.AnalyticsDashboard._escapeHtml('hello world');
    expect(result).toBe('hello world');
  });

  it('returns empty string for empty input', () => {
    expect(window.AnalyticsDashboard._escapeHtml('')).toBe('');
  });
});
