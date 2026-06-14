/**
 * Tests for static/js/search/query-parser.js
 *
 * Module uses CommonJS exports (same pattern as spellcheck.js).
 * Covers: parse(), matchesFilters(), describe().
 */

import { beforeEach, describe, expect, it } from 'vitest';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const PARSER_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/search/query-parser.js'
);

let QP;
beforeEach(() => {
  delete require.cache[PARSER_PATH];
  QP = require(PARSER_PATH);
});

// -----------------------------------------------------------------
// parse() — empty / null input
// -----------------------------------------------------------------
describe('parse: empty input', () => {
  it('returns valid empty structure for null', () => {
    const r = QP.parse(null);
    expect(r.phrases).toEqual([]);
    expect(r.fields).toEqual({});
    expect(r.negations).toEqual({ terms: [], phrases: [] });
    expect(r.terms).toEqual([]);
    expect(r.cleanQuery).toBe('');
  });

  it('returns valid empty structure for empty string', () => {
    const r = QP.parse('');
    expect(r.terms).toEqual([]);
  });

  it('returns valid empty structure for whitespace', () => {
    const r = QP.parse('   ');
    expect(r.terms).toEqual([]);
  });
});

// -----------------------------------------------------------------
// parse() — plain terms
// -----------------------------------------------------------------
describe('parse: plain terms', () => {
  it('splits plain terms into array', () => {
    const r = QP.parse('causal inference regression');
    expect(r.terms).toEqual(['causal', 'inference', 'regression']);
  });

  it('lowercases terms', () => {
    const r = QP.parse('Causal Inference');
    expect(r.terms).toEqual(['causal', 'inference']);
  });

  it('cleanQuery includes all plain terms', () => {
    const r = QP.parse('double ml');
    expect(r.cleanQuery).toContain('double');
    expect(r.cleanQuery).toContain('ml');
  });
});

// -----------------------------------------------------------------
// parse() — quoted phrases
// -----------------------------------------------------------------
describe('parse: quoted phrases', () => {
  it('extracts exact phrase', () => {
    const r = QP.parse('"causal inference"');
    expect(r.phrases).toContain('causal inference');
    expect(r.terms).toHaveLength(0);
  });

  it('extracts phrase and remaining terms', () => {
    const r = QP.parse('"causal inference" regression');
    expect(r.phrases).toContain('causal inference');
    expect(r.terms).toContain('regression');
  });

  it('phrase ends up in cleanQuery', () => {
    const r = QP.parse('"machine learning"');
    expect(r.cleanQuery).toContain('machine learning');
  });

  it('multiple phrases extracted', () => {
    const r = QP.parse('"causal inference" "difference in differences"');
    expect(r.phrases).toHaveLength(2);
  });
});

// -----------------------------------------------------------------
// parse() — negated phrases
// -----------------------------------------------------------------
describe('parse: negations', () => {
  it('extracts negated term', () => {
    const r = QP.parse('causal -regression');
    expect(r.negations.terms).toContain('regression');
    expect(r.terms).toContain('causal');
  });

  it('negated phrase goes to negations.phrases', () => {
    const r = QP.parse('-"linear regression"');
    expect(r.negations.phrases).toContain('linear regression');
    expect(r.phrases).toHaveLength(0);
  });

  it('single-char negations are ignored', () => {
    const r = QP.parse('-a causal');
    expect(r.negations.terms).toHaveLength(0);
    expect(r.terms).toContain('causal');
  });
});

// -----------------------------------------------------------------
// parse() — field filters
// -----------------------------------------------------------------
describe('parse: field filters', () => {
  it('extracts author field', () => {
    const r = QP.parse('author:Athey');
    expect(r.fields).toHaveProperty('author');
    expect(r.fields.author).toContain('Athey');
  });

  it('normalizes author aliases: "by:" -> author', () => {
    const r = QP.parse('by:Smith');
    expect(r.fields).toHaveProperty('author');
  });

  it('normalizes author aliases: "authors:" -> author', () => {
    const r = QP.parse('authors:Imbens');
    expect(r.fields).toHaveProperty('author');
  });

  it('extracts year field', () => {
    const r = QP.parse('year:2024');
    expect(r.fields).toHaveProperty('year');
    expect(r.fields.year).toContain('2024');
  });

  it('normalizes "date:" -> year', () => {
    const r = QP.parse('date:2023');
    expect(r.fields).toHaveProperty('year');
  });

  it('extracts topic field', () => {
    const r = QP.parse('topic:Causal');
    expect(r.fields).toHaveProperty('topic');
  });

  it('normalizes "area:" -> topic', () => {
    const r = QP.parse('area:ML');
    expect(r.fields).toHaveProperty('topic');
  });

  it('extracts type field', () => {
    const r = QP.parse('type:package');
    expect(r.fields).toHaveProperty('type');
    expect(r.fields.type).toContain('package');
  });

  it('unknown field names are ignored', () => {
    const r = QP.parse('foo:bar');
    expect(r.fields).toEqual({});
    // "bar" stays as remaining text but field "foo" is not recognized
  });

  it('field filter does not leak into terms', () => {
    const r = QP.parse('author:Athey causal');
    expect(r.terms).not.toContain('author:athey');
    expect(r.terms).toContain('causal');
  });
});

// -----------------------------------------------------------------
// parse() — combined query
// -----------------------------------------------------------------
describe('parse: combined query', () => {
  it('handles full complex query', () => {
    const r = QP.parse('"double debiased" ml author:Chernozhukov year:2018 -neural');
    expect(r.phrases).toContain('double debiased');
    expect(r.fields).toHaveProperty('author');
    expect(r.fields).toHaveProperty('year');
    expect(r.negations.terms).toContain('neural');
    expect(r.terms).toContain('ml');
  });
});

// -----------------------------------------------------------------
// matchesFilters()
// -----------------------------------------------------------------
describe('matchesFilters', () => {
  it('passes when no filters', () => {
    const pq = QP.parse('causal');
    const result = { name: 'Anything', type: 'package' };
    expect(QP.matchesFilters(result, pq)).toBe(true);
  });

  it('matches author field', () => {
    const pq = QP.parse('author:Athey');
    expect(QP.matchesFilters({ authors: 'Susan Athey' }, pq)).toBe(true);
    expect(QP.matchesFilters({ authors: 'John Smith' }, pq)).toBe(false);
  });

  it('matches year field exactly', () => {
    const pq = QP.parse('year:2024');
    expect(QP.matchesFilters({ year: 2024 }, pq)).toBe(true);
    expect(QP.matchesFilters({ year: 2023 }, pq)).toBe(false);
    expect(QP.matchesFilters({ year: null }, pq)).toBe(false);
  });

  it('matches topic field (substring)', () => {
    const pq = QP.parse('topic:Causal');
    expect(QP.matchesFilters({ topic: 'Causal Inference' }, pq)).toBe(true);
    expect(QP.matchesFilters({ topic: 'Deep Learning' }, pq)).toBe(false);
  });

  it('matches type field exactly', () => {
    const pq = QP.parse('type:package');
    expect(QP.matchesFilters({ type: 'package' }, pq)).toBe(true);
    expect(QP.matchesFilters({ type: 'dataset' }, pq)).toBe(false);
  });

  it('requires ALL field filters to match', () => {
    const pq = QP.parse('author:Athey year:2024');
    expect(QP.matchesFilters({ authors: 'Athey', year: 2024 }, pq)).toBe(true);
    expect(QP.matchesFilters({ authors: 'Athey', year: 2020 }, pq)).toBe(false);
    expect(QP.matchesFilters({ authors: 'Smith', year: 2024 }, pq)).toBe(false);
  });
});

// -----------------------------------------------------------------
// describe()
// -----------------------------------------------------------------
describe('describe', () => {
  it('returns empty string for empty query', () => {
    const pq = QP.parse('');
    expect(QP.describe(pq)).toBe('');
  });

  it('includes terms in description', () => {
    const pq = QP.parse('causal ml');
    expect(QP.describe(pq)).toContain('causal');
  });

  it('includes phrase in description', () => {
    const pq = QP.parse('"causal inference"');
    expect(QP.describe(pq)).toContain('causal inference');
  });

  it('includes field filter in description', () => {
    const pq = QP.parse('author:Athey');
    const desc = QP.describe(pq);
    expect(desc).toContain('author');
    expect(desc).toContain('Athey');
  });

  it('includes negations in description', () => {
    const pq = QP.parse('-neural');
    expect(QP.describe(pq)).toContain('neural');
  });
});
