/**
 * Tests for static/js/homepage-mmr-experiment.js (Re1 MMR variant toggle).
 *
 * Uses the IIFE loader pattern from debug-score.test.js.
 * Exposes window.HomepageMMR for testing.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SCRIPT_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/homepage-mmr-experiment.js'
);
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

function buildDOM() {
  document.body.innerHTML = `
    <div class="mmr-row-wrap" data-row-id="talks-worth-watching">
      <div data-mmr-variant="control"><div class="home-row">Control Talks</div></div>
      <div data-mmr-variant="treatment" hidden><div class="home-row">Treatment Talks</div></div>
    </div>
    <div class="mmr-row-wrap" data-row-id="top-packages">
      <div data-mmr-variant="control"><div class="home-row">Control Packages</div></div>
      <div data-mmr-variant="treatment" hidden><div class="home-row">Treatment Packages</div></div>
    </div>
  `;
}

function loadScript() {
  // eslint-disable-next-line no-new-func
  new Function(SCRIPT_SOURCE).call(window);
}

let HomepageMMR;

beforeEach(() => {
  delete window.HomepageMMR;
  delete window.Experiments;
  buildDOM();
  loadScript();
  HomepageMMR = window.HomepageMMR;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// -----------------------------------------------------------------
// Module surface
// -----------------------------------------------------------------
describe('HomepageMMR exports', () => {
  it('exposes the public test API', () => {
    expect(HomepageMMR).toBeDefined();
    expect(typeof HomepageMMR.applyVariant).toBe('function');
    expect(typeof HomepageMMR.init).toBe('function');
    expect(HomepageMMR.EXP_ID).toBe('exp_re1_mmr_v1');
  });
});

// -----------------------------------------------------------------
// applyVariant — control
// -----------------------------------------------------------------
describe('applyVariant("control")', () => {
  it('keeps control visible and treatment hidden', () => {
    HomepageMMR.applyVariant('control');
    const wraps = document.querySelectorAll('.mmr-row-wrap');
    wraps.forEach(wrap => {
      const control   = wrap.querySelector('[data-mmr-variant="control"]');
      const treatment = wrap.querySelector('[data-mmr-variant="treatment"]');
      expect(control.hidden).toBe(false);
      expect(treatment.hidden).toBe(true);
    });
  });
});

// -----------------------------------------------------------------
// applyVariant — treatment
// -----------------------------------------------------------------
describe('applyVariant("treatment")', () => {
  it('hides control and shows treatment', () => {
    HomepageMMR.applyVariant('treatment');
    const wraps = document.querySelectorAll('.mmr-row-wrap');
    wraps.forEach(wrap => {
      const control   = wrap.querySelector('[data-mmr-variant="control"]');
      const treatment = wrap.querySelector('[data-mmr-variant="treatment"]');
      expect(control.hidden).toBe(true);
      expect(treatment.hidden).toBe(false);
    });
  });

  it('applies to ALL row wraps on the page', () => {
    HomepageMMR.applyVariant('treatment');
    expect(document.querySelectorAll('[data-mmr-variant="control"][hidden]').length).toBe(2);
    expect(document.querySelectorAll('[data-mmr-variant="treatment"]:not([hidden])').length).toBe(2);
  });
});

// -----------------------------------------------------------------
// applyVariant — null / draft (no-op)
// -----------------------------------------------------------------
describe('applyVariant(null)', () => {
  it('does not touch DOM when variant is null', () => {
    // treatment should remain hidden (default HTML state)
    HomepageMMR.applyVariant(null);
    const treatment = document.querySelectorAll('[data-mmr-variant="treatment"]');
    treatment.forEach(el => expect(el.hidden).toBe(true));
  });

  it('does not throw for undefined variant', () => {
    expect(() => HomepageMMR.applyVariant(undefined)).not.toThrow();
  });
});

// -----------------------------------------------------------------
// init — reads from window.Experiments
// -----------------------------------------------------------------
describe('init()', () => {
  it('applies treatment when Experiments returns "treatment"', () => {
    window.Experiments = { getVariant: (id) => id === 'exp_re1_mmr_v1' ? 'treatment' : null };
    HomepageMMR.init();
    const control = document.querySelectorAll('[data-mmr-variant="control"]');
    control.forEach(el => expect(el.hidden).toBe(true));
  });

  it('is a no-op when Experiments returns null (draft experiment)', () => {
    window.Experiments = { getVariant: () => null };
    HomepageMMR.init();
    // Default state: control visible, treatment hidden
    const treatment = document.querySelectorAll('[data-mmr-variant="treatment"]');
    treatment.forEach(el => expect(el.hidden).toBe(true));
  });

  it('does not throw when window.Experiments is undefined', () => {
    delete window.Experiments;
    expect(() => HomepageMMR.init()).not.toThrow();
  });

  it('does not throw when Experiments.getVariant throws', () => {
    window.Experiments = { getVariant: () => { throw new Error('boom'); } };
    expect(() => HomepageMMR.init()).not.toThrow();
    // DOM unchanged — still default state
    const treatment = document.querySelectorAll('[data-mmr-variant="treatment"]');
    treatment.forEach(el => expect(el.hidden).toBe(true));
  });
});

// -----------------------------------------------------------------
// Edge cases
// -----------------------------------------------------------------
describe('applyVariant — edge cases', () => {
  it('skips wraps missing variant children without crashing', () => {
    document.body.innerHTML = `
      <div class="mmr-row-wrap" data-row-id="bad">
        <!-- no children with data-mmr-variant -->
      </div>
    `;
    expect(() => HomepageMMR.applyVariant('treatment')).not.toThrow();
  });

  it('handles a page with no .mmr-row-wrap elements', () => {
    document.body.innerHTML = '<div>No rows</div>';
    expect(() => HomepageMMR.applyVariant('treatment')).not.toThrow();
  });
});
