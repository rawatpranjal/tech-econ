/**
 * Search Worker - Runs search operations in a Web Worker for non-blocking UI
 *
 * Handles:
 * - MiniSearch keyword search (BM25/TF-IDF)
 * - Transformers.js semantic query embedding
 * - Cosine similarity search against pre-computed embeddings
 * - Reciprocal Rank Fusion (RRF) for hybrid scoring
 */

// Import MiniSearch from CDN
importScripts('https://cdn.jsdelivr.net/npm/minisearch@6.3.0/dist/umd/index.min.js');

// State
var miniSearch = null;
var searchIndex = null;
var embeddings = null;
var embeddingsMetadata = null;
var transformersModel = null;
var isModelLoading = false;
var modelLoadPromise = null;
var synonyms = null;

// Configuration
var CONFIG = {
  DIMENSIONS: 384,
  MODEL_ID: 'Xenova/gte-small',
  RRF_K: 60,  // RRF constant
  KEYWORD_WEIGHT: 1.0,
  SEMANTIC_WEIGHT: 1.0
};

/**
 * Handle messages from main thread
 */
self.onmessage = function(event) {
  var message = event.data;
  var type = message.type;

  switch (type) {
    case 'INIT':
      handleInit(message.payload);
      break;
    case 'LOAD_INDEX':
      handleLoadIndex(message.payload);
      break;
    case 'LOAD_EMBEDDINGS':
      handleLoadEmbeddings(message.payload);
      break;
    case 'LOAD_SYNONYMS':
      handleLoadSynonyms(message.payload);
      break;
    case 'LOAD_MODEL':
      handleLoadModel();
      break;
    case 'SEARCH':
      handleSearch(message.payload, message.id);
      break;
    case 'KEYWORD_SEARCH':
      handleKeywordSearch(message.payload, message.id);
      break;
    default:
      console.warn('[SearchWorker] Unknown message type:', type);
  }
};

/**
 * Initialize worker with all data
 */
function handleInit(payload) {
  if (payload.synonyms) {
    synonyms = payload.synonyms;
  }

  postMessage({
    type: 'INIT_COMPLETE',
    payload: { success: true }
  });
}

/**
 * Load MiniSearch index
 */
function handleLoadIndex(payload) {
  try {
    var indexData = payload.indexData;

    // Create MiniSearch instance
    miniSearch = new MiniSearch({
      fields: indexData.config.fields,
      storeFields: indexData.config.storeFields,
      searchOptions: {
        boost: indexData.config.searchOptions.boost,
        fuzzy: indexData.config.searchOptions.fuzzy,
        prefix: indexData.config.searchOptions.prefix
      }
    });

    // Add all documents
    miniSearch.addAll(indexData.documents);
    searchIndex = indexData;

    postMessage({
      type: 'INDEX_LOADED',
      payload: {
        success: true,
        count: indexData.documents.length
      }
    });
  } catch (error) {
    postMessage({
      type: 'INDEX_LOADED',
      payload: {
        success: false,
        error: error.message
      }
    });
  }
}

/**
 * Load embeddings (binary format)
 */
function handleLoadEmbeddings(payload) {
  try {
    embeddingsMetadata = payload.metadata;
    embeddings = new Float32Array(payload.embeddingsBuffer);

    postMessage({
      type: 'EMBEDDINGS_LOADED',
      payload: {
        success: true,
        count: embeddingsMetadata.count
      }
    });
  } catch (error) {
    postMessage({
      type: 'EMBEDDINGS_LOADED',
      payload: {
        success: false,
        error: error.message
      }
    });
  }
}

/**
 * Load synonyms
 */
function handleLoadSynonyms(payload) {
  synonyms = payload.synonyms;
  postMessage({
    type: 'SYNONYMS_LOADED',
    payload: { success: true }
  });
}

/**
 * Load Transformers.js model
 */
function handleLoadModel() {
  if (transformersModel) {
    postMessage({
      type: 'MODEL_LOADED',
      payload: { success: true, cached: true }
    });
    return;
  }

  if (isModelLoading) {
    // Already loading, wait for it
    modelLoadPromise.then(function() {
      postMessage({
        type: 'MODEL_LOADED',
        payload: { success: !!transformersModel, cached: false }
      });
    });
    return;
  }

  isModelLoading = true;
  postMessage({
    type: 'MODEL_LOADING',
    payload: { status: 'starting' }
  });

  // Dynamic import of Transformers.js
  modelLoadPromise = import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.0.0')
    .then(function(module) {
      postMessage({
        type: 'MODEL_LOADING',
        payload: { status: 'loading_model' }
      });

      return module.pipeline('feature-extraction', CONFIG.MODEL_ID, {
        dtype: 'q8',  // Quantized for smaller size
        device: 'wasm'  // WebGPU not reliable in workers yet
      });
    })
    .then(function(extractor) {
      transformersModel = extractor;
      isModelLoading = false;
      postMessage({
        type: 'MODEL_LOADED',
        payload: { success: true, cached: false }
      });
    })
    .catch(function(error) {
      isModelLoading = false;
      console.error('[SearchWorker] Failed to load model:', error);
      postMessage({
        type: 'MODEL_LOADED',
        payload: { success: false, error: error.message }
      });
    });
}

/**
 * Perform hybrid search (keyword + semantic)
 */
function handleSearch(payload, messageId) {
  var query = payload.query;
  var topK = payload.topK || 20;
  var useSemanticSearch = payload.semantic !== false && transformersModel && embeddings;

  // Start with keyword search
  var keywordResults = performKeywordSearch(query, 100);

  if (!useSemanticSearch) {
    // Return keyword results only
    postMessage({
      type: 'SEARCH_RESULTS',
      id: messageId,
      payload: {
        results: keywordResults.slice(0, topK),
        mode: 'keyword'
      }
    });
    return;
  }

  // Perform semantic search
  embedQuery(query).then(function(queryEmbedding) {
    if (!queryEmbedding) {
      // Fallback to keyword only
      postMessage({
        type: 'SEARCH_RESULTS',
        id: messageId,
        payload: {
          results: keywordResults.slice(0, topK),
          mode: 'keyword'
        }
      });
      return;
    }

    var semanticResults = performSemanticSearch(queryEmbedding, 100);

    // Check if semantic scores are too low (nothing semantically close)
    var topSemanticScore = semanticResults.length > 0 ? semanticResults[0].score : 0;
    if (topSemanticScore < 0.3) {
      // Fall back to keyword-only results
      postMessage({
        type: 'SEARCH_RESULTS',
        id: messageId,
        payload: {
          results: keywordResults.slice(0, topK),
          mode: 'keyword-fallback'
        }
      });
      return;
    }

    // Fuse results using RRF
    var fusedResults = reciprocalRankFusion(keywordResults, semanticResults, topK);

    postMessage({
      type: 'SEARCH_RESULTS',
      id: messageId,
      payload: {
        results: fusedResults,
        mode: 'hybrid'
      }
    });
  }).catch(function(error) {
    // Fallback to keyword only
    postMessage({
      type: 'SEARCH_RESULTS',
      id: messageId,
      payload: {
        results: keywordResults.slice(0, topK),
        mode: 'keyword',
        error: error.message
      }
    });
  });
}

/**
 * Perform keyword-only search (fast path)
 */
function handleKeywordSearch(payload, messageId) {
  var query = payload.query;
  var topK = payload.topK || 20;

  var results = performKeywordSearch(query, topK);

  postMessage({
    type: 'SEARCH_RESULTS',
    id: messageId,
    payload: {
      results: results,
      mode: 'keyword'
    }
  });
}

/**
 * Perform keyword search with MiniSearch
 */
function performKeywordSearch(query, limit) {
  if (!miniSearch) return [];

  // Expand query with synonyms
  var expandedQueries = expandQuery(query);

  var seen = {};
  var allResults = [];

  expandedQueries.forEach(function(q, queryIndex) {
    var results = miniSearch.search(q, { limit: limit });

    results.forEach(function(result) {
      if (!seen[result.id]) {
        seen[result.id] = true;

        // Penalize synonym matches slightly
        var score = result.score;
        if (queryIndex > 0) {
          score = score * 0.9;  // 10% penalty for synonym matches
        }

        allResults.push({
          id: result.id,
          name: result.name,
          description: result.description,
          category: result.category,
          url: result.url,
          type: result.type,
          score: score,
          source: 'keyword'
        });
      }
    });
  });

  // Sort by score (higher is better in MiniSearch)
  allResults.sort(function(a, b) {
    return b.score - a.score;
  });

  // Boost exact matches
  allResults = boostExactMatches(allResults, query);

  return allResults.slice(0, limit);
}

/**
 * Expand query with synonyms
 */
function expandQuery(query) {
  if (!synonyms) return [query];

  var words = query.toLowerCase().split(/\s+/);
  var expanded = [query];

  words.forEach(function(word) {
    if (synonyms[word]) {
      synonyms[word].forEach(function(syn) {
        if (expanded.indexOf(syn) === -1) {
          expanded.push(syn);
        }
      });
    }
  });

  return expanded;
}

/**
 * Boost exact matches in results
 */
function boostExactMatches(results, query) {
  var queryLower = query.toLowerCase().trim();

  return results.map(function(result) {
    var nameLower = (result.name || '').toLowerCase();
    var boost = 1.0;

    // Exact name match - strongest boost
    if (nameLower === queryLower) {
      boost = 2.0;
    }
    // Name starts with query
    else if (nameLower.startsWith(queryLower)) {
      boost = 1.5;
    }
    // Name contains query as whole word
    else if (new RegExp('\\b' + escapeRegex(queryLower) + '\\b', 'i').test(nameLower)) {
      boost = 1.3;
    }

    return Object.assign({}, result, {
      score: result.score * boost
    });
  }).sort(function(a, b) {
    return b.score - a.score;
  });
}

/**
 * Escape regex special characters
 */
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Embed query using Transformers.js
 */
function embedQuery(query) {
  if (!transformersModel) {
    return Promise.resolve(null);
  }

  return transformersModel(query, {
    pooling: 'mean',
    normalize: true
  }).then(function(output) {
    return Array.from(output.data);
  }).catch(function(error) {
    console.error('[SearchWorker] Query embedding failed:', error);
    return null;
  });
}

/**
 * Perform semantic search using cosine similarity
 */
function performSemanticSearch(queryEmbedding, limit) {
  if (!embeddings || !embeddingsMetadata) return [];

  var results = [];
  var dim = CONFIG.DIMENSIONS;
  var count = embeddingsMetadata.count;

  // Calculate cosine similarity for all items
  for (var i = 0; i < count; i++) {
    var offset = i * dim;
    var similarity = 0;

    for (var j = 0; j < dim; j++) {
      similarity += queryEmbedding[j] * embeddings[offset + j];
    }

    var item = embeddingsMetadata.items[i];
    results.push({
      id: item.id,
      name: item.name,
      description: item.description,
      category: item.category,
      url: item.url,
      type: item.type,
      score: similarity,
      source: 'semantic'
    });
  }

  // Sort by similarity (higher is better)
  results.sort(function(a, b) {
    return b.score - a.score;
  });

  return results.slice(0, limit);
}

/**
 * Reciprocal Rank Fusion (RRF) to combine keyword and semantic results
 * RRF score = sum(1 / (k + rank_in_list))
 */
function reciprocalRankFusion(keywordResults, semanticResults, topK) {
  var k = CONFIG.RRF_K;
  var scores = {};
  var items = {};

  // Score keyword results
  keywordResults.forEach(function(item, rank) {
    var rrfScore = CONFIG.KEYWORD_WEIGHT / (k + rank + 1);
    scores[item.id] = (scores[item.id] || 0) + rrfScore;
    items[item.id] = item;
  });

  // Score semantic results
  semanticResults.forEach(function(item, rank) {
    var rrfScore = CONFIG.SEMANTIC_WEIGHT / (k + rank + 1);
    scores[item.id] = (scores[item.id] || 0) + rrfScore;
    if (!items[item.id]) {
      items[item.id] = item;
    }
  });

  // Build final results
  var fusedResults = Object.keys(scores).map(function(id) {
    return Object.assign({}, items[id], {
      rrfScore: scores[id],
      source: 'hybrid'
    });
  });

  // Sort by RRF score (higher is better)
  fusedResults.sort(function(a, b) {
    return b.rrfScore - a.rrfScore;
  });

  return fusedResults.slice(0, topK);
}

// Signal that worker is ready
postMessage({ type: 'WORKER_READY' });
