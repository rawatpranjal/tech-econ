/**
 * Tests for static/js/search/spellcheck.js (Re2).
 *
 * The module is the AMD/CommonJS/global-export pattern from
 * search-synonyms.js. We require() it directly here.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const SPELLCHECK_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/search/spellcheck.js'
);

let Spellcheck;
beforeEach(() => {
  // Re-require fresh in case other tests hold references
  delete require.cache[SPELLCHECK_PATH];
  Spellcheck = require(SPELLCHECK_PATH);
});

describe('levenshtein', () => {
  it('returns 0 for identical strings', () => {
    expect(Spellcheck.levenshtein('foo', 'foo')).toBe(0);
  });

  it('handles empty inputs', () => {
    expect(Spellcheck.levenshtein('', '')).toBe(0);
    expect(Spellcheck.levenshtein('', 'abc')).toBe(3);
    expect(Spellcheck.levenshtein('abc', '')).toBe(3);
  });

  it('measures simple edits correctly (no cap)', () => {
    expect(Spellcheck.levenshtein('cat', 'bat', 5)).toBe(1); // substitution
    expect(Spellcheck.levenshtein('cat', 'cats', 5)).toBe(1); // insertion
    expect(Spellcheck.levenshtein('cats', 'cat', 5)).toBe(1); // deletion
    expect(Spellcheck.levenshtein('kitten', 'sitting', 5)).toBe(3); // classic
  });

  it('respects the cap by returning cap+1 for distant strings', () => {
    expect(Spellcheck.levenshtein('aaaaaa', 'bbbbbb', 2)).toBe(3); // cap=2, real=6
    expect(Spellcheck.levenshtein('hello', 'world', 1)).toBe(2); // cap=1, real=4
  });

  it('handles common typo patterns', () => {
    expect(Spellcheck.levenshtein('inferance', 'inference', 3)).toBe(1); // a→e
    expect(Spellcheck.levenshtein('causel', 'causal', 3)).toBe(1);
    expect(Spellcheck.levenshtein('econometrcs', 'econometrics', 3)).toBe(1); // missing 'i'
  });
});

describe('buildVocabulary', () => {
  it('returns an empty Set for empty input', () => {
    expect(Spellcheck.buildVocabulary([]).size).toBe(0);
    expect(Spellcheck.buildVocabulary(null).size).toBe(0);
  });

  it('lowercases and tokenises on non-letter chars', () => {
    const v = Spellcheck.buildVocabulary(['Causal Inference: A Primer']);
    expect(v.has('causal')).toBe(true);
    expect(v.has('inference')).toBe(true);
    expect(v.has('primer')).toBe(true);
  });

  it('skips short words (<4 chars)', () => {
    const v = Spellcheck.buildVocabulary(['a an the foo bar baz']);
    // "the" has 3 chars, would also be a stop-word so filtered both ways
    expect(v.has('a')).toBe(false);
    expect(v.has('an')).toBe(false);
    expect(v.has('the')).toBe(false);
    // "foo", "bar", "baz" are 3 chars too — also filtered
    expect(v.has('foo')).toBe(false);
  });

  it('drops common English stop words even if long enough', () => {
    const v = Spellcheck.buildVocabulary(['this and that with from these those']);
    expect(v.has('this')).toBe(false);
    expect(v.has('that')).toBe(false);
    expect(v.has('these')).toBe(false);
    expect(v.has('those')).toBe(false);
  });

  it('handles arrays with null/undefined entries gracefully', () => {
    const v = Spellcheck.buildVocabulary([null, undefined, 'word here', '']);
    expect(v.has('word')).toBe(true);
    expect(v.has('here')).toBe(true);
  });
});

describe('closestMatch', () => {
  it('returns null for words already in the vocabulary', () => {
    const vocab = new Set(['causal', 'inference']);
    expect(Spellcheck.closestMatch('causal', vocab)).toBeNull();
  });

  it('returns null for short tokens (<4 chars)', () => {
    const vocab = new Set(['causal', 'inference']);
    expect(Spellcheck.closestMatch('cau', vocab)).toBeNull();
  });

  it('finds an obvious typo within distance 1', () => {
    const vocab = new Set(['causal', 'inference', 'econometrics']);
    expect(Spellcheck.closestMatch('inferance', vocab)).toBe('inference');
    expect(Spellcheck.closestMatch('causel', vocab)).toBe('causal');
  });

  it('finds typos within distance 2', () => {
    const vocab = new Set(['inference']);
    expect(Spellcheck.closestMatch('inferanc', vocab)).toBe('inference');
  });

  it('returns null when no candidate is within MAX_EDIT_DISTANCE', () => {
    const vocab = new Set(['causal']);
    expect(Spellcheck.closestMatch('completely-unrelated', vocab)).toBeNull();
  });
});

describe('suggest', () => {
  let vocab;
  beforeEach(() => {
    vocab = Spellcheck.buildVocabulary([
      'Causal Inference and Difference-in-Differences',
      'Econometrics with Regression',
      'Bayesian Statistics',
      'Time Series Forecasting',
    ]);
  });

  it('returns null when nothing in the query is misspelled', () => {
    expect(Spellcheck.suggest('causal inference', vocab)).toBeNull();
  });

  it('returns null on empty query', () => {
    expect(Spellcheck.suggest('', vocab)).toBeNull();
    expect(Spellcheck.suggest(null, vocab)).toBeNull();
  });

  it('returns null when vocab is empty', () => {
    expect(Spellcheck.suggest('inferance', new Set())).toBeNull();
  });

  it('corrects a single-word typo', () => {
    const result = Spellcheck.suggest('inferance', vocab);
    expect(result).not.toBeNull();
    expect(result.changed).toBe(true);
    expect(result.corrected).toBe('inference');
  });

  it('corrects one word in a multi-word query and preserves the rest', () => {
    const result = Spellcheck.suggest('causel inference', vocab);
    expect(result).not.toBeNull();
    expect(result.corrected).toBe('causal inference');
  });

  it('preserves whitespace between tokens', () => {
    const result = Spellcheck.suggest('causel  inference', vocab);
    expect(result).not.toBeNull();
    expect(result.corrected).toBe('causal  inference');
  });

  it('does not "correct" short words like "of", "and"', () => {
    // "of" is 2 chars; even if vocab contains "off" we shouldn't replace
    const v = new Set(['off']);
    const result = Spellcheck.suggest('of', v);
    expect(result).toBeNull();
  });

  it('returns null for completely-unrecognised tokens (no good match)', () => {
    const result = Spellcheck.suggest('xyzzyfoobarqux', vocab);
    expect(result).toBeNull();
  });
});
