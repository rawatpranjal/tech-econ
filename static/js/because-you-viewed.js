/**
 * because-you-viewed.js
 *
 * Renders a "Because you viewed [last item]" row on the homepage by
 * combining two existing data sources that were collected but unused
 * together:
 *   - localStorage reading history (via window.TechEconHistory)
 *   - static/embeddings/related-items.json (top-5 semantic neighbours per item)
 *   - static/embeddings/search-metadata.json (id <-> name <-> url lookup)
 *
 * Inputs:
 *   - DOM element with id="because-you-viewed-section" (placeholder in
 *     layouts/index.html). If absent, the script is a no-op.
 *   - window.TechEconHistory (from reading-history.js, loaded earlier).
 *   - Lazy fetches /embeddings/{search-metadata,related-items}.json on
 *     demand (only when there is at least one history item).
 *
 * Side effects:
 *   - Mutates innerHTML of the placeholder + flips display from none to
 *     block once cards are ready. Silently leaves the placeholder hidden
 *     on any failure (no history, no match, network error, etc.).
 *
 * Reproducibility:
 *   - Pure DOM transformation; no randomness; cards always come from the
 *     fixed top-5 neighbours of the user's most recent click.
 */

(function () {
  'use strict';

  var SECTION_ID = 'because-you-viewed-section';
  var METADATA_URL = '/embeddings/search-metadata.json';
  var RELATED_URL = '/embeddings/related-items.json';
  var MAX_CARDS = 5;
  var DESC_MAX_CHARS = 120;

  /**
   * Find an item in the metadata array that matches the user's history
   * entry. The history records (name, type) but no id. We match by exact
   * name first, narrowing by type when ambiguous.
   *
   * Pure function — exposed for unit testing.
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
   * Resolve the neighbour ids returned by related-items.json into full
   * item objects (with name, url, type, etc.) by indexing search-metadata.
   * Excludes the source itself if it accidentally appears.
   *
   * Pure function — exposed for unit testing.
   */
  function resolveNeighbours(metadataItems, neighbours, sourceId) {
    var lookup = Object.create(null);
    for (var i = 0; i < metadataItems.length; i++) {
      var it = metadataItems[i];
      if (it && it.id) lookup[it.id] = it;
    }
    var resolved = [];
    for (var j = 0; j < neighbours.length; j++) {
      var n = neighbours[j];
      if (!n || !n.id || n.id === sourceId) continue;
      var item = lookup[n.id];
      if (item) resolved.push(item);
      if (resolved.length >= MAX_CARDS) break;
    }
    return resolved;
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  /**
   * Render the row. Pure DOM transform — exposed for unit testing.
   * Caller is responsible for showing the container.
   */
  function renderRow(container, anchor, items) {
    var anchorName = escapeHtml(anchor && anchor.name);
    var cards = items.map(function (item) {
      var url = escapeHtml(item.url || '#');
      var name = escapeHtml(item.name || '');
      var type = escapeHtml(item.type || '');
      var category = escapeHtml(item.category || '');
      var desc = escapeHtml(String(item.description || '').slice(0, DESC_MAX_CHARS));
      return (
        '<a href="' + url + '" target="_blank" rel="noopener" class="byv-card">' +
          (type ? '<span class="byv-type">' + type + '</span>' : '') +
          '<span class="byv-name">' + name + '</span>' +
          (category ? '<span class="byv-category">' + category + '</span>' : '') +
          (desc ? '<span class="byv-desc">' + desc + '</span>' : '') +
        '</a>'
      );
    }).join('');

    container.innerHTML =
      '<div class="byv-header">' +
        '<h3>Because you viewed <em>' + anchorName + '</em></h3>' +
      '</div>' +
      '<div class="byv-cards">' + cards + '</div>';
  }

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ' returned ' + r.status);
      return r.json();
    });
  }

  function init() {
    var container = document.getElementById(SECTION_ID);
    if (!container) return Promise.resolve();

    var history =
      window.TechEconHistory && typeof window.TechEconHistory.getRecent === 'function'
        ? window.TechEconHistory.getRecent(1)
        : [];
    if (!history || history.length === 0) return Promise.resolve();

    var anchor = history[0];

    return Promise.all([fetchJson(METADATA_URL), fetchJson(RELATED_URL)])
      .then(function (results) {
        var metadata = results[0] || {};
        var related = results[1] || {};
        var metadataItems = metadata.items || [];
        var relatedItems = related.items || {};

        var sourceId = findItemId(metadataItems, anchor);
        if (!sourceId) return;

        var neighbours = relatedItems[sourceId] || [];
        if (neighbours.length === 0) return;

        var resolved = resolveNeighbours(metadataItems, neighbours, sourceId);
        if (resolved.length === 0) return;

        renderRow(container, anchor, resolved);
        container.style.display = 'block';
      })
      .catch(function (err) {
        // Silent failure mode — the placeholder simply stays hidden. We
        // log to console for debugging but never throw, never alert.
        if (typeof console !== 'undefined' && console.warn) {
          console.warn('[because-you-viewed]', err);
        }
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Public API for tests + manual triggering.
  window.BecauseYouViewed = {
    init: init,
    findItemId: findItemId,
    resolveNeighbours: resolveNeighbours,
    renderRow: renderRow,
  };
})();
