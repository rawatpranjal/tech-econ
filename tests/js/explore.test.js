/**
 * Tests for static/js/explore.js pure helpers.
 *
 * Exercises the window.Explore._* test surface exposed at the bottom of the
 * IIFE: slugify, truncate, isPopularItem, isNewItem, getDailyHeroSeed,
 * selectDailyHero, and getEngagementBadge.
 *
 * init() is NOT called — DOMContentLoaded never fires in jsdom after the
 * document is already 'complete', so there are no fetch or DOM side-effects.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/explore.js',
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

function loadScript() {
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

describe('explore.js pure helpers', () => {
  beforeEach(() => {
    loadScript();
  });

  afterEach(() => {
    vi.useRealTimers();
    delete window.Explore;
  });

  // -------------------------------------------------------------------------
  // _slugify
  // -------------------------------------------------------------------------
  describe('_slugify', () => {
    it('lowercases text', () => {
      expect(window.Explore._slugify('HelloWorld')).toBe('helloworld');
    });

    it('replaces spaces with hyphens', () => {
      expect(window.Explore._slugify('hello world')).toBe('hello-world');
    });

    it('replaces special characters with a single hyphen', () => {
      expect(window.Explore._slugify('foo & bar')).toBe('foo-bar');
    });

    it('strips leading and trailing hyphens', () => {
      expect(window.Explore._slugify('  hello  ')).toBe('hello');
    });

    it('collapses consecutive non-alnum runs to one hyphen', () => {
      expect(window.Explore._slugify('a--b__c')).toBe('a-b-c');
    });

    it('handles empty string', () => {
      expect(window.Explore._slugify('')).toBe('');
    });
  });

  // -------------------------------------------------------------------------
  // _truncate
  // -------------------------------------------------------------------------
  describe('_truncate', () => {
    it('returns empty string for null', () => {
      expect(window.Explore._truncate(null, 10)).toBe('');
    });

    it('returns empty string for undefined', () => {
      expect(window.Explore._truncate(undefined, 10)).toBe('');
    });

    it('returns string as-is when shorter than len', () => {
      expect(window.Explore._truncate('hello', 10)).toBe('hello');
    });

    it('returns string as-is when exactly len', () => {
      expect(window.Explore._truncate('hello', 5)).toBe('hello');
    });

    it('truncates and appends ellipsis when longer', () => {
      const result = window.Explore._truncate('hello world', 5);
      expect(result).toBe('hello...');
    });

    it('handles empty string', () => {
      expect(window.Explore._truncate('', 10)).toBe('');
    });
  });

  // -------------------------------------------------------------------------
  // _isPopularItem
  // -------------------------------------------------------------------------
  describe('_isPopularItem', () => {
    it('returns true when model_score > 0.7', () => {
      expect(window.Explore._isPopularItem({ model_score: 0.8 })).toBe(true);
    });

    it('returns true at model_score = 0.71', () => {
      expect(window.Explore._isPopularItem({ model_score: 0.71 })).toBe(true);
    });

    it('returns false when model_score equals 0.7 exactly', () => {
      expect(window.Explore._isPopularItem({ model_score: 0.7 })).toBe(false);
    });

    it('returns false when model_score is 0', () => {
      expect(window.Explore._isPopularItem({ model_score: 0 })).toBe(false);
    });

    it('returns false when model_score is absent', () => {
      expect(window.Explore._isPopularItem({})).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // _isNewItem
  // -------------------------------------------------------------------------
  describe('_isNewItem', () => {
    it('returns false when date_added is missing', () => {
      expect(window.Explore._isNewItem({})).toBe(false);
    });

    it('returns true for item added today', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      expect(window.Explore._isNewItem({ date_added: '2026-05-25' })).toBe(true);
    });

    it('returns true for item added 4 days ago', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      expect(window.Explore._isNewItem({ date_added: '2026-05-21' })).toBe(true);
    });

    it('returns false for item added 6 days ago', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      expect(window.Explore._isNewItem({ date_added: '2026-05-19' })).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // _getDailyHeroSeed
  // -------------------------------------------------------------------------
  describe('_getDailyHeroSeed', () => {
    it('returns a positive integer', () => {
      const seed = window.Explore._getDailyHeroSeed();
      expect(typeof seed).toBe('number');
      expect(Number.isInteger(seed)).toBe(true);
      expect(seed).toBeGreaterThan(0);
    });

    it('is deterministic within the same day', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T08:00:00Z'));
      const s1 = window.Explore._getDailyHeroSeed();
      vi.setSystemTime(new Date('2026-05-25T23:59:59Z'));
      const s2 = window.Explore._getDailyHeroSeed();
      expect(s1).toBe(s2);
    });

    it('produces a different seed on a different day', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      const s1 = window.Explore._getDailyHeroSeed();
      vi.setSystemTime(new Date('2026-05-26T12:00:00Z'));
      const s2 = window.Explore._getDailyHeroSeed();
      expect(s1).not.toBe(s2);
    });
  });

  // -------------------------------------------------------------------------
  // _selectDailyHero
  // -------------------------------------------------------------------------
  describe('_selectDailyHero', () => {
    it('returns null for empty array', () => {
      expect(window.Explore._selectDailyHero([], 'cluster-1')).toBeNull();
    });

    it('returns null for null items', () => {
      expect(window.Explore._selectDailyHero(null, 'cluster-1')).toBeNull();
    });

    it('returns one of the provided items', () => {
      const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
      const hero = window.Explore._selectDailyHero(items, 'cluster-1');
      expect(items).toContain(hero);
    });

    it('is deterministic for same inputs on the same day', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
      const h1 = window.Explore._selectDailyHero(items, 'cluster-test');
      const h2 = window.Explore._selectDailyHero(items, 'cluster-test');
      expect(h1).toBe(h2);
    });

    it('varies by carouselId (different clusters select different heroes)', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      const items = Array.from({ length: 20 }, (_, i) => ({ id: `item-${i}` }));
      const heroes = new Set(
        Array.from({ length: 20 }, (_, i) =>
          window.Explore._selectDailyHero(items, `cluster-${i}`)?.id,
        ),
      );
      expect(heroes.size).toBeGreaterThan(1);
    });
  });

  // -------------------------------------------------------------------------
  // _getEngagementBadge
  // -------------------------------------------------------------------------
  describe('_getEngagementBadge', () => {
    it('returns empty string when neither new nor popular', () => {
      expect(window.Explore._getEngagementBadge({ model_score: 0.1 })).toBe('');
    });

    it('returns Popular badge for high model_score', () => {
      const badge = window.Explore._getEngagementBadge({ model_score: 0.9 });
      expect(badge).toContain('badge-popular');
      expect(badge).toContain('Popular');
    });

    it('New badge takes priority over Popular when both qualify', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      const badge = window.Explore._getEngagementBadge({
        date_added: '2026-05-25',
        model_score: 0.9,
      });
      expect(badge).toContain('badge-new');
      expect(badge).not.toContain('badge-popular');
    });

    it('returns New badge for recently added item with low score', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      const badge = window.Explore._getEngagementBadge({
        date_added: '2026-05-24',
        model_score: 0.1,
      });
      expect(badge).toContain('badge-new');
    });

    it('returns empty string for old item with low score', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-05-25T12:00:00Z'));
      const badge = window.Explore._getEngagementBadge({
        date_added: '2026-01-01',
        model_score: 0.1,
      });
      expect(badge).toBe('');
    });
  });
});
