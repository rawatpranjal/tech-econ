/**
 * Tests for static/js/search/search-synonyms.js
 *
 * CommonJS exports: { SYNONYMS, expandQuery, getSynonyms }
 * Tests the core domain-term expansion logic used by both search-worker.js
 * and unified-search.js.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const SYNS_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/search/search-synonyms.js'
);

let SS;
beforeEach(() => {
  delete require.cache[SYNS_PATH];
  SS = require(SYNS_PATH);
});

// -----------------------------------------------------------------
// getSynonyms
// -----------------------------------------------------------------
describe('getSynonyms', () => {
  it('returns array of synonyms for known term', () => {
    const syns = SS.getSynonyms('dml');
    expect(Array.isArray(syns)).toBe(true);
    expect(syns.length).toBeGreaterThan(0);
  });

  it('returns empty array for unknown term', () => {
    expect(SS.getSynonyms('zzz_unknown_zzz')).toEqual([]);
  });

  it('is case-insensitive', () => {
    const lower = SS.getSynonyms('did');
    const upper = SS.getSynonyms('DID');
    expect(lower).toEqual(upper);
  });

  it('DiD expands to difference-in-differences variants', () => {
    const syns = SS.getSynonyms('did');
    const joined = syns.join(' ').toLowerCase();
    expect(joined).toContain('difference-in-differences');
  });

  it('rdd expands to regression discontinuity variants', () => {
    const syns = SS.getSynonyms('rdd');
    const joined = syns.join(' ').toLowerCase();
    expect(joined).toContain('regression discontinuity');
  });

  it('iv expands to instrumental variable variants', () => {
    const syns = SS.getSynonyms('iv');
    const joined = syns.join(' ').toLowerCase();
    expect(joined).toContain('instrumental');
  });

  it('dml expands to double machine learning variants', () => {
    const syns = SS.getSynonyms('dml');
    const joined = syns.join(' ').toLowerCase();
    expect(joined).toContain('double machine learning');
  });

  it('ml expands to machine learning', () => {
    const syns = SS.getSynonyms('ml');
    expect(syns.join(' ').toLowerCase()).toContain('machine learning');
  });
});

// -----------------------------------------------------------------
// expandQuery
// -----------------------------------------------------------------
describe('expandQuery', () => {
  it('always includes the original query', () => {
    const results = SS.expandQuery('causal');
    expect(results).toContain('causal');
  });

  it('expands known terms', () => {
    const results = SS.expandQuery('did');
    expect(results.length).toBeGreaterThan(1);
  });

  it('returns original query alone for unknown terms', () => {
    const results = SS.expandQuery('zzz_no_match_zzz');
    expect(results).toEqual(['zzz_no_match_zzz']);
  });

  it('expands multi-word query (each word looked up)', () => {
    const results = SS.expandQuery('did rdd');
    // Should include expansions from both 'did' and 'rdd'
    const joined = results.join(' ').toLowerCase();
    expect(joined).toContain('difference-in-differences');
    expect(joined).toContain('regression discontinuity');
  });

  it('does not include duplicate entries', () => {
    const results = SS.expandQuery('did did');
    const unique = [...new Set(results)];
    expect(results.length).toBe(unique.length);
  });

  it('returns same expansions regardless of case (normalized comparison)', () => {
    const lower = SS.expandQuery('dml').map(s => s.toLowerCase()).sort();
    const upper = SS.expandQuery('DML').map(s => s.toLowerCase()).sort();
    // After lowercasing, dedup, and sort, both should be identical
    const lowerUniq = [...new Set(lower)];
    const upperUniq = [...new Set(upper)];
    expect(lowerUniq).toEqual(upperUniq);
  });
});

// -----------------------------------------------------------------
// SYNONYMS object integrity
// -----------------------------------------------------------------
describe('SYNONYMS object', () => {
  it('exists and is a non-empty object', () => {
    expect(typeof SS.SYNONYMS).toBe('object');
    expect(Object.keys(SS.SYNONYMS).length).toBeGreaterThan(50);
  });

  it('every key is lowercase', () => {
    for (const key of Object.keys(SS.SYNONYMS)) {
      expect(key).toBe(key.toLowerCase());
    }
  });

  it('every value is a non-empty array', () => {
    for (const [key, val] of Object.entries(SS.SYNONYMS)) {
      expect(Array.isArray(val), `${key} should be an array`).toBe(true);
      expect(val.length, `${key} should have synonyms`).toBeGreaterThan(0);
    }
  });

  it('every synonym string is non-empty', () => {
    for (const [key, val] of Object.entries(SS.SYNONYMS)) {
      for (const syn of val) {
        expect(typeof syn, `${key} synonym should be string`).toBe('string');
        expect(syn.length, `${key} has empty synonym`).toBeGreaterThan(0);
      }
    }
  });
});
