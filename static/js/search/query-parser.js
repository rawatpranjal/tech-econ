/**
 * Query Parser Module
 *
 * Parses search queries to extract:
 * - Phrases: "exact phrase"
 * - Field filters: author:Smith, year:2024, topic:Causal
 * - Negations: -term, -"excluded phrase"
 * - Regular terms: remaining keywords
 */
(function(global) {
  'use strict';

  var QueryParser = {};

  /**
   * Parse a search query into structured components
   * @param {string} rawQuery - The raw search query
   * @returns {Object} Parsed query with phrases, fields, negations, terms
   */
  QueryParser.parse = function(rawQuery) {
    if (!rawQuery || typeof rawQuery !== 'string') {
      return {
        phrases: [],
        fields: {},
        negations: { terms: [], phrases: [] },
        terms: [],
        cleanQuery: ''
      };
    }

    var result = {
      phrases: [],        // ["exact phrase", ...]
      fields: {},         // { author: ["Smith"], year: ["2024"] }
      negations: {
        terms: [],        // ["excluded"]
        phrases: []       // ["excluded phrase"]
      },
      terms: [],          // ["remaining", "keywords"]
      cleanQuery: ''      // Query without special syntax for fuzzy search
    };

    var query = rawQuery.trim();
    var remaining = query;

    // 1. Extract quoted phrases (including negated ones)
    var phraseRegex = /(-?)"([^"]+)"/g;
    var match;
    while ((match = phraseRegex.exec(query)) !== null) {
      var isNegated = match[1] === '-';
      var phrase = match[2].trim();
      if (phrase) {
        if (isNegated) {
          result.negations.phrases.push(phrase.toLowerCase());
        } else {
          result.phrases.push(phrase.toLowerCase());
        }
      }
      remaining = remaining.replace(match[0], ' ');
    }

    // 2. Extract field filters (field:value)
    // Collect all matches first — modifying `remaining` inside the exec() loop
    // corrupts lastIndex because the string length changes mid-scan.
    var fieldRegex = /(\w+):(\S+)/g;
    var fieldMatches = [];
    while ((match = fieldRegex.exec(remaining)) !== null) {
      fieldMatches.push({ raw: match[0], field: match[1], value: match[2] });
    }
    for (var fi = 0; fi < fieldMatches.length; fi++) {
      var fm = fieldMatches[fi];
      var normalizedField = normalizeFieldName(fm.field.toLowerCase());
      if (normalizedField && fm.value) {
        if (!result.fields[normalizedField]) {
          result.fields[normalizedField] = [];
        }
        result.fields[normalizedField].push(fm.value.trim());
      }
      remaining = remaining.replace(fm.raw, ' ');
    }

    // 3. Extract negated terms (-term)
    var negationRegex = /-(\w+)/g;
    while ((match = negationRegex.exec(remaining)) !== null) {
      var term = match[1].trim().toLowerCase();
      if (term && term.length > 1) {  // Ignore single-char negations
        result.negations.terms.push(term);
      }
      remaining = remaining.replace(match[0], ' ');
    }

    // 4. Extract remaining terms
    var terms = remaining.trim().split(/\s+/).filter(function(t) {
      return t && t.length > 0;
    });
    result.terms = terms.map(function(t) { return t.toLowerCase(); });

    // 5. Build clean query for fuzzy search (terms + phrases)
    var cleanParts = result.terms.concat(result.phrases);
    result.cleanQuery = cleanParts.join(' ');

    return result;
  };

  /**
   * Normalize field names to standard fields
   * @param {string} field - Raw field name
   * @returns {string|null} - Normalized field name or null if invalid
   */
  function normalizeFieldName(field) {
    var fieldMap = {
      // Author variations
      'author': 'author',
      'authors': 'author',
      'by': 'author',
      'writer': 'author',

      // Year variations
      'year': 'year',
      'date': 'year',
      'published': 'year',
      'yr': 'year',

      // Topic variations
      'topic': 'topic',
      'area': 'topic',
      'field': 'topic',
      'domain': 'topic',

      // Type variations
      'type': 'type',
      'kind': 'type',
      'category': 'type'
    };

    return fieldMap[field] || null;
  }

  /**
   * Check if a result matches the parsed query filters
   * @param {Object} result - Search result to check
   * @param {Object} parsedQuery - Parsed query from parse()
   * @returns {boolean} - Whether result matches filters
   */
  QueryParser.matchesFilters = function(result, parsedQuery) {
    // Check field filters
    for (var field in parsedQuery.fields) {
      var values = parsedQuery.fields[field];

      if (field === 'author') {
        var authors = (result.authors || result.tags || '').toLowerCase();
        var hasAuthor = values.some(function(v) {
          return authors.indexOf(v.toLowerCase()) !== -1;
        });
        if (!hasAuthor) return false;
      }

      if (field === 'year') {
        var year = result.year;
        if (!year) return false;
        var hasYear = values.some(function(v) {
          return String(year) === v;
        });
        if (!hasYear) return false;
      }

      if (field === 'topic') {
        var topic = (result.topic || result.category || '').toLowerCase();
        var hasTopic = values.some(function(v) {
          return topic.indexOf(v.toLowerCase()) !== -1;
        });
        if (!hasTopic) return false;
      }

      if (field === 'type') {
        var type = result.type || '';
        var hasType = values.some(function(v) {
          return type === v.toLowerCase();
        });
        if (!hasType) return false;
      }
    }

    // Check phrase matches
    for (var i = 0; i < parsedQuery.phrases.length; i++) {
      var phrase = parsedQuery.phrases[i];
      var searchText = [
        result.name || '',
        result.description || '',
        result.tags || '',
        result.authors || ''
      ].join(' ').toLowerCase();

      if (searchText.indexOf(phrase) === -1) {
        return false;
      }
    }

    // Check negations
    var negationText = [
      result.name || '',
      result.description || '',
      result.tags || '',
      result.authors || ''
    ].join(' ').toLowerCase();

    for (var j = 0; j < parsedQuery.negations.terms.length; j++) {
      if (negationText.indexOf(parsedQuery.negations.terms[j]) !== -1) {
        return false;
      }
    }

    for (var k = 0; k < parsedQuery.negations.phrases.length; k++) {
      if (negationText.indexOf(parsedQuery.negations.phrases[k]) !== -1) {
        return false;
      }
    }

    return true;
  };

  /**
   * Apply parsed query filters to search results
   * @param {Array} results - Search results
   * @param {Object} parsedQuery - Parsed query from parse()
   * @returns {Array} - Filtered results
   */
  QueryParser.applyFilters = function(results, parsedQuery) {
    // If no special filters, return all results
    if (!parsedQuery.phrases.length &&
        !Object.keys(parsedQuery.fields).length &&
        !parsedQuery.negations.terms.length &&
        !parsedQuery.negations.phrases.length) {
      return results;
    }

    return results.filter(function(result) {
      return QueryParser.matchesFilters(result, parsedQuery);
    });
  };

  /**
   * Get a human-readable description of the parsed query
   * @param {Object} parsedQuery - Parsed query from parse()
   * @returns {string} - Description
   */
  QueryParser.describe = function(parsedQuery) {
    var parts = [];

    if (parsedQuery.terms.length) {
      parts.push('searching for: ' + parsedQuery.terms.join(' '));
    }

    if (parsedQuery.phrases.length) {
      parts.push('exact phrases: "' + parsedQuery.phrases.join('", "') + '"');
    }

    for (var field in parsedQuery.fields) {
      parts.push(field + ': ' + parsedQuery.fields[field].join(', '));
    }

    if (parsedQuery.negations.terms.length) {
      parts.push('excluding: ' + parsedQuery.negations.terms.join(', '));
    }

    return parts.join(' | ');
  };

  // Export
  if (typeof module === 'object' && module.exports) {
    module.exports = QueryParser;
  } else {
    global.QueryParser = QueryParser;
  }

})(typeof window !== 'undefined' ? window : typeof self !== 'undefined' ? self : this);
