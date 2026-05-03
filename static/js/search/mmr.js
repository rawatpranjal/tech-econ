/**
 * MMR (Maximal Marginal Relevance) Diversity Reranking — Re1
 *
 * Purpose:
 *   Reduce near-duplicate results in hybrid search. After RRF fusion,
 *   apply MMR to the top-K so the displayed list trades a small amount
 *   of relevance for noticeable topical diversity.
 *
 *   For each pick after the first:
 *     score(i) = lambda * relevance(i) - (1 - lambda) * max_{s in selected} cos(emb_i, emb_s)
 *
 *   lambda = 1.0 → pure relevance (no-op)
 *   lambda = 0.0 → pure diversity
 *   lambda = 0.7 → balanced (default for tech-econ)
 *
 * Mirrors search-synonyms.js loader pattern (AMD/CJS/global) so the
 * worker can importScripts() it and tests can require() it.
 *
 * Inputs:  scored items + embedding lookup function + lambda + topK
 * Outputs: reordered slice (length ≤ topK)
 * Side effects: none (pure)
 * Reproducibility: deterministic — same inputs → same output
 */
(function (global) {
  'use strict';

  // -----------------------------------------------------------------
  // Cosine similarity for two same-length numeric vectors. Returns 0
  // for any malformed / mismatched / zero-norm input rather than NaN
  // so downstream MMR doesn't propagate garbage.
  // -----------------------------------------------------------------
  function cosineSim(a, b) {
    if (!a || !b) return 0;
    var len = a.length;
    if (len !== b.length || len === 0) return 0;

    var dot = 0;
    var normA = 0;
    var normB = 0;
    for (var i = 0; i < len; i++) {
      var av = a[i];
      var bv = b[i];
      dot += av * bv;
      normA += av * av;
      normB += bv * bv;
    }
    if (normA === 0 || normB === 0) return 0;
    return dot / Math.sqrt(normA * normB);
  }

  // -----------------------------------------------------------------
  // MMR reranking.
  //
  // @param {Array<Object>} items - candidates with {id, ...relevanceScore}
  // @param {Function} embeddingLookup - (id: string) => Float32Array | null
  // @param {Object} [options]
  // @param {number} [options.lambda=0.7] - relevance/diversity tradeoff
  // @param {number} [options.topK] - max output length (default = items.length)
  // @param {string} [options.scoreField='rrfScore'] - which field on each
  //                  item carries the relevance signal
  // @returns {Array<Object>} reordered slice
  //
  // Items without an embedding are NOT excluded — they're appended after
  // the diverse set, preserving their relative order. This matters because
  // some items in the catalogue may not yet have generated embeddings.
  // -----------------------------------------------------------------
  function mmrRerank(items, embeddingLookup, options) {
    options = options || {};
    var lambda = options.lambda;
    if (typeof lambda !== 'number' || isNaN(lambda)) lambda = 0.7;
    if (lambda < 0) lambda = 0;
    if (lambda > 1) lambda = 1;
    var topK = typeof options.topK === 'number' ? options.topK : (items ? items.length : 0);
    var scoreField = options.scoreField || 'rrfScore';

    if (!Array.isArray(items) || items.length === 0) return [];
    if (typeof embeddingLookup !== 'function') {
      // No embeddings available → degrade to identity (sorted by score)
      return items.slice(0, topK);
    }

    // Cache embeddings once per call — embeddingLookup may be expensive
    // (subarray slicing into a packed Float32Array, etc.).
    var n = items.length;
    var embs = new Array(n);
    var withEmb = [];
    var withoutEmb = [];
    for (var i = 0; i < n; i++) {
      var e = embeddingLookup(items[i].id);
      embs[i] = e || null;
      if (e) withEmb.push(i);
      else withoutEmb.push(i);
    }

    // Fast path: if lambda === 1, MMR collapses to pure relevance.
    // Sort defensively by scoreField in case the caller passed unsorted
    // input or used a non-default field.
    if (lambda >= 0.999) {
      var sortedByScore = items.slice().sort(function (a, b) {
        var sa = typeof a[scoreField] === 'number' ? a[scoreField] : 0;
        var sb = typeof b[scoreField] === 'number' ? b[scoreField] : 0;
        return sb - sa;
      });
      return sortedByScore.slice(0, topK);
    }

    // Greedy MMR over indices that have embeddings.
    var pool = withEmb.slice();
    var selected = []; // indices in items[] order
    var maxSimToSel = {}; // index -> max cosine to anything in `selected`

    while (pool.length > 0 && selected.length < topK) {
      var bestIdx = -1;
      var bestScore = -Infinity;

      for (var p = 0; p < pool.length; p++) {
        var idx = pool[p];
        var rel = items[idx][scoreField];
        if (typeof rel !== 'number' || isNaN(rel)) rel = 0;
        var sim = maxSimToSel[idx] || 0;
        var mmrScore = lambda * rel - (1 - lambda) * sim;
        if (mmrScore > bestScore) {
          bestScore = mmrScore;
          bestIdx = p;
        }
      }
      if (bestIdx === -1) break;

      var picked = pool[bestIdx];
      selected.push(picked);
      pool.splice(bestIdx, 1);

      // Update max-sim for everyone left in the pool
      var pickedEmb = embs[picked];
      for (var q = 0; q < pool.length; q++) {
        var qIdx = pool[q];
        var s = cosineSim(pickedEmb, embs[qIdx]);
        if (s > (maxSimToSel[qIdx] || 0)) maxSimToSel[qIdx] = s;
      }
    }

    // Append any items without embeddings, in their original order, to
    // fill out the topK slot if there's room.
    var result = selected.map(function (i) { return items[i]; });
    for (var w = 0; w < withoutEmb.length && result.length < topK; w++) {
      result.push(items[withoutEmb[w]]);
    }
    return result;
  }

  // -----------------------------------------------------------------
  // Module export
  // -----------------------------------------------------------------
  var MMR = {
    cosineSim: cosineSim,
    mmrRerank: mmrRerank,
  };

  if (typeof define === 'function' && define.amd) {
    define(function () { return MMR; });
  } else if (typeof module === 'object' && module.exports) {
    module.exports = MMR;
  } else {
    global.MMR = MMR;
  }
})(typeof window !== 'undefined' ? window : typeof self !== 'undefined' ? self : this);
