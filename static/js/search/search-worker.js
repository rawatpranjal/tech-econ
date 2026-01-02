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
  SEMANTIC_WEIGHT: 1.0,
  MODEL_SCORE_WEIGHT: 0.4  // Engagement boost weight (0.3-0.5 range)
};

// Audience detection patterns
var BEGINNER_PATTERNS = /intro|beginner|start|basic|learn|what is|simple|getting started|tutorial|guide for/i;
var ADVANCED_PATTERNS = /paper|research|advanced|theory|proof|optimal|state of the art|sota|novel|algorithm/i;

/**
 * Score items based on synthetic questions matching
 * Returns bonus score (0-0.3) if query matches an item's synthetic questions
 */
function scoreSyntheticQuestions(item, query) {
  if (!item.synthetic_questions || !query) return 0;
  // Guard: ensure synthetic_questions is an array
  if (!Array.isArray(item.synthetic_questions)) return 0;

  var queryLower = query.toLowerCase().trim();
  var queryWords = queryLower.split(/\s+/);

  for (var i = 0; i < item.synthetic_questions.length; i++) {
    var q = item.synthetic_questions[i];
    // Guard: skip non-string entries
    if (typeof q !== 'string') continue;
    q = q.toLowerCase();
    // Full query match
    if (q.includes(queryLower) || queryLower.includes(q)) {
      return 0.3;
    }
    // Partial word overlap (at least 3 words match)
    var matchCount = 0;
    for (var j = 0; j < queryWords.length; j++) {
      if (queryWords[j].length > 2 && q.includes(queryWords[j])) {
        matchCount++;
      }
    }
    if (matchCount >= 3) return 0.2;
    if (matchCount >= 2) return 0.1;
  }
  return 0;
}

/**
 * Get audience boost multiplier based on query complexity
 * Boosts beginner content for beginner queries, advanced for research queries
 */
function getAudienceBoost(item, query) {
  if (!item.audience || !query) return 1.0;

  var audienceStr = Array.isArray(item.audience) ? item.audience.join(',') : item.audience;

  if (BEGINNER_PATTERNS.test(query)) {
    if (audienceStr.includes('Junior-DS') || audienceStr.includes('Beginner')) {
      return 1.25;  // 25% boost for beginner content on beginner queries
    }
    if (audienceStr.includes('Senior-DS') || audienceStr.includes('PhD')) {
      return 0.85;  // Slight penalty for advanced content on beginner queries
    }
  }

  if (ADVANCED_PATTERNS.test(query)) {
    if (audienceStr.includes('Senior-DS') || audienceStr.includes('PhD')) {
      return 1.2;  // 20% boost for advanced content on research queries
    }
  }

  return 1.0;
}

/**
 * Get model score boost multiplier based on engagement prediction
 * Applies a weighted multiplier to surface popular/engaged content
 *
 * @param {Object} item - Search result item
 * @param {number} weight - Weight for model_score influence (0-1)
 * @returns {number} Multiplier between 1.0 and 1.0 + weight
 */
function getModelScoreBoost(item, weight) {
  var modelScore = item.model_score;

  // Handle missing/invalid scores gracefully (cold start items get neutral boost)
  if (typeof modelScore !== 'number' || isNaN(modelScore)) {
    return 1.0;
  }

  // Clamp to valid range [0, 1]
  modelScore = Math.max(0, Math.min(1, modelScore));

  // Formula: 1.0 + (model_score * weight)
  // With weight=0.4 and score=1.0: multiplier = 1.4 (40% boost)
  // With weight=0.4 and score=0.5: multiplier = 1.2 (20% boost)
  // With weight=0.4 and score=0.0: multiplier = 1.0 (no boost)
  return 1.0 + (modelScore * weight);
}

/**
 * Handle messages from main thread
 */
self.onmessage = function(event) {
  var message = event.data;

  // Guard: validate message structure
  if (!message || typeof message.type !== 'string') {
    console.warn('[SearchWorker] Invalid message received:', message);
    return;
  }

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
    case 'SEARCH_PROGRESSIVE':
      handleProgressiveSearch(message.payload, message.id);
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
  console.log('[SearchWorker] handleLoadIndex called');
  try {
    var indexData = payload.indexData;

    // Guard: validate index data structure
    if (!indexData || !indexData.documents || !indexData.config || !indexData.config.fields) {
      console.error('[SearchWorker] Invalid index data structure');
      postMessage({ type: 'INDEX_LOADED', payload: { success: false, error: 'Invalid index structure' } });
      return;
    }

    console.log('[SearchWorker] Loading index with', indexData.documents.length, 'documents');

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
    console.log('[SearchWorker] MiniSearch instance created, adding documents...');
    miniSearch.addAll(indexData.documents);
    searchIndex = indexData;
    console.log('[SearchWorker] Documents added successfully');

    postMessage({
      type: 'INDEX_LOADED',
      payload: {
        success: true,
        count: indexData.documents.length
      }
    });
  } catch (error) {
    console.error('[SearchWorker] Index load error:', error);
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
 * Load embeddings (binary format - Float32 or quantized Int8)
 */
function handleLoadEmbeddings(payload) {
  try {
    embeddingsMetadata = payload.metadata;

    if (payload.quantized) {
      // Dequantize Int8 to Float32
      var view = new DataView(payload.embeddingsBuffer);
      var count = view.getUint32(0, true);  // Little-endian
      var dim = view.getUint32(4, true);

      var headerSize = 8;
      var scaleSize = count * 4;  // Float32 min/max per vector

      // Guard: validate buffer size before creating TypedArrays
      var expectedSize = headerSize + scaleSize * 2 + count * dim;
      if (payload.embeddingsBuffer.byteLength < expectedSize) {
        console.error('[SearchWorker] Embeddings buffer too small:', payload.embeddingsBuffer.byteLength, 'vs expected', expectedSize);
        postMessage({ type: 'EMBEDDINGS_LOADED', payload: { success: false, error: 'Buffer size mismatch' } });
        return;
      }

      // Read scale factors
      var mins = new Float32Array(payload.embeddingsBuffer, headerSize, count);
      var maxs = new Float32Array(payload.embeddingsBuffer, headerSize + scaleSize, count);

      // Read quantized values
      var quantized = new Uint8Array(payload.embeddingsBuffer, headerSize + scaleSize * 2, count * dim);

      // Dequantize to Float32
      embeddings = new Float32Array(count * dim);
      for (var i = 0; i < count; i++) {
        var min = mins[i];
        var range = maxs[i] - min;
        var offset = i * dim;
        for (var j = 0; j < dim; j++) {
          embeddings[offset + j] = (quantized[offset + j] / 255) * range + min;
        }
      }

      console.log('[SearchWorker] Dequantized', count, 'embeddings from Int8');
    } else {
      // Standard Float32 format
      embeddings = new Float32Array(payload.embeddingsBuffer);
    }

    postMessage({
      type: 'EMBEDDINGS_LOADED',
      payload: {
        success: true,
        count: embeddingsMetadata.count,
        quantized: !!payload.quantized
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

  // Timeout promise (30 seconds)
  var MODEL_LOAD_TIMEOUT = 30000;
  var timeoutPromise = new Promise(function(_, reject) {
    setTimeout(function() {
      reject(new Error('Model loading timeout after ' + MODEL_LOAD_TIMEOUT + 'ms'));
    }, MODEL_LOAD_TIMEOUT);
  });

  // Dynamic import of Transformers.js with timeout
  var loadPromise = import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.0.0')
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
    });

  // Race between load and timeout
  modelLoadPromise = Promise.race([loadPromise, timeoutPromise])
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
  console.log('[SearchWorker] handleSearch:', payload.query, 'semantic:', payload.semantic);
  var query = payload.query;
  var topK = payload.topK || 20;
  var useSemanticSearch = payload.semantic !== false && transformersModel && embeddings;

  // Start with keyword search
  var keywordResults = performKeywordSearch(query, 100);
  console.log('[SearchWorker] Keyword search returned', keywordResults.length, 'results');

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

    // Fuse results using RRF with enriched field boosting
    var fusedResults = reciprocalRankFusion(keywordResults, semanticResults, topK, query);

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
 * Perform progressive search - send keyword results immediately, then semantic
 */
function handleProgressiveSearch(payload, messageId) {
  var query = payload.query;
  var topK = payload.topK || 20;
  var useSemanticSearch = payload.semantic !== false && transformersModel && embeddings;

  // Phase 1: Send keyword results immediately (fast path)
  var keywordResults = performKeywordSearch(query, 100);

  postMessage({
    type: 'KEYWORD_RESULTS',
    id: messageId,
    payload: {
      results: keywordResults.slice(0, topK),
      mode: 'keyword',
      isPartial: useSemanticSearch  // More results coming if semantic is available
    }
  });

  // Phase 2: If semantic available, compute and send hybrid results
  if (useSemanticSearch) {
    embedQuery(query).then(function(queryEmbedding) {
      if (!queryEmbedding) {
        // No embedding, keyword results are final
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

      var semanticResults = performSemanticSearch(queryEmbedding, 100);

      // Check if semantic scores are too low
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

      // Fuse results using RRF with enriched field boosting
      var fusedResults = reciprocalRankFusion(keywordResults, semanticResults, topK, query);

      postMessage({
        type: 'SEARCH_RESULTS',
        id: messageId,
        payload: {
          results: fusedResults,
          mode: 'hybrid'
        }
      });
    }).catch(function(error) {
      // Error during semantic, keyword results are final
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
  // If no semantic search, keyword results were already sent as final
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
  if (!miniSearch) {
    console.error('[SearchWorker] miniSearch is null! Index not loaded.');
    return [];
  }
  console.log('[SearchWorker] performKeywordSearch:', query);

  // Expand query with synonyms
  var expandedQueries = expandQuery(query);

  var seen = {};
  var allResults = [];

  expandedQueries.forEach(function(q, queryIndex) {
    // Guard: wrap search in try-catch to handle malformed queries
    var results;
    try {
      results = miniSearch.search(q, { limit: limit });
    } catch (e) {
      console.error('[SearchWorker] miniSearch.search failed:', e);
      results = [];
    }

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
          source: 'keyword',
          // Enriched fields from LLM
          difficulty: result.difficulty,
          prerequisites: result.prerequisites,
          topic_tags: result.topic_tags,
          summary: result.summary,
          audience: result.audience
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
 * Boost exact matches in results with enhanced signals
 */
function boostExactMatches(results, query) {
  var queryLower = query.toLowerCase().trim();
  var queryWords = queryLower.split(/\s+/).filter(function(w) { return w.length > 2; });

  return results.map(function(result) {
    var nameLower = (result.name || '').toLowerCase();
    var descLower = (result.description || '').toLowerCase();
    var tagsLower = (result.tags || '').toLowerCase();
    var boost = 1.0;

    // Exact name match - strongest boost
    if (nameLower === queryLower) {
      boost = 3.0;
    }
    // Name starts with query
    else if (nameLower.startsWith(queryLower)) {
      boost = 2.0;
    }
    // Name contains query as whole word
    else if (new RegExp('\\b' + escapeRegex(queryLower) + '\\b', 'i').test(nameLower)) {
      boost = 1.5;
    }

    // Tag match boost
    if (tagsLower.indexOf(queryLower) !== -1) {
      boost *= 1.2;
    }

    // Multi-word query: boost if all words found
    if (queryWords.length > 1) {
      var allWordsFound = queryWords.every(function(word) {
        return nameLower.indexOf(word) !== -1 ||
               descLower.indexOf(word) !== -1 ||
               tagsLower.indexOf(word) !== -1;
      });
      if (allWordsFound) {
        boost *= 1.3;
      }
    }

    // Quality signals: longer descriptions tend to be more informative
    if (result.description && result.description.length > 100) {
      boost *= 1.05;
    }

    // Type-based boost (papers and packages are primary content)
    if (result.type === 'paper' || result.type === 'package') {
      boost *= 1.1;
    }

    return Object.assign({}, result, {
      score: (typeof result.score === 'number' ? result.score : 0) * boost
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
    // Guard: validate output structure before accessing .data
    if (!output || !output.data) {
      console.warn('[SearchWorker] embedQuery: invalid model output');
      return null;
    }
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

  // Guard: validate queryEmbedding dimensions to prevent NaN cascade
  if (!queryEmbedding || queryEmbedding.length !== CONFIG.DIMENSIONS) {
    console.warn('[SearchWorker] Query embedding dimension mismatch:', queryEmbedding ? queryEmbedding.length : 'null', 'vs expected', CONFIG.DIMENSIONS);
    return [];
  }

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
    // Guard: skip invalid items
    if (!item || !item.id) continue;

    results.push({
      id: item.id,
      name: item.name,
      description: item.description,
      category: item.category,
      url: item.url,
      type: item.type,
      score: similarity,
      source: 'semantic',
      // Enriched fields from LLM
      difficulty: item.difficulty,
      prerequisites: item.prerequisites,
      summary: item.summary
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
 * RRF score = sum(weight / (k + rank_in_list))
 *
 * Uses adaptive weighting based on result quality:
 * - If keyword results have high scores, trust them more
 * - If semantic results are highly confident, trust them more
 */
function reciprocalRankFusion(keywordResults, semanticResults, topK, query) {
  var k = CONFIG.RRF_K;
  var scores = {};
  var items = {};

  // Adaptive weighting based on result quality
  var keywordWeight = CONFIG.KEYWORD_WEIGHT;
  var semanticWeight = CONFIG.SEMANTIC_WEIGHT;

  // If top keyword result has very high score, trust keyword more
  if (keywordResults.length > 0 && keywordResults[0].score > 15) {
    keywordWeight = 1.5;
    semanticWeight = 0.7;
  }

  // If semantic results are very confident (high similarity), trust semantic more
  if (semanticResults.length > 0 && semanticResults[0].score > 0.7) {
    semanticWeight = 1.3;
  }

  // Score keyword results
  keywordResults.forEach(function(item, rank) {
    var rrfScore = keywordWeight / (k + rank + 1);
    scores[item.id] = (scores[item.id] || 0) + rrfScore;
    items[item.id] = item;
  });

  // Score semantic results
  semanticResults.forEach(function(item, rank) {
    var rrfScore = semanticWeight / (k + rank + 1);
    scores[item.id] = (scores[item.id] || 0) + rrfScore;
    if (!items[item.id]) {
      items[item.id] = item;
    }
  });

  // Build final results with enriched field boosts
  var fusedResults = Object.keys(scores).map(function(id) {
    var item = items[id];
    var baseScore = scores[id];

    // Apply synthetic questions bonus (adds 0-0.3)
    var syntheticBonus = scoreSyntheticQuestions(item, query);

    // Apply audience boost multiplier (0.85-1.25x)
    var audienceMultiplier = getAudienceBoost(item, query);

    // Apply model score boost multiplier (1.0-1.4x based on engagement)
    var modelScoreMultiplier = getModelScoreBoost(item, CONFIG.MODEL_SCORE_WEIGHT);

    var finalScore = (baseScore + syntheticBonus) * audienceMultiplier * modelScoreMultiplier;

    return Object.assign({}, item, {
      rrfScore: finalScore,
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
