/**
 * Search Spellcheck Module (Re2)
 *
 * When a user's keyword search returns zero hits, attempt a Levenshtein
 * distance-based correction against the index vocabulary. If a single
 * confidently-better spelling exists, return it as a "Did you mean…?"
 * suggestion. Otherwise stay silent.
 *
 * Used by both search-worker.js and (for tests) Node CommonJS. Mirrors
 * the loader/exporter pattern in search-synonyms.js.
 *
 * Inputs:  query string + vocabulary Set of lowercased single-word tokens
 * Outputs: corrected query string OR null
 * Side effects: none (all functions pure)
 * Reproducibility: deterministic; same inputs → same output
 */
(function (global) {
  'use strict';

  // -----------------------------------------------------------------
  // Tunables
  // -----------------------------------------------------------------
  // Maximum edit distance for a single word to be considered a typo.
  // Above this we don't risk a false suggestion.
  var MAX_EDIT_DISTANCE = 2;
  // Don't bother spell-checking very short words (too noisy — "a" → "as"
  // is not useful).
  var MIN_WORD_LEN = 4;
  // Don't suggest if the user's input word looks like a typo *but* the
  // best vocabulary match is itself only marginally longer than the
  // user's input. Avoids over-correcting valid uncommon words.
  var MIN_VOCAB_LEN_DIFF = 0;
  // Words that should never be suggested *as corrections* — purely
  // structural English bits that contaminate vocabularies built from
  // descriptions. Filtered when building the vocab.
  var STOP_WORDS = new Set([
    'the','and','for','with','from','this','that','are','was','have','has',
    'but','not','you','can','will','about','into','their','than','then',
    'they','them','what','when','where','which','who','why','how','also',
    'such','some','any','all','one','two','three','first','second','more',
    'most','other','others','these','those','only','its','our','your','his',
    'her','him','she','out','over','under','across','through','between',
    'while','because','though','within','before','after','during','since',
    'around','among','many','much','very','just','like','well','only','own',
  ]);

  // -----------------------------------------------------------------
  // Levenshtein distance with an early-out cap.
  // Standard Wagner–Fischer DP. Bails out as soon as it can prove the
  // distance is going to exceed `cap`, which is a meaningful speed-up
  // when comparing a query word against thousands of vocab words.
  // Pure function.
  // -----------------------------------------------------------------
  function levenshtein(a, b, cap) {
    if (a === b) return 0;
    if (cap == null) cap = MAX_EDIT_DISTANCE;

    if (Math.abs(a.length - b.length) > cap) return cap + 1;
    if (!a.length) return b.length;
    if (!b.length) return a.length;

    // Trim equal prefixes / suffixes — they contribute zero to the
    // distance and shrink the DP table.
    var start = 0;
    while (start < a.length && start < b.length && a.charCodeAt(start) === b.charCodeAt(start)) {
      start++;
    }
    var endA = a.length;
    var endB = b.length;
    while (endA > start && endB > start && a.charCodeAt(endA - 1) === b.charCodeAt(endB - 1)) {
      endA--;
      endB--;
    }
    var sa = a.slice(start, endA);
    var sb = b.slice(start, endB);
    if (!sa.length) return sb.length > cap ? cap + 1 : sb.length;
    if (!sb.length) return sa.length > cap ? cap + 1 : sa.length;

    var prev = new Array(sb.length + 1);
    var curr = new Array(sb.length + 1);
    for (var j = 0; j <= sb.length; j++) prev[j] = j;

    for (var i = 1; i <= sa.length; i++) {
      curr[0] = i;
      var rowMin = curr[0];
      var ca = sa.charCodeAt(i - 1);
      for (var k = 1; k <= sb.length; k++) {
        var cost = ca === sb.charCodeAt(k - 1) ? 0 : 1;
        curr[k] = Math.min(
          prev[k] + 1,        // deletion
          curr[k - 1] + 1,    // insertion
          prev[k - 1] + cost  // substitution
        );
        if (curr[k] < rowMin) rowMin = curr[k];
      }
      if (rowMin > cap) return cap + 1;
      var tmp = prev; prev = curr; curr = tmp;
    }
    return prev[sb.length];
  }

  // -----------------------------------------------------------------
  // Build a vocabulary Set from a list of arbitrary strings (typically
  // names + categories + tags from the index docs). Lowercases, splits
  // on non-letter chars, drops short words and stop-words.
  // Pure function.
  // -----------------------------------------------------------------
  function buildVocabulary(strings) {
    var vocab = new Set();
    if (!strings) return vocab;
    for (var i = 0; i < strings.length; i++) {
      var s = strings[i];
      if (!s) continue;
      var tokens = String(s).toLowerCase().match(/[a-z][a-z0-9]+/g);
      if (!tokens) continue;
      for (var j = 0; j < tokens.length; j++) {
        var w = tokens[j];
        if (w.length < MIN_WORD_LEN) continue;
        if (STOP_WORDS.has(w)) continue;
        vocab.add(w);
      }
    }
    return vocab;
  }

  // -----------------------------------------------------------------
  // Find the closest vocab match for a single token. Returns null if
  // nothing within MAX_EDIT_DISTANCE.
  // -----------------------------------------------------------------
  function closestMatch(token, vocab, cap) {
    if (cap == null) cap = MAX_EDIT_DISTANCE;
    var lower = token.toLowerCase();
    if (vocab.has(lower)) return null; // already in vocab, not a typo
    if (lower.length < MIN_WORD_LEN) return null;

    var best = null;
    var bestDist = cap + 1;
    var iter = vocab.values();
    var step = iter.next();
    while (!step.done) {
      var word = step.value;
      // Quick length-difference filter
      if (Math.abs(word.length - lower.length) > cap) {
        step = iter.next();
        continue;
      }
      var d = levenshtein(lower, word, cap);
      if (d < bestDist) {
        bestDist = d;
        best = word;
        if (d === 1) break; // distance 1 is good enough; stop searching
      }
      step = iter.next();
    }
    if (!best) return null;
    if (bestDist > cap) return null;
    if (best.length - lower.length < MIN_VOCAB_LEN_DIFF) return null;
    return best;
  }

  // -----------------------------------------------------------------
  // Whole-query spellcheck. Returns:
  //   { corrected: "...", changed: true } if at least one word was
  //     corrected
  //   null otherwise
  // -----------------------------------------------------------------
  function suggest(query, vocab) {
    if (!query || !vocab || vocab.size === 0) return null;
    var raw = String(query);
    // Tokenize while preserving non-word separators so we can stitch
    // the corrected query back together.
    var parts = raw.split(/(\s+|[^A-Za-z0-9'-]+)/);
    var changed = false;
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (!/[A-Za-z]{4,}/.test(p)) continue;
      var match = closestMatch(p, vocab);
      if (match && match !== p.toLowerCase()) {
        // Preserve original case roughly: lowercase replacement is fine
        // for now — the banner will display it as-is.
        parts[i] = match;
        changed = true;
      }
    }
    if (!changed) return null;
    return { corrected: parts.join(''), changed: true };
  }

  // -----------------------------------------------------------------
  // Module export. Mirrors search-synonyms.js.
  // -----------------------------------------------------------------
  var Spellcheck = {
    levenshtein: levenshtein,
    buildVocabulary: buildVocabulary,
    closestMatch: closestMatch,
    suggest: suggest,
    // Constants exposed for tests + future tuning
    MAX_EDIT_DISTANCE: MAX_EDIT_DISTANCE,
    MIN_WORD_LEN: MIN_WORD_LEN,
  };

  if (typeof define === 'function' && define.amd) {
    define(function () { return Spellcheck; });
  } else if (typeof module === 'object' && module.exports) {
    module.exports = Spellcheck;
  } else {
    global.Spellcheck = Spellcheck;
  }
})(typeof window !== 'undefined' ? window : typeof self !== 'undefined' ? self : this);
