/**
 * Tests for pure scoring/boosting helpers in search-worker.js:
 *   scoreSyntheticQuestions, getAudienceBoost, getModelScoreBoost,
 *   boostExactMatches, escapeRegex, reciprocalRankFusion
 *
 * Strategy: strip the importScripts() calls and the onmessage handler
 * (both require Worker context), then load the pure functions.
 * Expose them via a global shim block appended to the source.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const WORKER_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/search/search-worker.js'
);
const RAW = fs.readFileSync(WORKER_PATH, 'utf8');

// Strip importScripts calls (not available in jsdom) and the last postMessage
// The file ends with: postMessage({ type: 'WORKER_READY' });
const STRIPPED = RAW
  .replace(/^importScripts\(.*\);?\s*$/gm, '/* importScripts stripped */')
  .replace(/postMessage\(\{[^}]*WORKER_READY[^}]*\}\);?\s*$/, '/* WORKER_READY stripped */');

// Append test-surface exposure
const TESTABLE = STRIPPED + `
if (typeof window !== 'undefined') {
  window._searchWorkerHelpers = {
    scoreSyntheticQuestions,
    getAudienceBoost,
    getModelScoreBoost,
    boostExactMatches,
    escapeRegex,
    reciprocalRankFusion,
    expandQuery,
    maybeSuggestion,
    // setters so tests can inject module-level state
    setSynonyms: function(s) { synonyms = s; },
    setSpellcheckVocab: function(v) { spellcheckVocab = v; },
  };
}
`;

function loadWorker() {
  // Stub postMessage globally (worker uses it throughout)
  window.postMessage = () => {};
  // Stub MiniSearch class (referenced at module level via miniSearch variable)
  window.MiniSearch = class { constructor() {} };
  // eslint-disable-next-line no-new-func
  new Function(TESTABLE).call(window);
}

beforeEach(() => {
  delete window._searchWorkerHelpers;
  loadWorker();
});

afterEach(() => {
  delete window._searchWorkerHelpers;
  delete window.MiniSearch;
});

const H = () => window._searchWorkerHelpers;

// ──────────────────────────────────────────────
// escapeRegex
// ──────────────────────────────────────────────
describe('escapeRegex', () => {
  it('escapes dots', () => {
    expect(H().escapeRegex('a.b')).toBe('a\\.b');
  });

  it('escapes asterisk', () => {
    expect(H().escapeRegex('a*b')).toBe('a\\*b');
  });

  it('escapes parentheses', () => {
    expect(H().escapeRegex('(test)')).toBe('\\(test\\)');
  });

  it('passes clean strings unchanged', () => {
    expect(H().escapeRegex('hello world')).toBe('hello world');
  });

  it('empty string returns empty', () => {
    expect(H().escapeRegex('')).toBe('');
  });
});

// ──────────────────────────────────────────────
// scoreSyntheticQuestions
// ──────────────────────────────────────────────
describe('scoreSyntheticQuestions', () => {
  it('returns 0 for null synthetic_questions', () => {
    expect(H().scoreSyntheticQuestions({}, 'causal inference')).toBe(0);
  });

  it('returns 0 for null query', () => {
    expect(H().scoreSyntheticQuestions({ synthetic_questions: ['how do I do causal inference?'] }, null)).toBe(0);
  });

  it('returns 0.3 for full query match', () => {
    const item = { synthetic_questions: ['what is causal inference and how does it work?'] };
    expect(H().scoreSyntheticQuestions(item, 'causal inference')).toBe(0.3);
  });

  it('returns 0 for no word overlap', () => {
    const item = { synthetic_questions: ['how to cook pasta quickly'] };
    expect(H().scoreSyntheticQuestions(item, 'causal regression econometrics')).toBe(0);
  });

  it('skips non-string entries', () => {
    const item = { synthetic_questions: [null, 42, 'causal inference methods'] };
    const result = H().scoreSyntheticQuestions(item, 'causal inference');
    expect(result).toBeGreaterThanOrEqual(0);
    expect(result).toBeLessThanOrEqual(0.3);
  });

  it('returns 0 when synthetic_questions is not an array', () => {
    const item = { synthetic_questions: 'some string' };
    expect(H().scoreSyntheticQuestions(item, 'causal')).toBe(0);
  });
});

// ──────────────────────────────────────────────
// getModelScoreBoost
// ──────────────────────────────────────────────
describe('getModelScoreBoost', () => {
  it('returns 1.0 for missing model_score', () => {
    expect(H().getModelScoreBoost({}, 0.4)).toBe(1.0);
  });

  it('returns 1.0 for NaN model_score', () => {
    expect(H().getModelScoreBoost({ model_score: NaN }, 0.4)).toBe(1.0);
  });

  it('returns 1.0 for model_score 0', () => {
    expect(H().getModelScoreBoost({ model_score: 0 }, 0.4)).toBe(1.0);
  });

  it('returns 1.0 + weight for model_score 1.0', () => {
    expect(H().getModelScoreBoost({ model_score: 1.0 }, 0.4)).toBeCloseTo(1.4);
  });

  it('returns 1.0 + (0.5 * weight) for model_score 0.5', () => {
    expect(H().getModelScoreBoost({ model_score: 0.5 }, 0.4)).toBeCloseTo(1.2);
  });

  it('clamps out-of-range scores to [0, 1]', () => {
    // score > 1 should be treated as 1
    const high = H().getModelScoreBoost({ model_score: 2.0 }, 0.4);
    const low = H().getModelScoreBoost({ model_score: -1.0 }, 0.4);
    expect(high).toBeCloseTo(1.4);
    expect(low).toBeCloseTo(1.0);
  });
});

// ──────────────────────────────────────────────
// getAudienceBoost
// ──────────────────────────────────────────────
describe('getAudienceBoost', () => {
  it('returns 1.0 for missing audience', () => {
    expect(H().getAudienceBoost({}, 'intro to causal inference')).toBe(1.0);
  });

  it('returns 1.0 for missing query', () => {
    expect(H().getAudienceBoost({ audience: 'Beginner' }, null)).toBe(1.0);
  });

  it('returns 1.25 for beginner content on beginner query', () => {
    const result = H().getAudienceBoost({ audience: 'Beginner' }, 'intro to regression');
    expect(result).toBe(1.25);
  });

  it('returns 0.85 for advanced content on beginner query', () => {
    const result = H().getAudienceBoost({ audience: 'PhD' }, 'getting started with econometrics');
    expect(result).toBe(0.85);
  });

  it('returns 1.2 for advanced content on advanced query', () => {
    const result = H().getAudienceBoost({ audience: 'Senior-DS' }, 'advanced optimal algorithm proof');
    expect(result).toBe(1.2);
  });

  it('returns 1.0 for neutral query with beginner content', () => {
    const result = H().getAudienceBoost({ audience: 'Beginner' }, 'causal inference methods');
    expect(result).toBe(1.0);
  });

  it('handles array audience by joining', () => {
    const result = H().getAudienceBoost({ audience: ['Beginner', 'Junior-DS'] }, 'intro to ml');
    expect(result).toBe(1.25);
  });
});

// ──────────────────────────────────────────────
// boostExactMatches
// ──────────────────────────────────────────────
describe('boostExactMatches', () => {
  it('exact name match gets 3.0 boost', () => {
    const results = [{ name: 'DoubleML', score: 1.0 }];
    const boosted = H().boostExactMatches(results, 'doubleml');
    expect(boosted[0].score).toBeCloseTo(3.0);
  });

  it('name starts with query gets 2.0 boost', () => {
    const results = [{ name: 'DoubleML Package', score: 1.0 }];
    const boosted = H().boostExactMatches(results, 'doubleml');
    expect(boosted[0].score).toBeCloseTo(2.0);
  });

  it('no match returns 1.0 base boost', () => {
    const results = [{ name: 'Completely Different', description: 'nothing here', score: 1.0 }];
    const boosted = H().boostExactMatches(results, 'randomquery');
    expect(boosted[0].score).toBeCloseTo(1.0);
  });

  it('returns sorted results descending by score', () => {
    const results = [
      { name: 'Unrelated', score: 1.0 },
      { name: 'doubleml', score: 0.5 },
    ];
    const boosted = H().boostExactMatches(results, 'doubleml');
    expect(boosted[0].score).toBeGreaterThan(boosted[1].score);
  });

  it('paper/package type gets additional boost', () => {
    const r1 = [{ name: 'Tool', type: 'package', score: 1.0 }];
    const r2 = [{ name: 'Tool', type: 'dataset', score: 1.0 }];
    const b1 = H().boostExactMatches(r1, 'random query')[0].score;
    const b2 = H().boostExactMatches(r2, 'random query')[0].score;
    expect(b1).toBeGreaterThan(b2);
  });

  it('does not mutate input array', () => {
    const original = [{ name: 'Tool', score: 1.0 }];
    const originalScore = original[0].score;
    H().boostExactMatches(original, 'query');
    expect(original[0].score).toBe(originalScore);
  });
});

// ──────────────────────────────────────────────
// reciprocalRankFusion
// ──────────────────────────────────────────────
describe('reciprocalRankFusion', () => {
  const makeItem = (id, score = 1.0) => ({ id, name: id, score, description: '' });

  it('returns empty array for empty inputs', () => {
    const result = H().reciprocalRankFusion([], [], 10, '');
    expect(result).toEqual([]);
  });

  it('returns keyword-only results when semantic is empty', () => {
    const kw = [makeItem('a'), makeItem('b')];
    const result = H().reciprocalRankFusion(kw, [], 10, 'query');
    expect(result.length).toBe(2);
    const ids = result.map(r => r.id);
    expect(ids).toContain('a');
    expect(ids).toContain('b');
  });

  it('merges keyword and semantic results', () => {
    const kw = [makeItem('a')];
    const sem = [makeItem('b', 0.9)];
    const result = H().reciprocalRankFusion(kw, sem, 10, 'query');
    const ids = result.map(r => r.id);
    expect(ids).toContain('a');
    expect(ids).toContain('b');
  });

  it('item in both lists scores higher than item in one', () => {
    const item = makeItem('shared', 1.0);
    const kw = [item, makeItem('kw-only')];
    const sem = [item, makeItem('sem-only', 0.9)];
    const result = H().reciprocalRankFusion(kw, sem, 10, 'query');
    const sharedScore = result.find(r => r.id === 'shared').rrfScore;
    const kwOnlyScore = result.find(r => r.id === 'kw-only').rrfScore;
    expect(sharedScore).toBeGreaterThan(kwOnlyScore);
  });

  it('results are sorted descending by rrfScore', () => {
    const kw = [makeItem('a', 2.0), makeItem('b', 0.5)];
    const sem = [makeItem('a', 0.8)];
    const result = H().reciprocalRankFusion(kw, sem, 10, 'query');
    for (let i = 1; i < result.length; i++) {
      expect(result[i - 1].rrfScore).toBeGreaterThanOrEqual(result[i].rrfScore);
    }
  });

  it('each result has rrfScore property', () => {
    const kw = [makeItem('x')];
    const result = H().reciprocalRankFusion(kw, [], 10, 'test');
    expect(typeof result[0].rrfScore).toBe('number');
  });

  it('source is set to hybrid', () => {
    const kw = [makeItem('x')];
    const result = H().reciprocalRankFusion(kw, [], 10, 'test');
    expect(result[0].source).toBe('hybrid');
  });
});

// ──────────────────────────────────────────────
// expandQuery
// ──────────────────────────────────────────────
describe('expandQuery', () => {
  afterEach(() => {
    // Reset synonyms to null after each test
    H().setSynonyms(null);
  });

  it('returns [query] when synonyms is null', () => {
    H().setSynonyms(null);
    expect(H().expandQuery('causal inference')).toEqual(['causal inference']);
  });

  it('returns [query] when no synonym match', () => {
    H().setSynonyms({ 'regression': ['ols', 'linear model'] });
    expect(H().expandQuery('causal')).toEqual(['causal']);
  });

  it('adds synonyms for matching word', () => {
    H().setSynonyms({ 'causal': ['causal inference', 'treatment effects'] });
    const result = H().expandQuery('causal');
    expect(result).toContain('causal');
    expect(result).toContain('causal inference');
    expect(result).toContain('treatment effects');
  });

  it('deduplicates synonyms already in expanded list', () => {
    H().setSynonyms({ 'ml': ['machine learning', 'ml'] });
    const result = H().expandQuery('ml');
    const mlCount = result.filter(r => r === 'ml').length;
    expect(mlCount).toBe(1);
  });

  it('expands multiple words in the query', () => {
    H().setSynonyms({
      'ab': ['a/b testing', 'experiment'],
      'test': ['experiment', 'trial'],
    });
    const result = H().expandQuery('ab test');
    expect(result).toContain('a/b testing');
    expect(result).toContain('experiment');
  });

  it('query is always the first element', () => {
    H().setSynonyms({ 'ml': ['machine learning'] });
    const result = H().expandQuery('ml');
    expect(result[0]).toBe('ml');
  });
});

// ──────────────────────────────────────────────
// maybeSuggestion
// ──────────────────────────────────────────────
describe('maybeSuggestion', () => {
  afterEach(() => {
    H().setSpellcheckVocab(null);
    delete window.Spellcheck;
  });

  it('returns null when results are non-empty', () => {
    expect(H().maybeSuggestion('qurey', [{ id: 'a' }])).toBeNull();
  });

  it('returns null when results is null', () => {
    expect(H().maybeSuggestion('qurey', null)).toBeNull();
  });

  it('returns null when spellcheckVocab is null', () => {
    H().setSpellcheckVocab(null);
    expect(H().maybeSuggestion('qurey', [])).toBeNull();
  });

  it('returns null when Spellcheck is undefined', () => {
    H().setSpellcheckVocab(new Set(['query']));
    delete window.Spellcheck;
    expect(H().maybeSuggestion('qurey', [])).toBeNull();
  });

  it('returns corrected string when suggestion differs from query', () => {
    H().setSpellcheckVocab(new Set(['query']));
    window.Spellcheck = { suggest: () => ({ changed: true, corrected: 'query' }) };
    expect(H().maybeSuggestion('qurey', [])).toBe('query');
  });

  it('returns null when suggestion equals original query', () => {
    H().setSpellcheckVocab(new Set(['qurey']));
    window.Spellcheck = { suggest: () => ({ changed: false, corrected: 'qurey' }) };
    expect(H().maybeSuggestion('qurey', [])).toBeNull();
  });

  it('returns null when suggest returns null', () => {
    H().setSpellcheckVocab(new Set(['query']));
    window.Spellcheck = { suggest: () => null };
    expect(H().maybeSuggestion('qurey', [])).toBeNull();
  });
});
