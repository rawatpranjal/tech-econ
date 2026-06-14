/**
 * Tests for pure helper functions in llm-worker/index.js:
 *   isAllowedOrigin, corsHeaders, jsonResponse, sseError
 *
 * Strategy: strip `export default { ... };`, append window exposure, then
 * run via new Function().call(window) — same pattern as analytics-worker tests.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const WORKER_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../llm-worker/index.js'
);
const RAW = fs.readFileSync(WORKER_PATH, 'utf8');

// llm-worker has `export default { async fetch(...) { ... } }` at the top.
// Strip it so the file runs as plain JS in jsdom.
const WORKER_TESTABLE = RAW
  .replace(/^export default \{[\s\S]*?\n\};/m, '/* export default stripped */')
  + `
if (typeof window !== 'undefined') {
  window._llmHelpers = {
    isAllowedOrigin,
    corsHeaders,
    jsonResponse,
    sseError,
  };
}
`;

function loadWorker() {
  if (!window.Response) {
    window.Response = class Response {
      constructor(body, init) {
        this.body = body;
        this.status = (init || {}).status || 200;
        this._headers = (init || {}).headers || {};
        this.headers = {
          get: (k) => this._headers[k] ?? null,
        };
      }
      async text() { return this.body || ''; }
    };
  }
  // eslint-disable-next-line no-new-func
  new Function(WORKER_TESTABLE).call(window);
}

beforeEach(() => {
  delete window._llmHelpers;
  loadWorker();
});

afterEach(() => {
  delete window._llmHelpers;
});

// ──────────────────────────────────────────────
// isAllowedOrigin
// ──────────────────────────────────────────────
describe('llm-worker isAllowedOrigin', () => {
  it('allows tech-econ.com', () => {
    expect(window._llmHelpers.isAllowedOrigin('https://tech-econ.com')).toBe(true);
  });

  it('allows www.tech-econ.com', () => {
    expect(window._llmHelpers.isAllowedOrigin('https://www.tech-econ.com')).toBe(true);
  });

  it('allows localhost:1313', () => {
    expect(window._llmHelpers.isAllowedOrigin('http://localhost:1313')).toBe(true);
  });

  it('allows rawatpranjal.github.io', () => {
    expect(window._llmHelpers.isAllowedOrigin('https://rawatpranjal.github.io')).toBe(true);
  });

  it('rejects unknown origin', () => {
    expect(window._llmHelpers.isAllowedOrigin('https://evil.com')).toBe(false);
  });

  it('rejects null', () => {
    expect(window._llmHelpers.isAllowedOrigin(null)).toBe(false);
  });

  it('rejects empty string', () => {
    expect(window._llmHelpers.isAllowedOrigin('')).toBe(false);
  });

  it('rejects partial subdomain spoof', () => {
    expect(window._llmHelpers.isAllowedOrigin('https://not-tech-econ.com')).toBe(false);
  });
});

// ──────────────────────────────────────────────
// corsHeaders
// ──────────────────────────────────────────────
describe('llm-worker corsHeaders', () => {
  it('reflects allowed origin back', () => {
    const h = window._llmHelpers.corsHeaders('https://tech-econ.com');
    expect(h['Access-Control-Allow-Origin']).toBe('https://tech-econ.com');
  });

  it('falls back to first allowed origin for unknown origin', () => {
    const h = window._llmHelpers.corsHeaders('https://evil.com');
    expect(h['Access-Control-Allow-Origin']).toBe('https://tech-econ.com');
  });

  it('sets Allow-Credentials to false', () => {
    const h = window._llmHelpers.corsHeaders('https://tech-econ.com');
    expect(h['Access-Control-Allow-Credentials']).toBe('false');
  });

  it('returns exactly two keys', () => {
    const h = window._llmHelpers.corsHeaders('https://tech-econ.com');
    expect(Object.keys(h)).toHaveLength(2);
  });
});

// ──────────────────────────────────────────────
// jsonResponse
// ──────────────────────────────────────────────
describe('llm-worker jsonResponse', () => {
  it('returns 200 by default', () => {
    const res = window._llmHelpers.jsonResponse({ ok: true }, 'https://tech-econ.com');
    expect(res.status).toBe(200);
  });

  it('accepts custom status', () => {
    const res = window._llmHelpers.jsonResponse({ error: 'not found' }, null, 404);
    expect(res.status).toBe(404);
  });

  it('sets Content-Type to application/json', () => {
    const res = window._llmHelpers.jsonResponse({}, 'https://tech-econ.com');
    expect(res.headers.get('Content-Type')).toBe('application/json');
  });

  it('serializes data as JSON in body', async () => {
    const data = { results: [1, 2, 3], count: 3 };
    const res = window._llmHelpers.jsonResponse(data, null);
    const text = await res.text();
    expect(JSON.parse(text)).toEqual(data);
  });
});

// ──────────────────────────────────────────────
// sseError
// ──────────────────────────────────────────────
describe('llm-worker sseError', () => {
  it('returns a Response', () => {
    const res = window._llmHelpers.sseError('something went wrong', 'https://tech-econ.com');
    expect(res).toBeTruthy();
  });

  it('sets Content-Type to text/event-stream', () => {
    const res = window._llmHelpers.sseError('err', 'https://tech-econ.com');
    expect(res.headers.get('Content-Type')).toBe('text/event-stream');
  });

  it('wraps message in SSE data format with error key', async () => {
    const res = window._llmHelpers.sseError('timeout', null);
    const text = await res.text();
    expect(text).toMatch(/^data: /);
    const payload = JSON.parse(text.replace(/^data: /, '').replace(/\n\n$/, ''));
    expect(payload.error).toBe('timeout');
  });
});
