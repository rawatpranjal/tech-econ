/**
 * Tests for static/js/search/mmr.js (Re1 — MMR diversity rerank).
 */

import { beforeEach, describe, expect, it } from 'vitest';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const MMR_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/search/mmr.js'
);

let MMR;
beforeEach(() => {
  delete require.cache[MMR_PATH];
  MMR = require(MMR_PATH);
});

// -----------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------
const dim = 3;
function vec(...xs) {
  return new Float32Array(xs);
}
function makeItem(id, score, embedding) {
  return { id: id, name: id, rrfScore: score, _emb: embedding };
}
function lookupFromItems(items) {
  const map = {};
  for (const it of items) map[it.id] = it._emb || null;
  return (id) => map[id] || null;
}

// -----------------------------------------------------------------
// cosineSim
// -----------------------------------------------------------------
describe('cosineSim', () => {
  it('returns 1 for identical vectors', () => {
    expect(MMR.cosineSim(vec(1, 0, 0), vec(1, 0, 0))).toBeCloseTo(1, 6);
  });

  it('returns 0 for orthogonal vectors', () => {
    expect(MMR.cosineSim(vec(1, 0, 0), vec(0, 1, 0))).toBeCloseTo(0, 6);
  });

  it('returns -1 for opposite vectors', () => {
    expect(MMR.cosineSim(vec(1, 0, 0), vec(-1, 0, 0))).toBeCloseTo(-1, 6);
  });

  it('handles unequal lengths by returning 0', () => {
    expect(MMR.cosineSim(vec(1, 2, 3), vec(1, 2))).toBe(0);
  });

  it('handles zero norms by returning 0 (no NaN propagation)', () => {
    expect(MMR.cosineSim(vec(0, 0, 0), vec(1, 1, 1))).toBe(0);
    expect(MMR.cosineSim(vec(1, 1, 1), vec(0, 0, 0))).toBe(0);
  });

  it('handles null inputs gracefully', () => {
    expect(MMR.cosineSim(null, vec(1, 0, 0))).toBe(0);
    expect(MMR.cosineSim(vec(1, 0, 0), undefined)).toBe(0);
  });

  it('measures similarity for non-trivial vectors', () => {
    // Same direction, different magnitudes → cos = 1
    expect(MMR.cosineSim(vec(2, 0, 0), vec(5, 0, 0))).toBeCloseTo(1, 6);
    // 45-degree angle → cos = 1/sqrt(2)
    expect(MMR.cosineSim(vec(1, 1, 0), vec(1, 0, 0))).toBeCloseTo(1 / Math.sqrt(2), 6);
  });
});

// -----------------------------------------------------------------
// mmrRerank — base behaviour
// -----------------------------------------------------------------
describe('mmrRerank', () => {
  it('returns empty array for empty input', () => {
    expect(MMR.mmrRerank([], () => null, { lambda: 0.7 })).toEqual([]);
  });

  it('returns identity when no embedding lookup is provided', () => {
    const items = [
      makeItem('a', 1.0, null),
      makeItem('b', 0.9, null),
    ];
    const out = MMR.mmrRerank(items, null, { lambda: 0.5 });
    expect(out.map((i) => i.id)).toEqual(['a', 'b']);
  });

  it('returns identity when lambda = 1 (pure relevance, no MMR adjustment)', () => {
    const items = [
      makeItem('a', 1.0, vec(1, 0, 0)),
      makeItem('b', 0.9, vec(1, 0, 0)), // dup of a
      makeItem('c', 0.8, vec(0, 1, 0)),
    ];
    const out = MMR.mmrRerank(items, lookupFromItems(items), { lambda: 1.0 });
    expect(out.map((i) => i.id)).toEqual(['a', 'b', 'c']);
  });

  it('demotes a near-duplicate when lambda < 1', () => {
    // a (top relevance) and b (dup of a) compete. With lambda=0.5,
    // c's diversity bonus puts it ahead of the duplicate.
    const items = [
      makeItem('a', 1.0, vec(1, 0, 0)),
      makeItem('b', 0.95, vec(1, 0, 0)),  // identical embedding to a
      makeItem('c', 0.9, vec(0, 1, 0)),   // orthogonal to a
    ];
    const out = MMR.mmrRerank(items, lookupFromItems(items), { lambda: 0.5 });
    expect(out[0].id).toBe('a');           // highest-rel always picked first
    expect(out[1].id).toBe('c');           // diversity beats slightly-higher dup score
    expect(out[2].id).toBe('b');           // the dup ends up last
  });

  it('lambda = 0 picks pure-diversity ordering after the seed', () => {
    const items = [
      makeItem('a', 1.0, vec(1, 0, 0)),
      makeItem('b', 0.9, vec(1, 0, 0)),
      makeItem('c', 0.5, vec(0, 1, 0)),
    ];
    const out = MMR.mmrRerank(items, lookupFromItems(items), { lambda: 0.0 });
    // First pick is always the top-relevance item (a).
    // Second pick maximizes -max_sim_to_selected → orthogonal c wins.
    expect(out[0].id).toBe('a');
    expect(out[1].id).toBe('c');
  });

  it('respects topK', () => {
    const items = [
      makeItem('a', 1.0, vec(1, 0, 0)),
      makeItem('b', 0.9, vec(0, 1, 0)),
      makeItem('c', 0.8, vec(0, 0, 1)),
      makeItem('d', 0.7, vec(1, 1, 0)),
    ];
    const out = MMR.mmrRerank(items, lookupFromItems(items), { lambda: 0.7, topK: 2 });
    expect(out.length).toBe(2);
  });

  it('appends items without embeddings after the diverse set', () => {
    const items = [
      makeItem('a', 1.0, vec(1, 0, 0)),
      makeItem('b', 0.9, null), // no embedding
      makeItem('c', 0.8, vec(0, 1, 0)),
    ];
    const out = MMR.mmrRerank(items, lookupFromItems(items), { lambda: 0.5 });
    expect(out.map((i) => i.id)).toEqual(['a', 'c', 'b']);
  });

  it('clamps lambda outside [0, 1]', () => {
    const items = [
      makeItem('a', 1.0, vec(1, 0, 0)),
      makeItem('b', 0.9, vec(0, 1, 0)),
    ];
    expect(() => MMR.mmrRerank(items, lookupFromItems(items), { lambda: -1 })).not.toThrow();
    expect(() => MMR.mmrRerank(items, lookupFromItems(items), { lambda: 5 })).not.toThrow();
    // Clamping to 1 means identity output
    const out = MMR.mmrRerank(items, lookupFromItems(items), { lambda: 5 });
    expect(out.map((i) => i.id)).toEqual(['a', 'b']);
  });

  it('uses scoreField option to read relevance from a custom field', () => {
    const items = [
      { id: 'a', customScore: 0.5, _emb: vec(1, 0, 0), rrfScore: 999 },
      { id: 'b', customScore: 1.0, _emb: vec(0, 1, 0), rrfScore: 0 },
    ];
    const out = MMR.mmrRerank(items, lookupFromItems(items), {
      lambda: 1.0,
      scoreField: 'customScore',
    });
    // With pure-relevance lambda=1, b should win because customScore is higher.
    expect(out[0].id).toBe('b');
  });

  it('handles missing scoreField as 0 without crashing', () => {
    const items = [
      { id: 'a', _emb: vec(1, 0, 0) }, // no rrfScore at all
      { id: 'b', _emb: vec(0, 1, 0) },
    ];
    const out = MMR.mmrRerank(items, lookupFromItems(items), { lambda: 0.7 });
    expect(out.length).toBe(2);
  });

  it('topK=0 returns empty array', () => {
    const items = [makeItem('a', 1.0, vec(1, 0, 0))];
    expect(MMR.mmrRerank(items, lookupFromItems(items), { topK: 0 })).toEqual([]);
  });
});

// -----------------------------------------------------------------
// Realistic scenario: 10 items where 3 are near-duplicates
// -----------------------------------------------------------------
describe('mmrRerank — realistic scenario', () => {
  it('breaks up a triplet of near-duplicates near the top of the list', () => {
    const items = [
      // 3 near-duplicates (causal-inference cluster) at high relevance
      makeItem('causal-1', 0.95, vec(1.0, 0.05, 0.0)),
      makeItem('causal-2', 0.93, vec(1.0, 0.08, 0.0)),
      makeItem('causal-3', 0.91, vec(1.0, 0.06, 0.01)),
      // Diverse items at slightly lower scores
      makeItem('bayesian', 0.85, vec(0.0, 1.0, 0.0)),
      makeItem('time-series', 0.8, vec(0.0, 0.0, 1.0)),
      makeItem('econometrics', 0.75, vec(0.5, 0.5, 0.0)),
    ];

    const lookup = lookupFromItems(items);
    const baseline = MMR.mmrRerank(items, lookup, { lambda: 1.0, topK: 4 });
    const diversified = MMR.mmrRerank(items, lookup, { lambda: 0.7, topK: 4 });

    // Baseline: pure relevance — all 3 causals at the top
    expect(baseline.slice(0, 3).map((i) => i.id)).toEqual(['causal-1', 'causal-2', 'causal-3']);

    // Diversified: causal-1 wins seat 1; seats 2-3 should NOT both be other causals.
    // At minimum, NOT all of causal-2 and causal-3 should appear in top-3.
    const top3Diversified = diversified.slice(0, 3).map((i) => i.id);
    const causalCountInTop3 = top3Diversified.filter((id) => id.startsWith('causal-')).length;
    expect(causalCountInTop3).toBeLessThanOrEqual(2);
    // The first item is always the highest-relevance seed
    expect(top3Diversified[0]).toBe('causal-1');
  });
});
