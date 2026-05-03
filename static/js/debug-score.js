/**
 * debug-score.js
 *
 * `?debug=1` URL flag overlays each card in the DOM with its
 * `model_score` from static/embeddings/search-index.json. Pure
 * developer affordance — accelerates every future ranking change by
 * making the engagement signal visible alongside the cards we ship.
 *
 * Inputs:
 *   - URL search param `debug` set to "1" (or "true" — both work).
 *   - DOM cards that expose their item name via `[data-name]` (the
 *     standard pattern in layouts/index.html and the section list
 *     templates: `data-name="{{ .name | lower }}"`).
 *   - Lazy fetches `/embeddings/search-index.json` only when the flag
 *     is set, so the overlay has zero cost for normal users.
 *
 * Side effects:
 *   - Inserts a `<span class="debug-score-badge">` adjacent to each
 *     matched card's primary link.
 *   - Idempotent — running init() twice will not duplicate badges.
 *   - Silent on every failure path (no flag, no cards, fetch error,
 *     name not found) so it never harms a real user who happens to
 *     hit the flag.
 *
 * Reproducibility:
 *   - Pure DOM transformation; no randomness.
 */

(function () {
  'use strict';

  var INDEX_URL = '/embeddings/search-index.json';
  var BADGE_CLASS = 'debug-score-badge';

  /**
   * Read the URL flag. Returns true when `debug` is set to anything
   * truthy ('1', 'true', 'yes'). Pure function — exposed for testing.
   */
  function isDebugEnabled(search) {
    if (typeof search !== 'string') return false;
    var params = new URLSearchParams(search);
    var v = (params.get('debug') || '').toLowerCase();
    return v === '1' || v === 'true' || v === 'yes';
  }

  /**
   * Build a `nameLower → model_score` lookup from the `documents`
   * array of a parsed search-index.json. Tolerates missing fields
   * silently. Pure function — exposed for testing.
   */
  function buildScoreLookup(documents) {
    var out = Object.create(null);
    if (!Array.isArray(documents)) return out;
    for (var i = 0; i < documents.length; i++) {
      var d = documents[i];
      if (!d || typeof d.name !== 'string') continue;
      if (typeof d.model_score !== 'number') continue;
      out[d.name.toLowerCase()] = d.model_score;
    }
    return out;
  }

  /**
   * Format a score for display. Three significant figures, e.g.
   * 0.42  / 0.000123 / 1.00. Pure — exposed for testing.
   */
  function formatScore(score) {
    if (typeof score !== 'number' || isNaN(score)) return '?';
    if (score === 0) return '0';
    if (score < 0.001) return score.toExponential(1);
    if (score >= 1) return score.toFixed(2);
    return score.toFixed(3);
  }

  /**
   * Insert a badge next to a card. Idempotent — checks for an
   * existing `.debug-score-badge` child first. Pure DOM transform —
   * exposed for testing.
   */
  function injectBadge(card, score) {
    if (!card || card.querySelector('.' + BADGE_CLASS)) return false;
    var badge = document.createElement('span');
    badge.className = BADGE_CLASS;
    badge.textContent = formatScore(score);
    badge.title = 'model_score';
    // Insert near the primary heading so it's visible at a glance.
    var anchor = card.querySelector('h1, h2, h3, h4, .card-header, .card-title')
      || card.firstElementChild;
    if (anchor) anchor.appendChild(badge);
    else card.appendChild(badge);
    return true;
  }

  /**
   * Walk all `[data-name]` cards in the document, look up each one's
   * model_score, and inject a badge. Returns the number of badges
   * added (for testing). Pure DOM transform.
   */
  function applyOverlay(rootEl, lookup) {
    if (!rootEl || !rootEl.querySelectorAll) return 0;
    var cards = rootEl.querySelectorAll('[data-name]');
    var added = 0;
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var name = (card.getAttribute('data-name') || '').toLowerCase();
      if (!name || !(name in lookup)) continue;
      if (injectBadge(card, lookup[name])) added++;
    }
    return added;
  }

  function fetchIndex() {
    return fetch(INDEX_URL).then(function (r) {
      if (!r.ok) throw new Error(INDEX_URL + ' returned ' + r.status);
      return r.json();
    });
  }

  function init(opts) {
    if (typeof window === 'undefined' || typeof document === 'undefined') {
      return Promise.resolve();
    }
    opts = opts || {};
    var search = (typeof opts.search === 'string')
      ? opts.search
      : window.location.search;
    if (!isDebugEnabled(search)) return Promise.resolve();

    return fetchIndex()
      .then(function (data) {
        var lookup = buildScoreLookup((data && data.documents) || []);
        applyOverlay(document.body, lookup);
      })
      .catch(function (err) {
        if (typeof console !== 'undefined' && console.warn) {
          console.warn('[debug-score]', err);
        }
      });
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  }

  // Public API for tests + manual triggering.
  if (typeof window !== 'undefined') {
    window.DebugScore = {
      init: init,
      isDebugEnabled: isDebugEnabled,
      buildScoreLookup: buildScoreLookup,
      formatScore: formatScore,
      injectBadge: injectBadge,
      applyOverlay: applyOverlay,
    };
  }
})();
