/**
 * Tests for static/js/experiments.js (Phase 7 A/B harness scaffold).
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const MOD_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/experiments.js'
);

let Experiments;
beforeEach(() => {
  delete require.cache[MOD_PATH];
  Experiments = require(MOD_PATH);
});


// ---------------------------------------------------------------------------
// FNV-1a hash
// ---------------------------------------------------------------------------
describe('fnv1a', () => {
  it('returns 0 for empty string (well, actually 2166136261 — the FNV offset basis)', () => {
    expect(Experiments.fnv1a('')).toBe(2166136261);
  });

  it('is deterministic', () => {
    expect(Experiments.fnv1a('abc')).toBe(Experiments.fnv1a('abc'));
  });

  it('produces different hashes for different inputs', () => {
    const h1 = Experiments.fnv1a('abc');
    const h2 = Experiments.fnv1a('abd');
    expect(h1).not.toBe(h2);
  });

  it('returns a 32-bit unsigned integer', () => {
    const inputs = ['short', 'a much longer string with various characters !@#$%', 'ÿþ'];
    for (const s of inputs) {
      const h = Experiments.fnv1a(s);
      expect(Number.isInteger(h)).toBe(true);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThan(2 ** 32);
    }
  });
});


// ---------------------------------------------------------------------------
// bucketOf: distribution + determinism
// ---------------------------------------------------------------------------
describe('bucketOf', () => {
  it('returns a value in [0, 100)', () => {
    for (let i = 0; i < 50; i++) {
      const b = Experiments.bucketOf('uid-' + i, 'exp');
      expect(b).toBeGreaterThanOrEqual(0);
      expect(b).toBeLessThan(100);
    }
  });

  it('is deterministic for the same (uid, exp_id)', () => {
    expect(Experiments.bucketOf('alice', 'exp1')).toBe(Experiments.bucketOf('alice', 'exp1'));
  });

  it('experiment_id changes the bucket (no permanent treatment effect across experiments)', () => {
    // Find an alice for whom different experiments produce different
    // buckets. Across enough experiments at least one should differ.
    const expBuckets = new Set();
    for (let i = 0; i < 20; i++) {
      expBuckets.add(Experiments.bucketOf('alice', 'exp-' + i));
    }
    expect(expBuckets.size).toBeGreaterThan(1);
  });

  it('gives roughly uniform distribution over many users', () => {
    const counts = new Array(10).fill(0);
    for (let i = 0; i < 5000; i++) {
      const b = Experiments.bucketOf('user-' + i, 'distribution-test');
      counts[Math.floor(b / 10)]++;
    }
    // 5000 users / 10 deciles → 500 per decile in expectation. Allow
    // ±25% slack (375..625).
    for (const c of counts) {
      expect(c).toBeGreaterThan(375);
      expect(c).toBeLessThan(625);
    }
  });
});


// ---------------------------------------------------------------------------
// resolveVariant: config-driven variant pick
// ---------------------------------------------------------------------------
describe('resolveVariant', () => {
  const config50_50 = {
    experiments: [
      {
        id: 'exp_a',
        status: 'active',
        variants: [
          { id: 'control', traffic: 50 },
          { id: 'treatment', traffic: 50 },
        ],
      },
    ],
  };

  it('returns null for unknown experiment id', () => {
    expect(Experiments.resolveVariant(config50_50, 'uid', 'unknown')).toBeNull();
  });

  it('returns null for paused experiment', () => {
    const cfg = {
      experiments: [
        { id: 'p', status: 'paused', variants: [{ id: 'c', traffic: 100 }] },
      ],
    };
    expect(Experiments.resolveVariant(cfg, 'uid', 'p')).toBeNull();
  });

  it('returns null for draft experiment', () => {
    const cfg = {
      experiments: [
        { id: 'd', status: 'draft', variants: [{ id: 'c', traffic: 100 }] },
      ],
    };
    expect(Experiments.resolveVariant(cfg, 'uid', 'd')).toBeNull();
  });

  it('treats a 100-traffic variant as forced assignment', () => {
    const cfg = {
      experiments: [
        { id: 'force', status: 'active', variants: [{ id: 'only', traffic: 100 }] },
      ],
    };
    for (const uid of ['a', 'b', 'c', 'd', 'e']) {
      expect(Experiments.resolveVariant(cfg, uid, 'force')).toBe('only');
    }
  });

  it('respects unequal traffic splits', () => {
    const cfg = {
      experiments: [
        {
          id: 'skewed',
          status: 'active',
          variants: [
            { id: 'rare', traffic: 10 },
            { id: 'common', traffic: 90 },
          ],
        },
      ],
    };
    let rareCount = 0;
    const N = 1000;
    for (let i = 0; i < N; i++) {
      const v = Experiments.resolveVariant(cfg, 'user-' + i, 'skewed');
      if (v === 'rare') rareCount++;
    }
    // Expected ~10% with ±3 percentage-point slack
    const rareFraction = rareCount / N;
    expect(rareFraction).toBeGreaterThan(0.07);
    expect(rareFraction).toBeLessThan(0.13);
  });

  it('returns null when traffic does not sum to 100', () => {
    const cfg = {
      experiments: [
        {
          id: 'bad',
          status: 'active',
          variants: [
            { id: 'c', traffic: 30 },
            { id: 't', traffic: 30 },
          ],
        },
      ],
    };
    expect(Experiments.resolveVariant(cfg, 'uid', 'bad')).toBeNull();
  });

  it('returns null for missing variants array', () => {
    const cfg = { experiments: [{ id: 'e', status: 'active' }] };
    expect(Experiments.resolveVariant(cfg, 'uid', 'e')).toBeNull();
  });

  it('returns null for malformed variant entries', () => {
    const cfg = {
      experiments: [
        {
          id: 'bad',
          status: 'active',
          variants: [{ id: 'c', traffic: 'fifty' }, { id: 't', traffic: 50 }],
        },
      ],
    };
    expect(Experiments.resolveVariant(cfg, 'uid', 'bad')).toBeNull();
  });

  it('is deterministic for the same uid', () => {
    const v1 = Experiments.resolveVariant(config50_50, 'alice', 'exp_a');
    const v2 = Experiments.resolveVariant(config50_50, 'alice', 'exp_a');
    expect(v1).toBe(v2);
  });

  it('roughly 50/50 split across many users', () => {
    let controlCount = 0;
    const N = 2000;
    for (let i = 0; i < N; i++) {
      const v = Experiments.resolveVariant(config50_50, 'user-' + i, 'exp_a');
      if (v === 'control') controlCount++;
    }
    // Expected ~50% with ±5 percentage-point slack
    const controlFraction = controlCount / N;
    expect(controlFraction).toBeGreaterThan(0.45);
    expect(controlFraction).toBeLessThan(0.55);
  });
});


// ---------------------------------------------------------------------------
// findExperiment
// ---------------------------------------------------------------------------
describe('findExperiment', () => {
  it('returns the matching experiment', () => {
    const cfg = { experiments: [{ id: 'a' }, { id: 'b' }] };
    expect(Experiments.findExperiment(cfg, 'b').id).toBe('b');
  });

  it('returns null on miss', () => {
    expect(Experiments.findExperiment({ experiments: [] }, 'x')).toBeNull();
  });

  it('returns null for null config', () => {
    expect(Experiments.findExperiment(null, 'x')).toBeNull();
  });

  it('returns null when experiments is not an array', () => {
    expect(Experiments.findExperiment({ experiments: 'oops' }, 'x')).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// getVariant — DOM-integrated path
// ---------------------------------------------------------------------------
describe('getVariant — DOM integration', () => {
  let configEl;

  beforeEach(() => {
    configEl = document.createElement('script');
    configEl.id = 'experiments-config';
    configEl.type = 'application/json';
    document.head.appendChild(configEl);
    document.cookie = 'te_uid=test-uid-12345; path=/';
  });

  afterEach(() => {
    if (configEl.parentNode) configEl.parentNode.removeChild(configEl);
    document.cookie = 'te_uid=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  });

  it('returns null when config element is missing', () => {
    document.head.removeChild(configEl);
    configEl = document.createElement('script'); // dummy so afterEach is happy
    expect(Experiments.getVariant('any')).toBeNull();
  });

  it('returns null when config is malformed JSON', () => {
    configEl.textContent = '{not json';
    expect(Experiments.getVariant('any')).toBeNull();
  });

  it('returns the variant for an active experiment', () => {
    configEl.textContent = JSON.stringify({
      experiments: [
        {
          id: 'e1',
          status: 'active',
          variants: [
            { id: 'control', traffic: 50 },
            { id: 'treatment', traffic: 50 },
          ],
        },
      ],
    });
    const v = Experiments.getVariant('e1');
    expect(['control', 'treatment']).toContain(v);
  });

  it('returns null for unknown experiment id', () => {
    configEl.textContent = JSON.stringify({ experiments: [] });
    expect(Experiments.getVariant('unknown')).toBeNull();
  });

  it('returns null when experimentId is empty', () => {
    expect(Experiments.getVariant('')).toBeNull();
    expect(Experiments.getVariant(null)).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// getAllAssignments
// ---------------------------------------------------------------------------
describe('getAllAssignments', () => {
  let configEl;

  beforeEach(() => {
    configEl = document.createElement('script');
    configEl.id = 'experiments-config';
    configEl.type = 'application/json';
    document.head.appendChild(configEl);
    document.cookie = 'te_uid=multi-test-uid; path=/';
  });

  afterEach(() => {
    if (configEl.parentNode) configEl.parentNode.removeChild(configEl);
    document.cookie = 'te_uid=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  });

  it('returns empty object when no experiments', () => {
    configEl.textContent = JSON.stringify({ experiments: [] });
    expect(Experiments.getAllAssignments()).toEqual({});
  });

  it('returns assignments for all active experiments', () => {
    configEl.textContent = JSON.stringify({
      experiments: [
        {
          id: 'a',
          status: 'active',
          variants: [{ id: 'av', traffic: 100 }],
        },
        {
          id: 'b',
          status: 'active',
          variants: [{ id: 'bv', traffic: 100 }],
        },
      ],
    });
    const out = Experiments.getAllAssignments();
    expect(out).toEqual({ a: 'av', b: 'bv' });
  });

  it('skips inactive experiments', () => {
    configEl.textContent = JSON.stringify({
      experiments: [
        { id: 'on', status: 'active', variants: [{ id: 'v', traffic: 100 }] },
        { id: 'off', status: 'paused', variants: [{ id: 'v', traffic: 100 }] },
      ],
    });
    const out = Experiments.getAllAssignments();
    expect(out).toEqual({ on: 'v' });
  });
});
