/**
 * Pre-flight check for the active A/A experiment shipped in
 * data/experiments.json. The harness's first real experiment is a
 * no-op A/A test (per audit §4.A7 step 1) whose sole purpose is to
 * validate the end-to-end pipeline by checking that bucketing splits
 * traffic ~50/50.
 *
 * This test runs against the *actual* data/experiments.json (not a
 * synthetic config) and a large pool of synthetic uids, asserting
 * the deterministic bucket assignments come out close to the
 * declared traffic split. If they don't, either the config is wrong
 * or the hash distribution is non-uniform — both worth catching
 * before letting it loose on production traffic.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const MOD_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../static/js/experiments.js'
);
const EXPERIMENTS_JSON = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../data/experiments.json'
);

let Experiments;
let configEl;

beforeEach(() => {
  delete require.cache[MOD_PATH];
  Experiments = require(MOD_PATH);
  // Inline the actual experiments.json into the DOM so getVariant() reads it.
  configEl = document.createElement('script');
  configEl.id = 'experiments-config';
  configEl.type = 'application/json';
  configEl.textContent = fs.readFileSync(EXPERIMENTS_JSON, 'utf8');
  document.body.appendChild(configEl);
});

afterEach(() => {
  if (configEl.parentNode) configEl.parentNode.removeChild(configEl);
});

describe('harness_aa_v1: end-to-end bucket distribution', () => {
  // Parse the actual experiments.json directly so we don't need a getConfig() export.
  const cfg = JSON.parse(fs.readFileSync(EXPERIMENTS_JSON, 'utf8'));

  it('splits 10k synthetic uids ~50/50 across control_a and control_b', () => {
    const N = 10000;
    const counts = { control_a: 0, control_b: 0, other: 0 };
    for (let i = 0; i < N; i++) {
      // Use a stable seeded uid so the test is deterministic across runs.
      const variant = Experiments.resolveVariant(cfg, 'uid_' + i, 'harness_aa_v1');
      if (variant === 'control_a') counts.control_a++;
      else if (variant === 'control_b') counts.control_b++;
      else counts.other++;
    }
    expect(counts.other).toBe(0);  // every uid maps to one of the two
    const pctA = counts.control_a / N;
    // ±2 percentage points slack for hash-distribution noise. Empirically
    // the existing fnv1a test already confirms uniformity within tighter
    // bounds; this is a guardrail, not a precision test.
    expect(pctA).toBeGreaterThan(0.47);
    expect(pctA).toBeLessThan(0.53);
  });

  it('is deterministic — same uid always lands in the same variant', () => {
    for (let i = 0; i < 50; i++) {
      const uid = 'stable_uid_' + i;
      const v1 = Experiments.resolveVariant(cfg, uid, 'harness_aa_v1');
      const v2 = Experiments.resolveVariant(cfg, uid, 'harness_aa_v1');
      expect(v1).toBe(v2);
    }
  });

  it('appears in getAllAssignments when a uid is assigned', () => {
    document.cookie = 'te_uid=test_user_123; path=/';
    const all = Experiments.getAllAssignments();
    expect(all.harness_aa_v1).toMatch(/^control_[ab]$/);
    // _example_disabled is status=draft, so it should NOT appear.
    expect(all._example_disabled).toBeUndefined();
    document.cookie = 'te_uid=; path=/; max-age=0';
  });

  it('config has exactly two variants summing to 100', () => {
    const exp = cfg.experiments.find((e) => e.id === 'harness_aa_v1');
    expect(exp).toBeDefined();
    expect(exp.status).toBe('active');
    const total = exp.variants.reduce((s, v) => s + v.traffic, 0);
    expect(total).toBe(100);
    expect(exp.variants.length).toBe(2);
  });
});
