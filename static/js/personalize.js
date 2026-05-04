/**
 * personalize.js
 *
 * Ra4 (audit doc, recsys-audit-2026-05-03.md): client-side multiplicative
 * re-rank of homepage cards based on the user's recent reading history.
 *
 * Mechanism:
 *   1. Pull last MAX_HISTORY items from window.TechEconHistory.
 *   2. For each, look up its top-5 semantic neighbours in related-items.json.
 *      Build a boost map id -> max(rankWeight). rankWeight = 1.0 for the
 *      closest neighbour, decaying 0.1 per rank to 0.6 for the 5th.
 *      Multiple history items reinforce via max(), not sum, so heavy
 *      readers don't get runaway boosts.
 *   3. Each .package-card on the homepage maps to an item id via its
 *      lowercased data-name -> search-metadata.json lookup.
 *   4. Stable-sort cards within each .cards-row by (1 + LAMBDA * boost).
 *      Cards with no boost keep their original order.
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
 * LAMBDA at 0.2 keeps the multiplier in [1.0, 1.2] -- enough to surface
 * relevant cards within a row but not enough to override the global
 * model_score ordering. Bump cautiously.
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
   */
  function reorderRow(row, nameToId, boost) {
    var cards = Array.prototype.slice.call(row.querySelectorAll(CARD_SELECTOR));
    if (cards.length < 2) return false;

    var anyBoost = false;
    var scored = cards.map(function (card, idx) {
      var name = (card.getAttribute('data-name') || '').toLowerCase();
      var id = nameToId[name];
      var boostScore = id && boost[id] ? boost[id] : 0;
      if (boostScore > 0) anyBoost = true;
      return {
        card: card,
        idx: idx,
        multiplier: 1 + LAMBDA * boostScore
      };
    });

    if (!anyBoost) return false;

    scored.sort(function (a, b) {
      if (b.multiplier !== a.multiplier) return b.multiplier - a.multiplier;
      return a.idx - b.idx;
    });

    var fragment = document.createDocumentFragment();
    scored.forEach(function (s) { fragment.appendChild(s.card); });
    row.appendChild(fragment);
    return true;
  }

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

        var hasBoost = false;
        for (var k in boost) { hasBoost = true; break; }
        if (!hasBoost) return;

        var nameToId = buildNameToIdMap(metadata);
        var rowsTouched = 0;
        rows.forEach(function (row) {
          if (reorderRow(row, nameToId, boost)) rowsTouched++;
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
    buildNameToIdMap: buildNameToIdMap,
    reorderRow: reorderRow,
    LAMBDA: LAMBDA
  };
})();
