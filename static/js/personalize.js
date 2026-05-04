/**
 * personalize.js
 *
 * Ra4 + Re4 (audit doc, recsys-audit-2026-05-03.md): client-side
 * multiplicative re-rank of homepage cards based on the user's recent
 * reading history.
 *
 * Two complementary effects, applied in one pass:
 *   - **Ra4 boost**: for each history item, top-5 semantic neighbours in
 *     related-items.json get a rank-decayed positive bump. Closest
 *     neighbour gets multiplier 1+LAMBDA (1.2), 5th gets ~1+0.6*LAMBDA
 *     (1.12). Multiple history items reinforce via max(), not sum, so
 *     heavy readers don't get runaway boosts.
 *   - **Re4 dampen**: items the user has already clicked (the "source"
 *     items themselves) get pushed DOWN with multiplier 1-DAMPEN
 *     (0.8). Already-seen items are de-prioritised within the row so
 *     fresh content surfaces. Dampening **trumps** boosting -- if a
 *     card is both in the user's history AND a neighbour of another
 *     history item, dampening wins. The principle: "I've seen this"
 *     is a stronger signal than "this is similar to something I saw."
 *
 * Pipeline:
 *   1. Pull last MAX_HISTORY items from window.TechEconHistory.
 *   2. buildBoostMap(): id -> max(rankWeight) from neighbours.
 *      buildDampenSet(): set of source item ids (already-clicked).
 *   3. Each .package-card on the page maps to an item id via its
 *      lowercased data-name -> search-metadata.json lookup.
 *   4. reorderRow() computes per-card multiplier:
 *        if id in dampenSet:  multiplier = 1 - DAMPEN  (0.8)
 *        elif id in boostMap: multiplier = 1 + LAMBDA * boost  (1.0..1.2)
 *        else:                multiplier = 1.0  (untouched)
 *      Stable-sort by descending multiplier; ties keep original order.
 *
 * Why related-items.json instead of the raw embedding binary:
 *   The original Ra4 plan called for cosine over bge embeddings via
 *   search-cache.js:getEmbedding(id). That helper does not exist
 *   (search-cache.js only loads the whole 16 MB blob lazily after first
 *   search). Triggering a 16 MB download just to re-rank a homepage
 *   would be a poor trade. related-items.json is 1.4 MB, already
 *   fetched by because-you-viewed.js, so the marginal cost is one HTTP
 *   cache hit per page.
 *
 * LAMBDA = 0.2 and DAMPEN = 0.2 keep the final multiplier in [0.8, 1.2]
 * -- a 50% spread, enough to perturb ordering within a row but not
 * enough to override the global model_score. Bump cautiously and watch
 * the eval scoreboard.
 *
 * Silent failure on every error path: we never throw, never alert,
 * never block render. The DOM is left untouched on any unexpected state.
 */
(function () {
  'use strict';

  var ROW_SELECTOR = '.cards-row';
  var CARD_SELECTOR = '.package-card';
  var METADATA_URL = '/embeddings/search-metadata.json';
  var RELATED_URL = '/embeddings/related-items.json';
  var MIN_HISTORY = 3;
  var MAX_HISTORY = 5;
  var LAMBDA = 0.2;
  var DAMPEN = 0.2;

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ' returned ' + r.status);
      return r.json();
    });
  }

  /**
   * Look up the item id for a reading-history entry. Match by exact
   * name; if multiple items share the name, prefer one whose type
   * matches the history entry's type. Pure function -- exposed for
   * unit testing. Mirrors the shape used by because-you-viewed.js so
   * lookups stay consistent across the two surfaces.
   */
  function findItemId(items, historyEntry) {
    if (!items || !historyEntry || !historyEntry.name) return null;
    var name = historyEntry.name;
    var type = historyEntry.type;
    var exactNameTypeMatch = null;
    var exactNameMatch = null;
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      if (!it || it.name !== name) continue;
      if (type && type !== 'item' && it.type === type) {
        exactNameTypeMatch = it;
        break;
      }
      if (!exactNameMatch) exactNameMatch = it;
    }
    var match = exactNameTypeMatch || exactNameMatch;
    return match ? match.id : null;
  }

  /**
   * Build a boost map id -> [0..1] from history. Rank-decayed weight,
   * max() across history items so a card that's a neighbour of many
   * history items doesn't get exponential boost. Pure function.
   */
  function buildBoostMap(metadata, related, history) {
    var boost = Object.create(null);
    for (var h = 0; h < history.length; h++) {
      var sourceId = findItemId(metadata, history[h]);
      if (!sourceId) continue;
      var neighbours = related[sourceId] || [];
      for (var n = 0; n < neighbours.length; n++) {
        var nb = neighbours[n];
        if (!nb || !nb.id) continue;
        var rankWeight = 1 - 0.1 * n;
        if (rankWeight < 0) rankWeight = 0;
        if (!boost[nb.id] || boost[nb.id] < rankWeight) {
          boost[nb.id] = rankWeight;
        }
      }
    }
    return boost;
  }

  /**
   * Build the dampen set: ids of items the user has already clicked.
   * Re4 — "I've seen this" signal. Dampened cards are pushed to the
   * bottom of their row, regardless of any boost they might also have
   * accrued via being a neighbour of another history item. Pure function.
   */
  function buildDampenSet(metadata, history) {
    var set = Object.create(null);
    if (!history) return set;
    for (var h = 0; h < history.length; h++) {
      var sourceId = findItemId(metadata, history[h]);
      if (sourceId) set[sourceId] = true;
    }
    return set;
  }

  /**
   * Build lowercased-name -> id map from search-metadata.json's items.
   * Homepage cards expose data-name in lowercase, which is how we bridge
   * card DOM to embedding ids. First-write-wins on collisions; if two
   * items share a name, we'd need a richer lookup (data-section-category
   * disambiguator). Not needed today; revisit if cards are mis-boosted.
   */
  function buildNameToIdMap(metadata) {
    var lookup = Object.create(null);
    for (var i = 0; i < metadata.length; i++) {
      var it = metadata[i];
      if (it && it.name && it.id) {
        var key = String(it.name).toLowerCase();
        if (!lookup[key]) lookup[key] = it.id;
      }
    }
    return lookup;
  }

  /**
   * Reorder one .cards-row in place. Returns true if any card moved.
   * Stable on ties (preserves original DOM order).
   *
   * dampen is optional (defaults to empty); when present, ids in the
   * set get hard-set to multiplier 1-DAMPEN, overriding any boost.
   * Existing 3-arg callers continue to work as pre-Re4.
   */
  function reorderRow(row, nameToId, boost, dampen) {
    var cards = Array.prototype.slice.call(row.querySelectorAll(CARD_SELECTOR));
    if (cards.length < 2) return false;

    var dampenSet = dampen || EMPTY_DAMPEN;
    var anyChange = false;
    var scored = cards.map(function (card, idx) {
      var name = (card.getAttribute('data-name') || '').toLowerCase();
      var id = nameToId[name];
      var multiplier;
      if (id && dampenSet[id]) {
        multiplier = 1 - DAMPEN;
        anyChange = true;
      } else {
        var boostScore = id && boost[id] ? boost[id] : 0;
        multiplier = 1 + LAMBDA * boostScore;
        if (boostScore > 0) anyChange = true;
      }
      return { card: card, idx: idx, multiplier: multiplier };
    });

    if (!anyChange) return false;

    scored.sort(function (a, b) {
      if (b.multiplier !== a.multiplier) return b.multiplier - a.multiplier;
      return a.idx - b.idx;
    });

    var fragment = document.createDocumentFragment();
    scored.forEach(function (s) { fragment.appendChild(s.card); });
    row.appendChild(fragment);
    return true;
  }

  // Reused empty-dampen sentinel so reorderRow can default cheaply.
  var EMPTY_DAMPEN = Object.create(null);

  function init() {
    var rows = document.querySelectorAll(ROW_SELECTOR);
    if (rows.length === 0) return Promise.resolve();

    var history = window.TechEconHistory && typeof window.TechEconHistory.getRecent === 'function'
      ? window.TechEconHistory.getRecent(MAX_HISTORY)
      : [];
    if (!history || history.length < MIN_HISTORY) return Promise.resolve();

    return Promise.all([fetchJson(METADATA_URL), fetchJson(RELATED_URL)])
      .then(function (results) {
        var metadata = (results[0] && results[0].items) || [];
        var related = (results[1] && results[1].items) || {};
        var boost = buildBoostMap(metadata, related, history);
        var dampen = buildDampenSet(metadata, history);

        // Skip work if neither effect would do anything. We could still
        // proceed (reorderRow is a no-op when nothing matches) but bailing
        // here saves a name-lookup-map build on the common no-history path.
        var hasBoost = false;
        for (var k in boost) { hasBoost = true; break; }
        var hasDampen = false;
        for (var d in dampen) { hasDampen = true; break; }
        if (!hasBoost && !hasDampen) return;

        var nameToId = buildNameToIdMap(metadata);
        var rowsTouched = 0;
        rows.forEach(function (row) {
          if (reorderRow(row, nameToId, boost, dampen)) rowsTouched++;
        });
        if (typeof console !== 'undefined' && console.debug) {
          console.debug('[personalize] reranked', rowsTouched, 'rows');
        }
      })
      .catch(function (err) {
        if (typeof console !== 'undefined' && console.warn) {
          console.warn('[personalize]', err);
        }
      });
  }

  /**
   * Run after the page settles. requestIdleCallback yields to the
   * critical path; fall back to setTimeout for older Safari (<16.4).
   */
  function schedule() {
    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(init, { timeout: 2000 });
    } else {
      setTimeout(init, 200);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedule);
  } else {
    schedule();
  }

  window.TechEconPersonalize = {
    init: init,
    findItemId: findItemId,
    buildBoostMap: buildBoostMap,
    buildDampenSet: buildDampenSet,
    buildNameToIdMap: buildNameToIdMap,
    reorderRow: reorderRow,
    LAMBDA: LAMBDA,
    DAMPEN: DAMPEN
  };
})();
