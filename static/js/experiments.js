/**
 * A/B testing harness — client-side bucketing (Phase 7 scaffold)
 *
 * Inputs:
 *   - <script id="experiments-config" type="application/json">…</script>
 *     inlined in layouts/_default/baseof.html. Schema:
 *       {
 *         "experiments": [
 *           {
 *             "id": "homepage_row_mmr_vs_baseline",
 *             "status": "active",                // "active" | "paused" | "draft"
 *             "variants": [
 *               { "id": "control",   "traffic": 50 },
 *               { "id": "treatment", "traffic": 50 }
 *             ]
 *           }, ...
 *         ]
 *       }
 *   - te_uid cookie (set by tracker.js). Falls back to a per-tab
 *     ephemeral id if the cookie is absent so first-visit users still
 *     see a stable variant within the page.
 *
 * Outputs:
 *   - window.Experiments.getVariant(experimentId) -> "<variant_id>" | null
 *   - window.Experiments.getAllAssignments() -> {expId: variantId, ...}
 *
 * Side effects:
 *   - None at module load. Reads cookie + inline JSON; never writes.
 *   - Logging is left to tracker.js (which appends `experiment_id` +
 *     `variant_id` fields to every event in a separate, server-side PR).
 *
 * Reproducibility:
 *   - Bucketing is deterministic given (te_uid, experiment_id) — the
 *     same user always lands in the same variant of the same
 *     experiment, even across sessions. Different experiments'
 *     bucketing is independent (the experiment_id is mixed into the
 *     hash) so a user isn't permanently in "treatment" across all
 *     concurrent experiments.
 *
 * Architecture rules enforced:
 *   - A1: Inputs/Outputs/Side effects/Reproducibility documented
 *   - A2: typed surface — getVariant returns string | null, never undefined
 *   - C8: missing config / inactive experiments / unknown ids tolerated;
 *     return null rather than crashing
 *   - E14: malformed traffic splits (don't sum to 100, etc.) raise to
 *     console.error so the bug is visible during dev, but the function
 *     still returns null rather than throwing — the goal is "experiment
 *     misconfiguration must not break the page"
 */
(function (global) {
  'use strict';

  var CONFIG_ELEMENT_ID = 'experiments-config';
  var COOKIE_NAME = 'te_uid';
  var ephemeralUid = null; // populated lazily if no cookie

  // -----------------------------------------------------------------
  // FNV-1a 32-bit hash. Cheap, fast, and good enough for bucketing —
  // we don't need cryptographic strength, just a uniform spread.
  // Pure function — exposed for tests.
  // -----------------------------------------------------------------
  function fnv1a(str) {
    var hash = 2166136261; // 32-bit FNV offset basis
    for (var i = 0; i < str.length; i++) {
      hash ^= str.charCodeAt(i);
      hash = (hash + ((hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24))) >>> 0;
    }
    return hash >>> 0;
  }

  function bucketOf(uid, experimentId) {
    return fnv1a(uid + '|' + experimentId) % 100;
  }

  // -----------------------------------------------------------------
  // Cookie reader. Tracker.js owns writes; we only read.
  // -----------------------------------------------------------------
  function getCookie(name) {
    if (typeof document === 'undefined' || !document.cookie) return '';
    var pairs = document.cookie.split(';');
    for (var i = 0; i < pairs.length; i++) {
      var p = pairs[i].trim();
      if (p.indexOf(name + '=') === 0) return decodeURIComponent(p.substring(name.length + 1));
    }
    return '';
  }

  function getOrMintUid() {
    var uid = getCookie(COOKIE_NAME);
    if (uid) return uid;
    if (ephemeralUid) return ephemeralUid;
    // First-visit, no cookie yet — mint a per-tab id. Crypto if
    // available, fallback to Math.random.
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
      var bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      ephemeralUid = Array.from(bytes, function (b) {
        return b.toString(16).padStart(2, '0');
      }).join('');
    } else {
      ephemeralUid = 'eph-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    }
    return ephemeralUid;
  }

  // -----------------------------------------------------------------
  // Config loading.
  // -----------------------------------------------------------------
  function loadConfig() {
    if (typeof document === 'undefined') return null;
    var el = document.getElementById(CONFIG_ELEMENT_ID);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || '{}');
    } catch (e) {
      if (typeof console !== 'undefined') {
        console.error('[experiments] failed to parse config:', e);
      }
      return null;
    }
  }

  function findExperiment(config, experimentId) {
    if (!config || !Array.isArray(config.experiments)) return null;
    for (var i = 0; i < config.experiments.length; i++) {
      var exp = config.experiments[i];
      if (exp && exp.id === experimentId) return exp;
    }
    return null;
  }

  // -----------------------------------------------------------------
  // Variant resolution. Pure function — given config + uid +
  // experimentId, returns the variant id or null.
  // -----------------------------------------------------------------
  function resolveVariant(config, uid, experimentId) {
    var exp = findExperiment(config, experimentId);
    if (!exp) return null;
    if (exp.status && exp.status !== 'active') return null;
    if (!Array.isArray(exp.variants) || exp.variants.length === 0) return null;

    var totalTraffic = 0;
    for (var i = 0; i < exp.variants.length; i++) {
      var v = exp.variants[i];
      if (!v || typeof v.traffic !== 'number' || v.traffic < 0) {
        if (typeof console !== 'undefined') {
          console.error('[experiments] invalid variant in', experimentId, ':', v);
        }
        return null;
      }
      totalTraffic += v.traffic;
    }
    if (totalTraffic !== 100) {
      if (typeof console !== 'undefined') {
        console.error(
          '[experiments] traffic for ' + experimentId + ' sums to ' + totalTraffic +
          ', expected 100. Returning null.'
        );
      }
      return null;
    }

    var bucket = bucketOf(uid, experimentId); // 0..99
    var cumulative = 0;
    for (var j = 0; j < exp.variants.length; j++) {
      var variant = exp.variants[j];
      cumulative += variant.traffic;
      if (bucket < cumulative) return variant.id;
    }
    // Defensive — shouldn't reach here if total is exactly 100
    return exp.variants[exp.variants.length - 1].id;
  }

  // -----------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------
  function getVariant(experimentId) {
    if (!experimentId) return null;
    var config = loadConfig();
    var uid = getOrMintUid();
    return resolveVariant(config, uid, experimentId);
  }

  function getAllAssignments() {
    var config = loadConfig();
    if (!config || !Array.isArray(config.experiments)) return {};
    var uid = getOrMintUid();
    var assignments = {};
    for (var i = 0; i < config.experiments.length; i++) {
      var exp = config.experiments[i];
      if (!exp || !exp.id) continue;
      var v = resolveVariant(config, uid, exp.id);
      if (v) assignments[exp.id] = v;
    }
    return assignments;
  }

  // -----------------------------------------------------------------
  // Module export — globals + AMD/CJS for tests
  // -----------------------------------------------------------------
  var Experiments = {
    getVariant: getVariant,
    getAllAssignments: getAllAssignments,
    // Internals exposed for tests + manual tweaking
    fnv1a: fnv1a,
    bucketOf: bucketOf,
    resolveVariant: resolveVariant,
    findExperiment: findExperiment,
  };

  if (typeof define === 'function' && define.amd) {
    define(function () { return Experiments; });
  } else if (typeof module === 'object' && module.exports) {
    module.exports = Experiments;
  } else {
    global.Experiments = Experiments;
  }
})(typeof window !== 'undefined' ? window : typeof self !== 'undefined' ? self : this);
