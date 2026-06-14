/**
 * Tests for pure helper functions in submit-worker/index.js:
 *   validateSubmission, isValidUrl, extractDomain
 *
 * Strategy: same export-strip approach as analytics-worker tests.
 * The `export default { ... };` ends at line ~70; everything after is
 * module-level function declarations.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const WORKER_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../submit-worker/index.js'
);
const RAW = fs.readFileSync(WORKER_PATH, 'utf8');

// Strip the `export default { ... };` block (ends at first bare `};` after it)
// and expose pure helpers to window.
const WORKER_TESTABLE = RAW
  .replace(/^export default \{[\s\S]*?\n\};/m, '/* export default stripped */')
  + `
if (typeof window !== 'undefined') {
  window._submitHelpers = {
    validateSubmission,
    isValidUrl,
    extractDomain,
    mapToSchema,
    getCategories,
  };
}
`;

function loadWorker() {
  if (!window.Response) {
    window.Response = class Response {
      constructor(body, init) { this.body = body; this.status = (init || {}).status || 200; }
    };
  }
  // eslint-disable-next-line no-new-func
  new Function(WORKER_TESTABLE).call(window);
}

beforeEach(() => {
  delete window._submitHelpers;
  loadWorker();
});

afterEach(() => {
  delete window._submitHelpers;
});

// ──────────────────────────────────────────────
// isValidUrl
// ──────────────────────────────────────────────
describe('isValidUrl', () => {
  it('accepts https URL', () => {
    expect(window._submitHelpers.isValidUrl('https://github.com/org/repo')).toBe(true);
  });

  it('accepts http URL', () => {
    expect(window._submitHelpers.isValidUrl('http://example.com')).toBe(true);
  });

  it('rejects plain text', () => {
    expect(window._submitHelpers.isValidUrl('not-a-url')).toBe(false);
  });

  it('rejects empty string', () => {
    expect(window._submitHelpers.isValidUrl('')).toBe(false);
  });

  it('rejects ftp protocol', () => {
    expect(window._submitHelpers.isValidUrl('ftp://files.example.com')).toBe(false);
  });

  it('rejects javascript: scheme', () => {
    expect(window._submitHelpers.isValidUrl('javascript:alert(1)')).toBe(false);
  });

  it('accepts URL with path and query', () => {
    expect(window._submitHelpers.isValidUrl('https://arxiv.org/abs/1234.5678?version=2')).toBe(true);
  });
});

// ──────────────────────────────────────────────
// extractDomain
// ──────────────────────────────────────────────
describe('extractDomain', () => {
  it('extracts hostname from https URL', () => {
    expect(window._submitHelpers.extractDomain('https://github.com/org/repo')).toBe('github.com');
  });

  it('strips www prefix', () => {
    expect(window._submitHelpers.extractDomain('https://www.github.com/org')).toBe('github.com');
  });

  it('returns empty string for invalid URL', () => {
    expect(window._submitHelpers.extractDomain('not-a-url')).toBe('');
  });

  it('returns empty string for empty input', () => {
    expect(window._submitHelpers.extractDomain('')).toBe('');
  });

  it('handles URL with port — hostname only, port stripped', () => {
    // URL.hostname does NOT include port; URL.host would. extractDomain uses hostname.
    expect(window._submitHelpers.extractDomain('http://localhost:3000/path')).toBe('localhost');
  });

  it('handles arxiv URL', () => {
    expect(window._submitHelpers.extractDomain('https://arxiv.org/abs/1234.5678')).toBe('arxiv.org');
  });
});

// ──────────────────────────────────────────────
// validateSubmission
// ──────────────────────────────────────────────
describe('validateSubmission', () => {
  const validData = {
    resource_type: 'package',
    resource_name: 'DoubleML',
    url: 'https://github.com/DoubleML/doubleml-for-py',
    description: 'Double machine learning library'
  };

  it('accepts valid complete submission', () => {
    const result = window._submitHelpers.validateSubmission(validData);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('rejects missing resource_type', () => {
    const { resource_type: _, ...data } = validData;
    const result = window._submitHelpers.validateSubmission(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Resource type'))).toBe(true);
  });

  it('rejects invalid resource_type', () => {
    const result = window._submitHelpers.validateSubmission({ ...validData, resource_type: 'widget' });
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Invalid resource type'))).toBe(true);
  });

  it('rejects missing resource_name', () => {
    const { resource_name: _, ...data } = validData;
    const result = window._submitHelpers.validateSubmission(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('name'))).toBe(true);
  });

  it('rejects resource_name shorter than 2 chars', () => {
    const result = window._submitHelpers.validateSubmission({ ...validData, resource_name: 'X' });
    expect(result.valid).toBe(false);
  });

  it('rejects missing URL', () => {
    const { url: _, ...data } = validData;
    const result = window._submitHelpers.validateSubmission(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('URL'))).toBe(true);
  });

  it('rejects invalid URL', () => {
    const result = window._submitHelpers.validateSubmission({ ...validData, url: 'not-a-url' });
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Invalid URL'))).toBe(true);
  });

  it('rejects name exceeding max length', () => {
    const result = window._submitHelpers.validateSubmission({
      ...validData,
      resource_name: 'X'.repeat(201)
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('long'))).toBe(true);
  });

  it('rejects description exceeding max length', () => {
    const result = window._submitHelpers.validateSubmission({
      ...validData,
      description: 'A'.repeat(1001)
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Description'))).toBe(true);
  });

  it('accepts all valid resource types', () => {
    const types = ['package', 'dataset', 'learning', 'paper', 'talk', 'book', 'community'];
    for (const resource_type of types) {
      const result = window._submitHelpers.validateSubmission({ ...validData, resource_type });
      expect(result.valid).toBe(true);
    }
  });

  it('collects multiple errors at once', () => {
    const result = window._submitHelpers.validateSubmission({});
    expect(result.errors.length).toBeGreaterThanOrEqual(2);
  });
});

// ────────────────────────────────────────────────
// mapToSchema
// ────────────────────────────────────────────────

const BASE_FORM = {
  resource_name: 'My Tool',
  description: 'A great tool',
  category: 'Causal Inference',
  url: 'https://example.com',
  email: null,
};

describe('mapToSchema', () => {
  beforeEach(() => loadWorker());
  afterEach(() => { delete window._submitHelpers; });

  it('package: has name, github_url when url is github', () => {
    const result = window._submitHelpers.mapToSchema(
      { ...BASE_FORM, url: 'https://github.com/owner/repo' },
      'package'
    );
    expect(result.name).toBe('My Tool');
    expect(result.github_url).toBe('https://github.com/owner/repo');
  });

  it('package: github_url is null for non-github url', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'package');
    expect(result.github_url).toBeNull();
  });

  it('dataset: has name field', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'dataset');
    expect(result.name).toBe('My Tool');
  });

  it('paper: uses title instead of name', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'paper');
    expect(result.title).toBe('My Tool');
    expect(result.name).toBeUndefined();
  });

  it('paper: has citations: 0', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'paper');
    expect(result.citations).toBe(0);
  });

  it('learning: has domain extracted from url', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'learning');
    expect(result.domain).toBe('example.com');
  });

  it('talk: has type Video', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'talk');
    expect(result.type).toBe('Video');
  });

  it('book: has isbn field', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'book');
    expect(result).toHaveProperty('isbn');
  });

  it('community: has location and dates fields', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'community');
    expect(result).toHaveProperty('location');
    expect(result).toHaveProperty('dates');
  });

  it('all types have _submitted timestamp', () => {
    for (const type of ['package', 'dataset', 'learning', 'paper', 'talk', 'book', 'community']) {
      const result = window._submitHelpers.mapToSchema(BASE_FORM, type);
      expect(result._submitted).toBeTruthy();
    }
  });

  it('trims whitespace from name', () => {
    const result = window._submitHelpers.mapToSchema(
      { ...BASE_FORM, resource_name: '  Padded Tool  ' },
      'package'
    );
    expect(result.name).toBe('Padded Tool');
  });

  it('default fallback includes name', () => {
    const result = window._submitHelpers.mapToSchema(BASE_FORM, 'unknown_type');
    expect(result.name).toBe('My Tool');
  });
});

// ────────────────────────────────────────────────
// getCategories
// ────────────────────────────────────────────────

describe('getCategories', () => {
  beforeEach(() => loadWorker());
  afterEach(() => { delete window._submitHelpers; });

  it('returns object with all resource types', () => {
    const cats = window._submitHelpers.getCategories();
    for (const type of ['package', 'dataset', 'learning', 'paper', 'talk', 'book', 'community']) {
      expect(cats).toHaveProperty(type);
    }
  });

  it('each type has non-empty array', () => {
    const cats = window._submitHelpers.getCategories();
    for (const [type, list] of Object.entries(cats)) {
      expect(Array.isArray(list)).toBe(true);
      expect(list.length).toBeGreaterThan(0);
    }
  });

  it('all category values are non-empty strings', () => {
    const cats = window._submitHelpers.getCategories();
    for (const list of Object.values(cats)) {
      for (const cat of list) {
        expect(typeof cat).toBe('string');
        expect(cat.length).toBeGreaterThan(0);
      }
    }
  });

  it('community includes Conferences', () => {
    const cats = window._submitHelpers.getCategories();
    expect(cats.community).toContain('Conferences');
  });
});
