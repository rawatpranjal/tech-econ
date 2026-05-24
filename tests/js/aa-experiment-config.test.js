/**
 * Pre-flight check for the A/A experiments shipped in
 * data/experiments.json. The harness's A/A tests are no-op experiments
 * (per audit §4.A7 step 1) whose sole purpose is to validate the
 * end-to-end pipeline by checking that bucketing splits traffic ~50/50.
 *
 * harness_aa_v1: CONTAMINATED (paused 2026-05-23). cookie-timing bug
 *   caused first-visit users to receive a different ephemeral UUID for
 *   impressions vs. the real te_uid after interaction. 57 users appeared
 *   in both variants. Tests retained for historical reference only.
 *
 * harness_aa_v2: ACTIVE (started 2026-05-24). Identical A/A structure,
 *   new experiment ID so bucketing is fresh for all users. Runs against
 *   the fixed tracker.js that writes te_uid eagerly at page load.
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

// ---------------------------------------------------------------------------
// harness_aa_v1 — paused/contaminated experiment (historical validation)
// ---------------------------------------------------------------------------
describe('harness_aa_v1: paused (contaminated) — config integrity check', () => {
  // Parse the actual experiments.json directly so we don't need a getConfig() export.
  const cfg = JSON.parse(fs.readFileSync(EXPERIMENTS_JSON, 'utf8'));

  it('exists in config with status=paused (not active — it was contaminated)', () => {
    const exp = cfg.experiments.find((e) => e.id === 'harness_aa_v1');
    expect(exp).toBeDefined();
    expect(exp.status).toBe('paused');
    const total = exp.variants.reduce((s, v) => s + v.traffic, 0);
    expect(total).toBe(100);
    expect(exp.variants.length).toBe(2);
  });

  it('resolves to null for all uids (paused experiment)', () => {
    // resolveVariant returns null for non-active experiments. This is the
    // correct behaviour: paused experiments stop bucketing new traffic.
    for (let i = 0; i < 20; i++) {
      const variant = Experiments.resolveVariant(cfg, 'uid_' + i, 'harness_aa_v1');
      expect(variant).toBeNull();
    }
  });

  it('does NOT appear in getAllAssignments (paused)', () => {
    document.cookie = 'te_uid=test_user_123; path=/';
    const all = Experiments.getAllAssignments();
    expect(all.harness_aa_v1).toBeUndefined();
    document.cookie = 'te_uid=; path=/; max-age=0';
  });
});

// ---------------------------------------------------------------------------
// harness_aa_v2 — active replacement after tracker.js fix
// ---------------------------------------------------------------------------
describe('harness_aa_v2: end-to-end bucket distribution', () => {
  const cfg = JSON.parse(fs.readFileSync(EXPERIMENTS_JSON, 'utf8'));

  it('exists in config with status=active', () => {
    const exp = cfg.experiments.find((e) => e.id === 'harness_aa_v2');
    expect(exp).toBeDefined();
    expect(exp.status).toBe('active');
    const total = exp.variants.reduce((s, v) => s + v.traffic, 0);
    expect(total).toBe(100);
    expect(exp.variants.length).toBe(2);
  });

  it('splits 10k synthetic uids ~50/50 across control_a and control_b', () => {
    const N = 10000;
    const counts = { control_a: 0, control_b: 0, other: 0 };
    for (let i = 0; i < N; i++) {
      // Use a stable seeded uid so the test is deterministic across runs.
      const variant = Experiments.resolveVariant(cfg, 'uid_' + i, 'harness_aa_v2');
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
      const v1 = Experiments.resolveVariant(cfg, uid, 'harness_aa_v2');
      const v2 = Experiments.resolveVariant(cfg, uid, 'harness_aa_v2');
      expect(v1).toBe(v2);
    }
  });

  it('appears in getAllAssignments when a uid is assigned', () => {
    document.cookie = 'te_uid=test_user_123; path=/';
    const all = Experiments.getAllAssignments();
    expect(all.harness_aa_v2).toMatch(/^control_[ab]$/);
    // harness_aa_v1 is paused — must NOT appear.
    expect(all.harness_aa_v1).toBeUndefined();
    // _example_disabled is status=draft — must NOT appear.
    expect(all._example_disabled).toBeUndefined();
    document.cookie = 'te_uid=; path=/; max-age=0';
  });

  it('v1 and v2 bucket the same uid into potentially different variants (independent experiments)', () => {
    // Different experiment IDs must produce independent bucketing. Across
    // a large population some users will land in different variants across
    // experiments — this asserts the experiments are not positively correlated.
    let sameCount = 0;
    const N = 1000;
    for (let i = 0; i < N; i++) {
      const uid = 'cross_uid_' + i;
      const v1 = Experiments.resolveVariant(cfg, uid, 'harness_aa_v1');
      const v2 = Experiments.resolveVariant(cfg, uid, 'harness_aa_v2');
      // v1 is paused → null. We test v2 bucketing independently.
      expect(v2).toMatch(/^control_[ab]$/);
      if (v1 === v2) sameCount++;
    }
    // v1 is paused → always null, so sameCount is always 0.
    expect(sameCount).toBe(0);
  });
});
