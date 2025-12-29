/**
 * Unified Search Module
 *
 * Consolidated search system for tech-econ.org with:
 * - MiniSearch for fast keyword search (BM25/TF-IDF)
 * - Transformers.js for semantic query embedding
 * - Hybrid scoring with Reciprocal Rank Fusion (RRF)
 * - Web Worker for non-blocking search
 * - IndexedDB caching for embeddings and model
 *
 * Replaces: global-search.js, page-search.js, search.js, vector-search.js
 */
(function(global) {
  'use strict';

  // Configuration
  var CONFIG = {
    debounceMs: 150,
    maxResultsPerType: 999,  // Effectively unlimited per category
    maxTotalResults: 200,
    recentSearchesKey: 'global-recent-searches',
    maxRecentSearches: 5,
    suggestions: ['causal inference', 'experimentation', 'pricing', 'machine learning', 'A/B testing'],
    enableSemanticSearch: true,
    semanticSearchOnFocus: true,  // Start loading model on focus
    workerPath: '/js/search/search-worker.js',
    // LLM Enhancement Settings
    llmSearchKey: 'llm-search-enabled',
    llmExpandTimeout: 3000,    // 3s timeout for query expansion
    llmExplainTimeout: 10000   // 10s timeout for explanations
  };

  // Type display configuration
  var TYPE_CONFIG = {
    package: { label: 'Package', icon: 'pkg', color: '#0066cc', href: '/packages/' },
    dataset: { label: 'Dataset', icon: 'data', color: '#2e7d32', href: '/datasets/' },
    resource: { label: 'Resource', icon: 'book', color: '#7b1fa2', href: '/resources/' },
    talk: { label: 'Talk', icon: 'mic', color: '#e65100', href: '/talks/' },
    career: { label: 'Career', icon: 'job', color: '#c2185b', href: '/career/' },
    community: { label: 'Community', icon: 'people', color: '#00796b', href: '/community/' },
    roadmap: { label: 'Roadmap', icon: 'map', color: '#1565c0', href: '/start/' },
    paper: { label: 'Paper', icon: 'doc', color: '#5c6bc0', href: '/papers/' },
    book: { label: 'Book', icon: 'book', color: '#8d6e63', href: '/books/' },
    domain: { label: 'Domain', icon: 'category', color: '#607d8b', href: '/learning/' }
  };

  /**
   * UnifiedSearch class
   */
  function UnifiedSearch() {
    // Worker
    this.worker = null;
    this.workerReady = false;
    this.pendingSearches = new Map();
    this.pendingKeywordResults = new Map();  // Track keyword results for progressive rendering
    this.searchId = 0;

    // State
    this.isIndexLoaded = false;
    this.isEmbeddingsLoaded = false;
    this.embeddingsLoadingStarted = false;
    this.isModelLoaded = false;
    this.isModelLoading = false;
    this.searchIndex = null;

    // Global search UI state
    this.modal = null;
    this.backdrop = null;
    this.input = null;
    this.resultsContainer = null;
    this.emptyState = null;
    this.hint = null;
    this.triggers = null;
    this.isOpen = false;
    this.selectedIndex = -1;
    this.currentResults = [];
    this.flatResults = [];
    this.debounceTimer = null;
    this.currentSortOrder = 'relevance';  // 'relevance' | 'alphabetical' | 'type'

    // Filter state for faceted search
    this.activeFilters = {
      types: [],      // e.g., ['paper', 'package']
      topics: [],     // e.g., ['Experimentation', 'Causal Inference']
      years: [],      // e.g., [2023, 2024]
      yearRange: null // e.g., { min: 2020, max: 2024 }
    };
    this.facetCounts = null;  // Computed from search results

    // Parsed query state (for advanced query syntax)
    this.parsedQuery = null;  // Result of QueryParser.parse()
    this.rawQuery = '';       // Original user input

    // Related items state
    this.relatedItemsData = {};
    this.relatedItemsLoaded = false;
    this.relatedItemsLoading = false;
    this.relatedItemsPromise = null;

    // Page search instances
    this.pageSearchInstances = [];

    // LLM Enhancement state
    this.llmEnabled = false;
    this.llmToggleBtn = null;
    this.llmEndpoint = null;
    this.llmExpandedTermsContainer = null;
    this.llmExplanationPanel = null;
    this.isExpandingQuery = false;
    this.expandedTerms = [];
    this.explanationAbortController = null;
  }

  /**
   * Initialize the search system
   */
  UnifiedSearch.prototype.init = function() {
    var self = this;

    // Inject preload hints for faster resource loading
    this.injectPreloadHints();

    // Initialize worker
    this.initWorker();

    // Load only the keyword search index on init (lightweight)
    // Embeddings are lazy-loaded when search modal is opened
    this.loadSearchIndex();

    // Initialize global search UI
    this.initGlobalSearchUI();

    // Initialize page search if applicable
    this.initPageSearch();

    console.log('[UnifiedSearch] Initialized');
  };

  /**
   * Inject preload/prefetch hints for critical resources
   */
  UnifiedSearch.prototype.injectPreloadHints = function() {
    // Preload the search index (needed immediately on modal open)
    var indexLink = document.createElement('link');
    indexLink.rel = 'preload';
    indexLink.href = '/embeddings/search-index.json';
    indexLink.as = 'fetch';
    indexLink.crossOrigin = 'anonymous';
    document.head.appendChild(indexLink);

    // Prefetch embeddings during idle time (needed for semantic search)
    if ('requestIdleCallback' in window) {
      requestIdleCallback(function() {
        var embeddingsLink = document.createElement('link');
        embeddingsLink.rel = 'prefetch';
        embeddingsLink.href = '/embeddings/search-embeddings-q8.bin';
        embeddingsLink.as = 'fetch';
        embeddingsLink.crossOrigin = 'anonymous';
        document.head.appendChild(embeddingsLink);

        var metadataLink = document.createElement('link');
        metadataLink.rel = 'prefetch';
        metadataLink.href = '/embeddings/search-metadata.json';
        metadataLink.as = 'fetch';
        metadataLink.crossOrigin = 'anonymous';
        document.head.appendChild(metadataLink);
      }, { timeout: 3000 });
    }
  };

  /**
   * Initialize Web Worker
   */
  UnifiedSearch.prototype.initWorker = function() {
    var self = this;

    try {
      this.worker = new Worker(CONFIG.workerPath);

      this.worker.onmessage = function(event) {
        self.handleWorkerMessage(event.data);
      };

      this.worker.onerror = function(error) {
        console.error('[UnifiedSearch] Worker error:', error);
        self.workerReady = false;
      };
    } catch (e) {
      console.warn('[UnifiedSearch] Web Worker not supported, using fallback');
      this.workerReady = false;
    }
  };

  /**
   * Handle messages from worker
   */
  UnifiedSearch.prototype.handleWorkerMessage = function(message) {
    var type = message.type;
    console.log('[UnifiedSearch] Worker message:', type, message.payload);

    switch (type) {
      case 'WORKER_READY':
        this.workerReady = true;
        this.sendSynonymsToWorker();
        // Send index if it was already loaded before worker was ready
        if (this.searchIndex && !this.isIndexLoaded) {
          this.worker.postMessage({
            type: 'LOAD_INDEX',
            payload: { indexData: this.searchIndex }
          });
        }
        break;

      case 'INDEX_LOADED':
        this.isIndexLoaded = message.payload.success;
        if (this.isIndexLoaded) {
          console.log('[UnifiedSearch] Index loaded:', message.payload.count, 'documents');
        } else {
          console.error('[UnifiedSearch] Index load FAILED:', message.payload.error);
        }
        break;

      case 'EMBEDDINGS_LOADED':
        this.isEmbeddingsLoaded = message.payload.success;
        if (this.isEmbeddingsLoaded) {
          console.log('[UnifiedSearch] Embeddings loaded:', message.payload.count, 'vectors');
        }
        break;

      case 'MODEL_LOADING':
        this.isModelLoading = true;
        this.updateSearchStatus('Loading AI search...');
        break;

      case 'MODEL_LOADED':
        this.isModelLoading = false;
        this.isModelLoaded = message.payload.success;
        if (this.isModelLoaded) {
          console.log('[UnifiedSearch] Transformers.js model loaded');
          this.updateSearchStatus('AI search ready');
        }
        break;

      case 'KEYWORD_RESULTS':
        this.handleKeywordResults(message.id, message.payload);
        break;

      case 'SEARCH_RESULTS':
        this.handleSearchResults(message.id, message.payload);
        break;
    }
  };

  /**
   * Send synonyms to worker
   */
  UnifiedSearch.prototype.sendSynonymsToWorker = function() {
    if (!this.workerReady || !global.SearchSynonyms) return;

    this.worker.postMessage({
      type: 'LOAD_SYNONYMS',
      payload: { synonyms: global.SearchSynonyms.SYNONYMS }
    });
  };

  /**
   * Load search index only (lightweight, called on init)
   */
  UnifiedSearch.prototype.loadSearchIndex = function() {
    var self = this;

    // Load search index
    fetch('/embeddings/search-index.json')
      .then(function(response) {
        if (!response.ok) throw new Error('Failed to load search index');
        return response.json();
      })
      .then(function(data) {
        console.log('[UnifiedSearch] Fetched search index:', data.documents ? data.documents.length : 0, 'documents');
        // Wrap with config (same format as fallback)
        var indexData = {
          version: data.version || 1,
          documents: data.documents,
          config: {
            fields: ['name', 'description', 'category', 'tags', 'best_for'],
            storeFields: ['name', 'description', 'category', 'url', 'type', 'tags', 'best_for'],
            searchOptions: {
              boost: { name: 3, tags: 2, best_for: 1.2, description: 1, category: 0.8 },
              fuzzy: 0.2,
              prefix: true
            }
          }
        };
        self.searchIndex = indexData;
        if (self.workerReady) {
          console.log('[UnifiedSearch] Sending LOAD_INDEX to worker');
          self.worker.postMessage({
            type: 'LOAD_INDEX',
            payload: { indexData: indexData }
          });
        } else {
          console.log('[UnifiedSearch] Worker not ready yet, storing index for later');
        }
      })
      .catch(function(error) {
        console.warn('[UnifiedSearch] Failed to load search index:', error);
        // Fallback to inline data
        self.loadFallbackIndex();
      });
  };

  /**
   * Load search assets (index and embeddings) - legacy, kept for compatibility
   */
  UnifiedSearch.prototype.loadSearchAssets = function() {
    this.loadSearchIndex();
    this.loadEmbeddings();
  };

  /**
   * Load fallback index from inline data
   */
  UnifiedSearch.prototype.loadFallbackIndex = function() {
    var self = this;
    var dataEl = document.getElementById('global-search-data');

    if (dataEl) {
      try {
        var data = JSON.parse(dataEl.textContent);
        var indexData = {
          version: 1,
          documents: data,
          config: {
            fields: ['name', 'description', 'category', 'tags', 'best_for'],
            storeFields: ['name', 'description', 'category', 'url', 'type', 'tags', 'best_for'],
            searchOptions: {
              boost: { name: 3, tags: 2, best_for: 1.2, description: 1, category: 0.8 },
              fuzzy: 0.2,
              prefix: true
            }
          }
        };

        if (this.workerReady) {
          this.worker.postMessage({
            type: 'LOAD_INDEX',
            payload: { indexData: indexData }
          });
        }
      } catch (e) {
        console.error('[UnifiedSearch] Failed to parse fallback index:', e);
      }
    }
  };

  /**
   * Load embeddings with caching
   */
  UnifiedSearch.prototype.loadEmbeddings = function() {
    var self = this;

    // Try IndexedDB cache first
    if (global.SearchCache) {
      global.SearchCache.getEmbeddings().then(function(cached) {
        if (cached) {
          console.log('[UnifiedSearch] Using cached embeddings (quantized:', cached.quantized, ')');
          self.sendEmbeddingsToWorker(cached.metadata, cached.embeddings, cached.quantized);
          return;
        }
        self.fetchEmbeddings();
      });
    } else {
      this.fetchEmbeddings();
    }
  };

  /**
   * Fetch embeddings from server (tries quantized first, then full, then legacy)
   */
  UnifiedSearch.prototype.fetchEmbeddings = function() {
    var self = this;

    // First, fetch metadata (always needed)
    fetch('/embeddings/search-metadata.json')
      .then(function(r) {
        if (!r.ok) throw new Error('Failed to load metadata');
        return r.json();
      })
      .then(function(metadata) {
        // Try quantized embeddings first (smaller, ~500KB vs 1.9MB)
        return fetch('/embeddings/search-embeddings-q8.bin')
          .then(function(r) {
            if (!r.ok) throw new Error('Quantized not available');
            return r.arrayBuffer();
          })
          .then(function(buffer) {
            console.log('[UnifiedSearch] Using quantized embeddings');
            // Cache for next time
            if (global.SearchCache) {
              global.SearchCache.setEmbeddings(metadata, buffer, true);  // true = quantized
            }
            self.sendEmbeddingsToWorker(metadata, buffer, true);  // true = quantized
          })
          .catch(function() {
            // Fall back to full Float32 embeddings
            console.log('[UnifiedSearch] Falling back to Float32 embeddings');
            return fetch('/embeddings/search-embeddings.bin')
              .then(function(r) {
                if (!r.ok) throw new Error('Failed to load embeddings');
                return r.arrayBuffer();
              })
              .then(function(buffer) {
                if (global.SearchCache) {
                  global.SearchCache.setEmbeddings(metadata, buffer, false);
                }
                self.sendEmbeddingsToWorker(metadata, buffer, false);
              });
          });
      })
      .catch(function(error) {
        console.warn('[UnifiedSearch] Failed to load embeddings:', error);
        // Fall back to legacy JSON format
        self.loadLegacyEmbeddings();
      });
  };

  /**
   * Load legacy JSON embeddings
   */
  UnifiedSearch.prototype.loadLegacyEmbeddings = function() {
    var self = this;

    fetch('/embeddings/search-embeddings.json')
      .then(function(r) {
        if (!r.ok) throw new Error('Failed to load legacy embeddings');
        return r.json();
      })
      .then(function(data) {
        // Convert to binary format
        var buffer = new ArrayBuffer(data.count * data.dimensions * 4);
        var view = new Float32Array(buffer);
        var offset = 0;

        data.items.forEach(function(item) {
          item.embedding.forEach(function(val) {
            view[offset++] = val;
          });
        });

        var metadata = {
          version: 1,
          model: data.model,
          dimensions: data.dimensions,
          count: data.count,
          items: data.items.map(function(item) {
            return {
              id: item.id,
              type: item.type,
              name: item.name,
              description: item.description,
              category: item.category,
              url: item.url
            };
          })
        };

        self.sendEmbeddingsToWorker(metadata, buffer);
      })
      .catch(function(error) {
        console.warn('[UnifiedSearch] Failed to load legacy embeddings:', error);
      });
  };

  /**
   * Send embeddings to worker
   * @param {Object} metadata - Embeddings metadata
   * @param {ArrayBuffer} buffer - Binary embeddings data
   * @param {boolean} quantized - Whether the buffer contains quantized Int8 data
   */
  UnifiedSearch.prototype.sendEmbeddingsToWorker = function(metadata, buffer, quantized) {
    if (!this.workerReady) return;

    this.worker.postMessage({
      type: 'LOAD_EMBEDDINGS',
      payload: {
        metadata: metadata,
        embeddingsBuffer: buffer,
        quantized: !!quantized
      }
    }, [buffer]);  // Transfer buffer ownership
  };

  /**
   * Start loading Transformers.js model
   */
  UnifiedSearch.prototype.loadModel = function() {
    if (!this.workerReady || this.isModelLoaded || this.isModelLoading) return;

    this.worker.postMessage({ type: 'LOAD_MODEL' });
  };

  /**
   * Wait for index to be loaded
   */
  UnifiedSearch.prototype.waitForIndex = function(timeout) {
    var self = this;
    timeout = timeout || 5000;

    return new Promise(function(resolve, reject) {
      if (self.isIndexLoaded) {
        resolve();
        return;
      }

      var elapsed = 0;
      var interval = 100;
      var check = setInterval(function() {
        elapsed += interval;
        if (self.isIndexLoaded) {
          clearInterval(check);
          resolve();
        } else if (elapsed >= timeout) {
          clearInterval(check);
          reject(new Error('Index load timeout'));
        }
      }, interval);
    });
  };

  /**
   * Perform search (internal) - uses progressive search for faster results
   */
  UnifiedSearch.prototype._doSearch = function(query, options) {
    var self = this;
    var useProgressive = options.progressive !== false;
    var canUseSemantic = self.isEmbeddingsLoaded && self.isModelLoaded;

    return new Promise(function(resolve) {
      var id = ++self.searchId;
      var hasResolved = false;

      // For progressive search, we handle multiple responses
      self.pendingSearches.set(id, function(result) {
        if (hasResolved) {
          // This is a follow-up result (e.g., hybrid after keyword)
          // Re-render with updated results
          if (self.isOpen && result.results && result.results.length > 0) {
            self.currentResults = result.results.slice(0, CONFIG.maxTotalResults);
            self.renderGlobalResults(self.currentResults, query, result.isPartial);
          }
        } else {
          hasResolved = true;
          resolve(result);
        }
      });

      self.worker.postMessage({
        type: useProgressive ? 'SEARCH_PROGRESSIVE' : 'SEARCH',
        id: id,
        payload: {
          query: query,
          topK: options.topK || CONFIG.maxTotalResults,
          semantic: options.semantic !== false && canUseSemantic
        }
      });

      // Timeout after 5 seconds
      setTimeout(function() {
        if (self.pendingSearches.has(id)) {
          self.pendingSearches.delete(id);
          self.pendingKeywordResults.delete(id);
          if (!hasResolved) {
            resolve({ results: [], isPartial: false, mode: 'timeout' });
          }
        }
      }, 5000);
    });
  };

  /**
   * Perform search
   */
  UnifiedSearch.prototype.search = function(query, options) {
    var self = this;
    options = options || {};

    // Worker must be ready
    if (!this.workerReady) {
      return Promise.resolve([]);
    }

    // If index not loaded yet, wait for it
    if (!this.isIndexLoaded) {
      return this.waitForIndex(3000).then(function() {
        return self._doSearch(query, options);
      }).catch(function() {
        console.warn('[UnifiedSearch] Index not loaded after timeout');
        return [];
      });
    }

    return this._doSearch(query, options);
  };

  /**
   * Handle keyword results from worker (progressive search - fast results first)
   */
  UnifiedSearch.prototype.handleKeywordResults = function(id, payload) {
    // Store keyword results for this search
    this.pendingKeywordResults.set(id, {
      results: payload.results,
      isPartial: payload.isPartial
    });

    // Resolve immediately with keyword results (marked as partial if semantic is coming)
    var resolve = this.pendingSearches.get(id);
    if (resolve) {
      // Don't delete from pendingSearches yet - we may get SEARCH_RESULTS later
      resolve({
        results: payload.results,
        isPartial: payload.isPartial,
        mode: 'keyword'
      });
    }
  };

  /**
   * Handle search results from worker (final results - may replace keyword results)
   */
  UnifiedSearch.prototype.handleSearchResults = function(id, payload) {
    var resolve = this.pendingSearches.get(id);
    if (resolve) {
      this.pendingSearches.delete(id);
      this.pendingKeywordResults.delete(id);
      resolve({
        results: payload.results,
        isPartial: false,
        mode: payload.mode
      });
    }
  };

  /**
   * Update search status in UI
   */
  UnifiedSearch.prototype.updateSearchStatus = function(status) {
    var statusEl = document.getElementById('search-status');
    if (statusEl) {
      statusEl.textContent = status;
      statusEl.style.display = status ? 'block' : 'none';
    }
  };

  // ============================================
  // Related Items / Discovery
  // ============================================

  /**
   * Load related items data
   */
  UnifiedSearch.prototype.loadRelatedItems = function() {
    var self = this;

    if (this.relatedItemsLoaded || this.relatedItemsLoading) {
      return this.relatedItemsPromise;
    }

    this.relatedItemsLoading = true;
    this.relatedItemsPromise = fetch('/embeddings/related-items.json')
      .then(function(response) {
        if (!response.ok) throw new Error('Failed to load related items');
        return response.json();
      })
      .then(function(data) {
        self.relatedItemsData = data.items || {};
        self.relatedItemsLoaded = true;
        self.relatedItemsLoading = false;
        console.log('[UnifiedSearch] Related items loaded:', Object.keys(self.relatedItemsData).length, 'items');
        return self.relatedItemsData;
      })
      .catch(function(error) {
        console.warn('[UnifiedSearch] Failed to load related items:', error);
        self.relatedItemsLoading = false;
        self.relatedItemsData = {};
        return {};
      });

    return this.relatedItemsPromise;
  };

  /**
   * Get related items for a given item ID
   * @param {string} itemId - The item ID to find related items for
   * @returns {Promise<Array>} - Array of related items with full details
   */
  UnifiedSearch.prototype.getRelatedItems = function(itemId) {
    var self = this;

    return this.loadRelatedItems().then(function() {
      var relatedIds = self.relatedItemsData[itemId] || [];

      if (relatedIds.length === 0) {
        return [];
      }

      // Look up full item details from the search index
      // Related items are stored as {id, score}
      var results = [];
      relatedIds.forEach(function(rel) {
        // Find the item in our search index documents
        var item = self.findItemById(rel.id);
        if (item) {
          results.push({
            id: rel.id,
            name: item.name,
            description: item.description,
            type: item.type,
            category: item.category,
            url: item.url,
            score: rel.score
          });
        }
      });

      return results;
    });
  };

  /**
   * Find an item by ID in the search index
   * @param {string} itemId - The item ID to find
   * @returns {Object|null} - The item or null if not found
   */
  UnifiedSearch.prototype.findItemById = function(itemId) {
    if (!this.searchIndex || !this.searchIndex.documents) {
      return null;
    }

    for (var i = 0; i < this.searchIndex.documents.length; i++) {
      if (this.searchIndex.documents[i].id === itemId) {
        return this.searchIndex.documents[i];
      }
    }

    return null;
  };

  /**
   * Show related items in search results (triggered by "More like this" button)
   * @param {string} itemId - The item ID to show related items for
   * @param {string} itemName - The name of the source item (for display)
   */
  UnifiedSearch.prototype.showRelatedItems = function(itemId, itemName) {
    var self = this;

    this.showLoading();

    this.getRelatedItems(itemId).then(function(related) {
      self.hideLoading();

      if (related.length === 0) {
        self.showEmpty();
        return;
      }

      // Update the input to show what we're viewing
      if (self.input) {
        self.input.value = 'Related to: ' + itemName;
      }

      // Render results
      self.currentResults = related;
      self.renderGlobalResults(related, '', false);
    });
  };

  // ============================================
  // Global Search UI
  // ============================================

  /**
   * Initialize global search modal UI
   */
  UnifiedSearch.prototype.initGlobalSearchUI = function() {
    var self = this;

    this.modal = document.getElementById('global-search-modal');
    if (!this.modal) return;

    this.backdrop = this.modal.querySelector('.global-search-backdrop');
    this.input = document.getElementById('global-search-input');
    this.resultsContainer = document.getElementById('global-search-results');
    this.filtersContainer = document.getElementById('global-search-filters');
    this.emptyState = document.getElementById('global-search-empty');
    this.loadingState = document.getElementById('global-search-loading');
    this.hint = document.getElementById('global-search-hint');
    this.triggers = document.querySelectorAll('.global-search-trigger');
    this.currentTypeFilter = 'all';  // Filter state

    // Create preview panel for hover previews (desktop only)
    this.createPreviewPanel();

    // Initialize LLM toggle
    this.initLLMToggle();

    this.bindGlobalSearchEvents();
  };

  /**
   * Create preview panel for hover previews
   */
  UnifiedSearch.prototype.createPreviewPanel = function() {
    // Only create on desktop
    if (window.innerWidth < 900) return;

    var container = this.modal.querySelector('.global-search-container');
    if (!container) return;

    this.previewPanel = document.createElement('div');
    this.previewPanel.className = 'global-search-preview';
    this.previewPanel.style.display = 'none';
    container.appendChild(this.previewPanel);
  };

  /**
   * Show preview for a result
   */
  UnifiedSearch.prototype.showPreview = function(result) {
    if (!this.previewPanel || window.innerWidth < 900) return;

    var typeConfig = TYPE_CONFIG[result.type] || { label: result.type, icon: 'file', color: '#666' };

    var html = '<div class="preview-header">';
    html += '<span class="preview-type-badge" style="background-color:' + typeConfig.color + '">' + typeConfig.label + '</span>';
    html += '<h3 class="preview-title">' + escapeHtml(result.name) + '</h3>';
    html += '</div>';

    html += '<div class="preview-body">';

    // Category
    if (result.category) {
      html += '<div class="preview-field">';
      html += '<span class="preview-label">Category</span>';
      html += '<span class="preview-value">' + escapeHtml(result.category) + '</span>';
      html += '</div>';
    }

    // Full description
    if (result.description) {
      html += '<div class="preview-field">';
      html += '<span class="preview-label">Description</span>';
      html += '<p class="preview-description">' + escapeHtml(result.description) + '</p>';
      html += '</div>';
    }

    // Tags
    if (result.tags) {
      var tagsArr = typeof result.tags === 'string' ? result.tags.split(',').map(function(t) { return t.trim(); }).filter(Boolean) : result.tags;
      if (tagsArr.length > 0) {
        html += '<div class="preview-field">';
        html += '<span class="preview-label">Tags</span>';
        html += '<div class="preview-tags">';
        tagsArr.forEach(function(tag) {
          html += '<span class="preview-tag">' + escapeHtml(tag) + '</span>';
        });
        html += '</div>';
        html += '</div>';
      }
    }

    // Best for
    if (result.best_for) {
      html += '<div class="preview-field">';
      html += '<span class="preview-label">Best for</span>';
      html += '<p class="preview-best-for">' + escapeHtml(result.best_for) + '</p>';
      html += '</div>';
    }

    html += '</div>';

    html += '<div class="preview-footer">';
    html += '<span class="preview-url">' + escapeHtml(result.url) + '</span>';
    html += '</div>';

    this.previewPanel.innerHTML = html;
    this.previewPanel.style.display = 'block';
  };

  /**
   * Hide preview panel
   */
  UnifiedSearch.prototype.hidePreview = function() {
    if (this.previewPanel) {
      this.previewPanel.style.display = 'none';
    }
  };

  /**
   * Bind global search events
   */
  UnifiedSearch.prototype.bindGlobalSearchEvents = function() {
    var self = this;

    // Keyboard shortcut (Cmd/Ctrl + K)
    document.addEventListener('keydown', function(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        self.toggleModal();
      }
      if (e.key === 'Escape' && self.isOpen) {
        self.closeModal();
      }
    });

    // Trigger buttons
    this.triggers.forEach(function(trigger) {
      trigger.addEventListener('click', function(e) {
        e.preventDefault();
        self.openModal();
      });
    });

    // Backdrop click
    if (this.backdrop) {
      this.backdrop.addEventListener('click', function() {
        self.closeModal();
      });
    }

    // Syntax help button
    this.syntaxHelpBtn = document.getElementById('search-syntax-help');
    this.syntaxTooltip = document.getElementById('search-syntax-tooltip');
    if (this.syntaxHelpBtn && this.syntaxTooltip) {
      this.syntaxHelpBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        self.toggleSyntaxTooltip();
      });

      // Close tooltip when clicking outside
      document.addEventListener('click', function(e) {
        if (self.syntaxTooltip && self.syntaxTooltip.style.display !== 'none') {
          if (!self.syntaxTooltip.contains(e.target) && e.target !== self.syntaxHelpBtn) {
            self.hideSyntaxTooltip();
          }
        }
      });
    }

    // Search input
    if (this.input) {
      this.input.addEventListener('input', function() {
        clearTimeout(self.debounceTimer);
        self.debounceTimer = setTimeout(function() {
          self.performGlobalSearch();
        }, CONFIG.debounceMs);
      });

      this.input.addEventListener('focus', function() {
        // Start loading model on focus
        if (CONFIG.semanticSearchOnFocus) {
          self.loadModel();
        }
      });

      this.input.addEventListener('keydown', function(e) {
        self.handleKeyNavigation(e);
      });
    }

    // Result clicks
    if (this.resultsContainer) {
      this.resultsContainer.addEventListener('click', function(e) {
        // Handle "Explain" button click (LLM feature)
        var explainBtn = e.target.closest('.result-explain-btn');
        if (explainBtn) {
          e.preventDefault();
          e.stopPropagation();
          var index = parseInt(explainBtn.getAttribute('data-index'), 10);
          if (!isNaN(index) && self.flatResults && self.flatResults[index]) {
            self.explainResult(self.flatResults[index], self.rawQuery);
          }
          return;
        }

        // Handle "More like this" button click
        var moreLikeBtn = e.target.closest('.more-like-this-btn');
        if (moreLikeBtn) {
          e.preventDefault();
          e.stopPropagation();
          var itemId = moreLikeBtn.getAttribute('data-item-id');
          var itemName = moreLikeBtn.getAttribute('data-item-name');
          if (itemId && itemName) {
            self.showRelatedItems(itemId, itemName);
          }
          return;
        }

        var item = e.target.closest('.result-item');
        if (item) {
          self.closeModal();
        }
      });

      // Hover previews (desktop only)
      this.resultsContainer.addEventListener('mouseenter', function(e) {
        var item = e.target.closest('.result-item');
        if (item && self.flatResults) {
          var index = parseInt(item.getAttribute('data-index'), 10);
          if (!isNaN(index) && self.flatResults[index]) {
            self.showPreview(self.flatResults[index]);
          }
        }
      }, true);

      this.resultsContainer.addEventListener('mouseleave', function(e) {
        // Only hide if leaving to outside the results container
        var relatedTarget = e.relatedTarget;
        if (!relatedTarget || !self.resultsContainer.contains(relatedTarget)) {
          self.hidePreview();
        }
      }, true);

      // Handle mouse move between items
      this.resultsContainer.addEventListener('mouseover', function(e) {
        var item = e.target.closest('.result-item');
        if (item && self.flatResults) {
          var index = parseInt(item.getAttribute('data-index'), 10);
          if (!isNaN(index) && self.flatResults[index]) {
            self.showPreview(self.flatResults[index]);
          }
        }
      });
    }
  };

  /**
   * Toggle modal
   */
  UnifiedSearch.prototype.toggleModal = function() {
    this.isOpen ? this.closeModal() : this.openModal();
  };

  /**
   * Open modal
   */
  UnifiedSearch.prototype.openModal = function() {
    if (!this.modal) return;
    this.modal.style.display = 'flex';
    this.isOpen = true;
    this.selectedIndex = -1;
    this.flatResults = [];
    this.input.value = '';
    var self = this;
    setTimeout(function() { self.input.focus(); }, 50);
    this.showHint();
    document.body.style.overflow = 'hidden';

    // Lazy-load embeddings on first modal open
    if (!this.isEmbeddingsLoaded && !this.embeddingsLoadingStarted) {
      this.embeddingsLoadingStarted = true;
      this.loadEmbeddings();
    }

    // Start loading model
    if (CONFIG.semanticSearchOnFocus) {
      this.loadModel();
    }
  };

  /**
   * Close modal
   */
  UnifiedSearch.prototype.closeModal = function() {
    if (!this.modal) return;
    this.modal.style.display = 'none';
    this.isOpen = false;
    document.body.style.overflow = '';
    this.hidePreview();
  };

  /**
   * Perform global search
   */
  UnifiedSearch.prototype.performGlobalSearch = function() {
    var self = this;
    var query = this.input.value.trim();

    if (!query || query.length < 2) {
      this.showHint();
      this.currentResults = [];
      this.flatResults = [];
      this.parsedQuery = null;
      this.rawQuery = '';
      this.hideFilterChips();
      this.clearExpandedTerms();
      this.hideExplanationPanel();
      return;
    }

    // Store raw query
    this.rawQuery = query;

    // Clear previous expanded terms
    this.clearExpandedTerms();
    this.hideExplanationPanel();

    // Parse query for advanced syntax (phrases, filters, negations)
    if (typeof QueryParser !== 'undefined') {
      this.parsedQuery = QueryParser.parse(query);
      console.log('[UnifiedSearch] Parsed query:', this.parsedQuery);
    } else {
      this.parsedQuery = null;
    }

    // Render active filter chips
    this.renderFilterChips();

    // Save to recent searches
    this.addRecentSearch(query);

    // Show loading state
    this.showLoading();

    // Use cleanQuery for search (strips field filters, keeps terms + phrases)
    var searchQuery = this.parsedQuery ? this.parsedQuery.cleanQuery : query;
    if (!searchQuery || searchQuery.length < 1) {
      // Only filters, no search terms - use original query
      searchQuery = query;
    }

    // Helper function to execute search
    function executeSearch(enhancedQuery) {
      self.search(enhancedQuery, { topK: CONFIG.maxTotalResults * 2 })
        .then(function(result) {
          self.hideLoading();

          // Handle progressive result format
          var results = result.results || result;
          var isPartial = result.isPartial || false;

          // Apply query parser filters (phrases, field filters, negations)
          if (self.parsedQuery && typeof QueryParser !== 'undefined') {
            results = QueryParser.applyFilters(results, self.parsedQuery);
          }

          self.currentResults = results.slice(0, CONFIG.maxTotalResults);

          if (self.currentResults.length === 0) {
            self.showEmpty();
            self.flatResults = [];
          } else {
            self.renderGlobalResults(self.currentResults, query, isPartial);
          }
        })
        .catch(function(error) {
          console.error('[UnifiedSearch] Search failed:', error);
          self.hideLoading();
          self.showEmpty();
          self.flatResults = [];
        });
    }

    // If LLM is enabled, expand the query first, then search
    if (this.llmEnabled && this.llmEndpoint) {
      this.expandQueryWithLLM(searchQuery)
        .then(function(expandedTerms) {
          // Combine original query with expanded terms
          var enhancedQuery = expandedTerms.length > 0
            ? searchQuery + ' ' + expandedTerms.join(' ')
            : searchQuery;
          console.log('[UnifiedSearch] LLM enhanced query:', enhancedQuery);
          executeSearch(enhancedQuery);
        });
    } else {
      // Standard search without LLM
      executeSearch(searchQuery);
    }
  };

  /**
   * Render global search results
   * @param {Array} results - Search results
   * @param {string} query - Search query
   * @param {boolean} isPartial - Whether more results are coming (AI refining)
   */
  UnifiedSearch.prototype.renderGlobalResults = function(results, query, isPartial) {
    var self = this;
    this.hint.style.display = 'none';
    this.emptyState.style.display = 'none';

    // Count by type for filter chips
    var typeCounts = {};
    results.forEach(function(result) {
      typeCounts[result.type] = (typeCounts[result.type] || 0) + 1;
    });

    // Render type filter chips (with refining indicator if partial)
    this.renderTypeFilters(typeCounts, results.length, isPartial);

    // Render sort controls
    this.renderSortControls();

    // Apply facet filters (topics, years)
    var filteredResults = this.applyFilters(results);

    // Apply sort order to filtered results
    var sortedResults = this.sortResults(filteredResults, this.currentSortOrder);

    // Group sorted results by type
    var grouped = {};
    sortedResults.forEach(function(result) {
      var type = result.type;
      if (!grouped[type]) grouped[type] = [];
      grouped[type].push(result);
    });

    // Filter results if a type is selected
    var filteredGrouped = grouped;
    if (this.currentTypeFilter !== 'all') {
      filteredGrouped = {};
      if (grouped[this.currentTypeFilter]) {
        filteredGrouped[this.currentTypeFilter] = grouped[this.currentTypeFilter];
      }
    }

    var html = '';
    this.flatResults = [];
    var globalIndex = 0;

    // Order of types
    var typeOrder = ['paper', 'package', 'dataset', 'resource', 'book', 'talk', 'career', 'community', 'roadmap', 'domain'];

    typeOrder.forEach(function(type) {
      if (!filteredGrouped[type]) return;

      var typeConfig = TYPE_CONFIG[type] || { label: type, icon: 'file', color: '#666' };

      html += '<div class="result-group">';
      html += '<div class="result-group-header">';
      html += '<span class="result-type-label">' + typeConfig.label + 's</span>';
      html += '</div>';

      filteredGrouped[type].forEach(function(result) {
        var isSelected = globalIndex === self.selectedIndex;
        self.flatResults.push(result);

        html += '<a href="' + escapeHtml(result.url) + '" ';
        html += 'class="result-item' + (isSelected ? ' selected' : '') + '" ';
        html += 'data-index="' + globalIndex + '" ';
        html += 'target="_blank" rel="noopener">';
        html += '<div class="result-content">';
        html += '<span class="result-name">' + highlightTextEnhanced(result.name, query) + '</span>';
        // Use contextual snippets for descriptions
        var snippet = generateSnippet(result.description, query, 180);
        html += '<span class="result-description">' + highlightTextEnhanced(snippet, query) + '</span>';
        // Show tags if available
        if (result.tags) {
          var tagsArr = typeof result.tags === 'string' ? result.tags.split(',').map(function(t) { return t.trim(); }) : result.tags;
          if (tagsArr.length > 0) {
            html += '<span class="result-tags">' + escapeHtml(tagsArr.slice(0, 3).join(' · ')) + '</span>';
          }
        }
        html += '</div>';
        html += '<div class="result-meta">';
        html += '<span class="result-type-badge" style="background-color:' + typeConfig.color + '">' + typeConfig.label + '</span>';
        html += '<span class="result-category">' + escapeHtml(result.category) + '</span>';
        html += '</div>';
        html += '<button class="result-explain-btn" data-index="' + globalIndex + '" title="Explain why this result matches">';
        html += '<svg viewBox="0 0 24 24" width="12" height="12"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/></svg>';
        html += '</button>';
        html += '<button class="more-like-this-btn" data-item-id="' + escapeHtml(result.id) + '" data-item-name="' + escapeHtml(result.name) + '" title="Find similar items">';
        html += '<svg viewBox="0 0 24 24" width="14" height="14"><circle cx="12" cy="12" r="3" fill="currentColor"/><circle cx="5" cy="12" r="2" fill="currentColor" opacity="0.6"/><circle cx="19" cy="12" r="2" fill="currentColor" opacity="0.6"/></svg>';
        html += '</button>';
        html += '</a>';

        globalIndex++;
      });

      html += '</div>';
    });

    this.resultsContainer.innerHTML = html;
    this.selectedIndex = 0;
    this.updateSelection();
  };

  /**
   * Render type filter chips
   */
  UnifiedSearch.prototype.renderTypeFilters = function(typeCounts, totalCount, isPartial) {
    var self = this;
    if (!this.filtersContainer) return;

    var typeOrder = ['paper', 'package', 'dataset', 'resource', 'book', 'talk', 'career', 'community'];
    var html = '';

    // Refining indicator (when semantic search is running)
    if (isPartial) {
      html += '<span class="search-refining-indicator"><span class="refining-spinner"></span>Refining with AI...</span>';
    }

    // All filter
    var allActive = this.currentTypeFilter === 'all' ? ' active' : '';
    html += '<button class="type-filter-chip' + allActive + '" data-type="all">All (' + totalCount + ')</button>';

    // Type filters (only show types with results)
    typeOrder.forEach(function(type) {
      if (!typeCounts[type]) return;
      var typeConfig = TYPE_CONFIG[type] || { label: type };
      var isActive = self.currentTypeFilter === type ? ' active' : '';
      html += '<button class="type-filter-chip' + isActive + '" data-type="' + type + '">';
      html += typeConfig.label + 's (' + typeCounts[type] + ')';
      html += '</button>';
    });

    this.filtersContainer.innerHTML = html;
    this.filtersContainer.style.display = 'flex';

    // Bind click handlers
    this.filtersContainer.querySelectorAll('.type-filter-chip').forEach(function(chip) {
      chip.addEventListener('click', function() {
        self.currentTypeFilter = this.dataset.type;
        self.renderGlobalResults(self.currentResults, self.input.value.trim());
      });
    });

    // Render facet filters (topics, years) for papers
    this.renderFacetFilters();
  };

  /**
   * Render facet filters (topics, years) based on current results
   */
  UnifiedSearch.prototype.renderFacetFilters = function() {
    var self = this;

    // Find or create facet container
    var facetContainer = document.getElementById('global-search-facets');
    if (!facetContainer) {
      facetContainer = document.createElement('div');
      facetContainer.id = 'global-search-facets';
      facetContainer.className = 'global-search-facets';
      if (this.filtersContainer && this.filtersContainer.parentNode) {
        this.filtersContainer.parentNode.insertBefore(facetContainer, this.filtersContainer.nextSibling);
      }
    }

    // Only show facets when papers are selected or showing all
    var showFacets = this.currentTypeFilter === 'all' || this.currentTypeFilter === 'paper';
    if (!showFacets) {
      facetContainer.style.display = 'none';
      return;
    }

    // Compute facet counts from current results (before filtering)
    this.facetCounts = this.computeFacetCounts(this.currentResults);

    // Only show if there are meaningful facets
    var hasTopics = Object.keys(this.facetCounts.topics).length > 1;
    var hasYears = Object.keys(this.facetCounts.years).length > 1;

    if (!hasTopics && !hasYears) {
      facetContainer.style.display = 'none';
      return;
    }

    var html = '';

    // Topic filter dropdown
    if (hasTopics) {
      var sortedTopics = Object.entries(this.facetCounts.topics)
        .sort(function(a, b) { return b[1] - a[1]; })
        .slice(0, 10);  // Top 10 topics

      html += '<div class="facet-group">';
      html += '<label class="facet-label">Topic:</label>';
      html += '<select class="facet-select" id="facet-topic">';
      html += '<option value="">All Topics</option>';
      sortedTopics.forEach(function(entry) {
        var topic = entry[0];
        var count = entry[1];
        var selected = self.activeFilters.topics.indexOf(topic) !== -1 ? ' selected' : '';
        html += '<option value="' + escapeHtml(topic) + '"' + selected + '>' + escapeHtml(topic) + ' (' + count + ')</option>';
      });
      html += '</select>';
      html += '</div>';
    }

    // Year filter dropdown
    if (hasYears) {
      var sortedYears = Object.entries(this.facetCounts.years)
        .sort(function(a, b) { return parseInt(b[0]) - parseInt(a[0]); });  // Newest first

      html += '<div class="facet-group">';
      html += '<label class="facet-label">Year:</label>';
      html += '<select class="facet-select" id="facet-year">';
      html += '<option value="">All Years</option>';
      sortedYears.forEach(function(entry) {
        var year = entry[0];
        var count = entry[1];
        var selected = self.activeFilters.years.indexOf(parseInt(year)) !== -1 ? ' selected' : '';
        html += '<option value="' + year + '"' + selected + '>' + year + ' (' + count + ')</option>';
      });
      html += '</select>';
      html += '</div>';
    }

    // Clear filters button
    if (this.hasActiveFilters()) {
      html += '<button class="facet-clear" id="facet-clear">Clear Filters</button>';
    }

    facetContainer.innerHTML = html;
    facetContainer.style.display = 'flex';

    // Bind event handlers
    var topicSelect = document.getElementById('facet-topic');
    if (topicSelect) {
      topicSelect.addEventListener('change', function() {
        var value = this.value;
        self.activeFilters.topics = value ? [value] : [];
        self.renderGlobalResults(self.currentResults, self.input.value.trim());
      });
    }

    var yearSelect = document.getElementById('facet-year');
    if (yearSelect) {
      yearSelect.addEventListener('change', function() {
        var value = this.value;
        self.activeFilters.years = value ? [parseInt(value)] : [];
        self.renderGlobalResults(self.currentResults, self.input.value.trim());
      });
    }

    var clearBtn = document.getElementById('facet-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function() {
        self.clearFilters();
        self.renderGlobalResults(self.currentResults, self.input.value.trim());
      });
    }
  };

  /**
   * Sort results based on current sort order
   */
  UnifiedSearch.prototype.sortResults = function(results, sortOrder) {
    var sorted = results.slice();  // Clone array

    switch (sortOrder) {
      case 'alphabetical':
        sorted.sort(function(a, b) {
          return (a.name || '').localeCompare(b.name || '');
        });
        break;
      case 'type':
        var typeOrder = ['paper', 'package', 'dataset', 'resource', 'book', 'talk', 'career', 'community', 'roadmap', 'domain'];
        sorted.sort(function(a, b) {
          var aIdx = typeOrder.indexOf(a.type);
          var bIdx = typeOrder.indexOf(b.type);
          if (aIdx === -1) aIdx = 999;
          if (bIdx === -1) bIdx = 999;
          if (aIdx !== bIdx) return aIdx - bIdx;
          // Within same type, sort by relevance
          return (b.rrfScore || b.score || 0) - (a.rrfScore || a.score || 0);
        });
        break;
      case 'relevance':
      default:
        // Already sorted by relevance from worker
        break;
    }

    return sorted;
  };

  // ============================================
  // Filter Methods
  // ============================================

  /**
   * Apply active filters to results
   * @param {Array} results - Search results to filter
   * @returns {Array} - Filtered results
   */
  UnifiedSearch.prototype.applyFilters = function(results) {
    var self = this;
    var filters = this.activeFilters;

    return results.filter(function(result) {
      // Type filter
      if (filters.types.length > 0) {
        if (filters.types.indexOf(result.type) === -1) {
          return false;
        }
      }

      // Topic filter (for papers)
      if (filters.topics.length > 0) {
        var resultTopic = result.topic || '';
        if (filters.topics.indexOf(resultTopic) === -1) {
          return false;
        }
      }

      // Year filter (specific years)
      if (filters.years.length > 0) {
        var resultYear = result.year;
        if (!resultYear || filters.years.indexOf(resultYear) === -1) {
          return false;
        }
      }

      // Year range filter
      if (filters.yearRange) {
        var year = result.year;
        if (!year) return false;
        if (filters.yearRange.min && year < filters.yearRange.min) return false;
        if (filters.yearRange.max && year > filters.yearRange.max) return false;
      }

      return true;
    });
  };

  /**
   * Compute facet counts from results
   * @param {Array} results - Search results
   * @returns {Object} - Facet counts { types: {}, topics: {}, years: {} }
   */
  UnifiedSearch.prototype.computeFacetCounts = function(results) {
    var counts = {
      types: {},
      topics: {},
      years: {}
    };

    results.forEach(function(result) {
      // Count types
      var type = result.type;
      counts.types[type] = (counts.types[type] || 0) + 1;

      // Count topics (for papers)
      if (result.topic) {
        counts.topics[result.topic] = (counts.topics[result.topic] || 0) + 1;
      }

      // Count years (for papers)
      if (result.year) {
        var year = result.year;
        counts.years[year] = (counts.years[year] || 0) + 1;
      }
    });

    return counts;
  };

  /**
   * Set a filter value
   * @param {string} filterType - 'types', 'topics', 'years', or 'yearRange'
   * @param {any} value - Filter value to set
   */
  UnifiedSearch.prototype.setFilter = function(filterType, value) {
    if (filterType === 'yearRange') {
      this.activeFilters.yearRange = value;
    } else if (this.activeFilters[filterType]) {
      this.activeFilters[filterType] = Array.isArray(value) ? value : [value];
    }
  };

  /**
   * Toggle a filter value (add if missing, remove if present)
   * @param {string} filterType - 'types', 'topics', or 'years'
   * @param {any} value - Value to toggle
   */
  UnifiedSearch.prototype.toggleFilter = function(filterType, value) {
    if (!this.activeFilters[filterType]) return;

    var arr = this.activeFilters[filterType];
    var idx = arr.indexOf(value);
    if (idx === -1) {
      arr.push(value);
    } else {
      arr.splice(idx, 1);
    }
  };

  /**
   * Clear all filters
   */
  UnifiedSearch.prototype.clearFilters = function() {
    this.activeFilters = {
      types: [],
      topics: [],
      years: [],
      yearRange: null
    };
  };

  /**
   * Check if any filters are active
   * @returns {boolean}
   */
  UnifiedSearch.prototype.hasActiveFilters = function() {
    return this.activeFilters.types.length > 0 ||
           this.activeFilters.topics.length > 0 ||
           this.activeFilters.years.length > 0 ||
           this.activeFilters.yearRange !== null;
  };

  /**
   * Render sort controls
   */
  UnifiedSearch.prototype.renderSortControls = function() {
    var self = this;

    // Find or create sort container
    var sortContainer = document.getElementById('global-search-sort');
    if (!sortContainer) {
      sortContainer = document.createElement('div');
      sortContainer.id = 'global-search-sort';
      sortContainer.className = 'global-search-sort';
      // Insert after filters container
      if (this.filtersContainer && this.filtersContainer.parentNode) {
        this.filtersContainer.parentNode.insertBefore(sortContainer, this.filtersContainer.nextSibling);
      }
    }

    var html = '<span class="sort-label">Sort:</span>';
    html += '<button class="sort-btn' + (this.currentSortOrder === 'relevance' ? ' active' : '') + '" data-sort="relevance">Relevance</button>';
    html += '<button class="sort-btn' + (this.currentSortOrder === 'alphabetical' ? ' active' : '') + '" data-sort="alphabetical">A-Z</button>';
    html += '<button class="sort-btn' + (this.currentSortOrder === 'type' ? ' active' : '') + '" data-sort="type">Type</button>';

    sortContainer.innerHTML = html;
    sortContainer.style.display = 'flex';

    // Bind click handlers
    sortContainer.querySelectorAll('.sort-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        self.currentSortOrder = this.dataset.sort;
        self.renderGlobalResults(self.currentResults, self.input.value.trim());
      });
    });
  };

  /**
   * Show hint (recent searches + suggestions)
   */
  UnifiedSearch.prototype.showHint = function() {
    var self = this;
    this.emptyState.style.display = 'none';
    this.hint.style.display = 'none';
    if (this.filtersContainer) this.filtersContainer.style.display = 'none';
    var sortContainer = document.getElementById('global-search-sort');
    if (sortContainer) sortContainer.style.display = 'none';
    this.currentTypeFilter = 'all';  // Reset filter
    this.currentSortOrder = 'relevance';  // Reset sort

    var recent = this.getRecentSearches();
    var html = '';

    if (recent.length > 0) {
      html += '<div class="global-suggestions-section">';
      html += '<div class="global-suggestions-header"><span>Recent searches</span><button class="clear-recent-global">Clear</button></div>';
      html += '<div class="global-suggestion-chips">';
      recent.forEach(function(s) {
        html += '<button class="global-suggestion-chip" data-query="' + escapeHtml(s) + '">' + escapeHtml(s) + '</button>';
      });
      html += '</div></div>';
    }

    html += '<div class="global-suggestions-section">';
    html += '<div class="global-suggestions-header"><span>Try searching</span></div>';
    html += '<div class="global-suggestion-chips">';
    CONFIG.suggestions.forEach(function(s) {
      html += '<button class="global-suggestion-chip" data-query="' + escapeHtml(s) + '">' + escapeHtml(s) + '</button>';
    });
    html += '</div></div>';

    // Status indicator
    var statusText = '';
    if (this.isModelLoaded) {
      statusText = 'AI search enabled';
    } else if (this.isModelLoading) {
      statusText = 'Loading AI search...';
    }
    if (statusText) {
      html += '<div class="search-status-indicator">' + statusText + '</div>';
    }

    this.resultsContainer.innerHTML = html;

    // Bind click events
    this.resultsContainer.querySelectorAll('.global-suggestion-chip').forEach(function(chip) {
      chip.addEventListener('click', function() {
        var query = this.dataset.query;
        self.input.value = query;
        self.addRecentSearch(query);
        self.performGlobalSearch();
      });
    });

    var clearBtn = this.resultsContainer.querySelector('.clear-recent-global');
    if (clearBtn) {
      clearBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        self.clearRecentSearches();
        self.showHint();
      });
    }
  };

  /**
   * Show empty state
   */
  UnifiedSearch.prototype.showEmpty = function() {
    this.resultsContainer.innerHTML = '';
    this.hint.style.display = 'none';
    this.emptyState.style.display = 'flex';
    if (this.loadingState) this.loadingState.style.display = 'none';
    if (this.filtersContainer) this.filtersContainer.style.display = 'none';
    var sortContainer = document.getElementById('global-search-sort');
    if (sortContainer) sortContainer.style.display = 'none';
  };

  /**
   * Show loading state
   */
  UnifiedSearch.prototype.showLoading = function() {
    this.resultsContainer.innerHTML = '';
    this.hint.style.display = 'none';
    this.emptyState.style.display = 'none';
    if (this.loadingState) this.loadingState.style.display = 'flex';
  };

  /**
   * Hide loading state
   */
  UnifiedSearch.prototype.hideLoading = function() {
    if (this.loadingState) this.loadingState.style.display = 'none';
  };

  /**
   * Render filter chips based on parsed query
   */
  UnifiedSearch.prototype.renderFilterChips = function() {
    if (!this.filtersContainer || !this.parsedQuery) {
      this.hideFilterChips();
      return;
    }

    var self = this;
    var chips = [];
    var pq = this.parsedQuery;

    // Check if there are any active filters to show
    var hasFilters = pq.phrases.length > 0 ||
                     Object.keys(pq.fields).length > 0 ||
                     pq.negations.terms.length > 0 ||
                     pq.negations.phrases.length > 0;

    if (!hasFilters) {
      this.hideFilterChips();
      return;
    }

    // Phrase chips
    pq.phrases.forEach(function(phrase) {
      chips.push({
        type: 'phrase',
        label: '"' + phrase + '"',
        value: phrase,
        icon: '❝'
      });
    });

    // Field filter chips
    for (var field in pq.fields) {
      pq.fields[field].forEach(function(value) {
        chips.push({
          type: 'field',
          field: field,
          label: field + ':' + value,
          value: value,
          icon: field === 'author' ? '👤' : field === 'year' ? '📅' : field === 'type' ? '📁' : '🏷️'
        });
      });
    }

    // Negation chips
    pq.negations.terms.forEach(function(term) {
      chips.push({
        type: 'negation',
        label: '-' + term,
        value: term,
        icon: '🚫'
      });
    });

    pq.negations.phrases.forEach(function(phrase) {
      chips.push({
        type: 'negation-phrase',
        label: '-"' + phrase + '"',
        value: phrase,
        icon: '🚫'
      });
    });

    // Render chips
    var html = chips.map(function(chip, index) {
      return '<span class="filter-chip" data-type="' + chip.type + '" data-value="' + chip.value + '" data-index="' + index + '">' +
             '<span class="chip-icon">' + chip.icon + '</span>' +
             '<span class="chip-label">' + escapeHtml(chip.label) + '</span>' +
             '<button class="chip-remove" title="Remove filter">&times;</button>' +
             '</span>';
    }).join('');

    this.filtersContainer.innerHTML = html;
    this.filtersContainer.style.display = 'flex';

    // Add click handlers for chip removal
    var removeButtons = this.filtersContainer.querySelectorAll('.chip-remove');
    removeButtons.forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var chip = e.target.closest('.filter-chip');
        if (chip) {
          self.removeFilterFromQuery(chip.dataset.type, chip.dataset.value);
        }
      });
    });
  };

  /**
   * Hide filter chips
   */
  UnifiedSearch.prototype.hideFilterChips = function() {
    if (this.filtersContainer) {
      this.filtersContainer.style.display = 'none';
      this.filtersContainer.innerHTML = '';
    }
  };

  /**
   * Remove a filter from the query and re-search
   */
  UnifiedSearch.prototype.removeFilterFromQuery = function(type, value) {
    if (!this.rawQuery) return;

    var newQuery = this.rawQuery;

    if (type === 'phrase') {
      // Remove "phrase" from query
      newQuery = newQuery.replace(new RegExp('"' + this.escapeRegex(value) + '"', 'gi'), '');
    } else if (type === 'field') {
      // Remove field:value from query
      newQuery = newQuery.replace(new RegExp('\\w+:' + this.escapeRegex(value), 'gi'), '');
    } else if (type === 'negation') {
      // Remove -term from query
      newQuery = newQuery.replace(new RegExp('-' + this.escapeRegex(value), 'gi'), '');
    } else if (type === 'negation-phrase') {
      // Remove -"phrase" from query
      newQuery = newQuery.replace(new RegExp('-"' + this.escapeRegex(value) + '"', 'gi'), '');
    }

    // Clean up extra spaces
    newQuery = newQuery.replace(/\s+/g, ' ').trim();

    // Update input and re-search
    if (this.input) {
      this.input.value = newQuery;
      this.performGlobalSearch();
    }
  };

  /**
   * Escape string for use in regex
   */
  UnifiedSearch.prototype.escapeRegex = function(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  /**
   * Toggle syntax help tooltip
   */
  UnifiedSearch.prototype.toggleSyntaxTooltip = function() {
    if (!this.syntaxTooltip) return;
    if (this.syntaxTooltip.style.display === 'none') {
      this.showSyntaxTooltip();
    } else {
      this.hideSyntaxTooltip();
    }
  };

  /**
   * Show syntax help tooltip
   */
  UnifiedSearch.prototype.showSyntaxTooltip = function() {
    if (this.syntaxTooltip) {
      this.syntaxTooltip.style.display = 'block';
    }
    if (this.syntaxHelpBtn) {
      this.syntaxHelpBtn.classList.add('active');
    }
  };

  /**
   * Hide syntax help tooltip
   */
  UnifiedSearch.prototype.hideSyntaxTooltip = function() {
    if (this.syntaxTooltip) {
      this.syntaxTooltip.style.display = 'none';
    }
    if (this.syntaxHelpBtn) {
      this.syntaxHelpBtn.classList.remove('active');
    }
  };

  /**
   * Handle keyboard navigation
   */
  UnifiedSearch.prototype.handleKeyNavigation = function(e) {
    if (this.flatResults.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.selectedIndex = Math.min(this.selectedIndex + 1, this.flatResults.length - 1);
      this.updateSelection();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
      this.updateSelection();
    } else if (e.key === 'Enter' && this.selectedIndex >= 0) {
      e.preventDefault();
      var selected = this.resultsContainer.querySelector('.result-item.selected');
      if (selected) {
        window.open(selected.href, '_blank');
        this.closeModal();
      }
    }
  };

  /**
   * Update selection highlight
   */
  UnifiedSearch.prototype.updateSelection = function() {
    var self = this;
    var items = this.resultsContainer.querySelectorAll('.result-item');
    items.forEach(function(item, i) {
      if (i === self.selectedIndex) {
        item.classList.add('selected');
        item.scrollIntoView({ block: 'nearest' });
      } else {
        item.classList.remove('selected');
      }
    });
  };

  // Recent searches helpers
  UnifiedSearch.prototype.getRecentSearches = function() {
    try {
      return JSON.parse(localStorage.getItem(CONFIG.recentSearchesKey)) || [];
    } catch (e) {
      return [];
    }
  };

  UnifiedSearch.prototype.addRecentSearch = function(query) {
    if (!query || query.length < 2) return;
    var recent = this.getRecentSearches();
    recent = recent.filter(function(s) { return s.toLowerCase() !== query.toLowerCase(); });
    recent.unshift(query);
    recent = recent.slice(0, CONFIG.maxRecentSearches);
    try {
      localStorage.setItem(CONFIG.recentSearchesKey, JSON.stringify(recent));
    } catch (e) {}
  };

  UnifiedSearch.prototype.clearRecentSearches = function() {
    try {
      localStorage.removeItem(CONFIG.recentSearchesKey);
    } catch (e) {}
  };

  // ============================================
  // Page Search (for individual pages)
  // ============================================

  /**
   * Initialize page search if elements exist
   */
  UnifiedSearch.prototype.initPageSearch = function() {
    // Page search is now handled by PageSearchHandler instances
    // created via UnifiedSearch.createPageSearch()
  };

  /**
   * Create a page search instance
   * @param {Object} config - Configuration options
   * @returns {PageSearchHandler}
   */
  UnifiedSearch.prototype.createPageSearch = function(config) {
    var handler = new PageSearchHandler(this, config);
    this.pageSearchInstances.push(handler);
    return handler;
  };

  // ============================================
  // PageSearchHandler Class
  // ============================================

  /**
   * Handles page-level search (categories, filters, card visibility, etc.)
   *
   * Usage:
   *   new PageSearch({ searchInputId: 'talk-search', ... })
   *   new PageSearch(unifiedSearchInstance, { searchInputId: 'talk-search', ... })
   */
  function PageSearchHandler(unifiedSearchOrConfig, config) {
    // Support backwards-compatible single-argument call: new PageSearch(config)
    if (config === undefined && typeof unifiedSearchOrConfig === 'object' && !unifiedSearchOrConfig.search) {
      config = unifiedSearchOrConfig;
      this.unifiedSearch = global.UnifiedSearch;
    } else {
      this.unifiedSearch = unifiedSearchOrConfig;
    }

    // Merge config with defaults
    this.config = Object.assign({
      searchInputId: 'page-search',
      clearBtnId: 'clear-search',
      searchDataId: 'search-data',
      resultCountId: 'result-count',
      categorySelectId: 'category-select',
      viewContainerId: null,
      cardSelector: '.resource-card',
      sectionSelector: '.category-section',
      tableRowSelector: null,
      itemLabel: 'items',
      extraFilters: [],
      fuseKeys: ['name', 'description', 'category']
    }, config);

    // DOM elements
    this.searchInput = null;
    this.clearBtn = null;
    this.resultCount = null;
    this.categorySelect = null;
    this.viewContainer = null;
    this.cards = null;
    this.sections = null;
    this.tableRows = null;

    // State
    this.data = [];
    this.originalOrder = [];
    this.flatContainer = null;
    this.currentCategory = 'all';
    this.currentSearch = '';
    this.debounceTimer = null;
    this.totalItems = 0;
    this.extraFilterValues = {};

    this.init();
  }

  /**
   * Initialize page search handler
   */
  PageSearchHandler.prototype.init = function() {
    var self = this;

    // Get DOM elements
    this.searchInput = document.getElementById(this.config.searchInputId);
    this.clearBtn = document.getElementById(this.config.clearBtnId);
    this.resultCount = document.getElementById(this.config.resultCountId);
    this.categorySelect = document.getElementById(this.config.categorySelectId);

    if (!this.searchInput) {
      console.warn('[PageSearchHandler] Search input not found:', this.config.searchInputId);
      return;
    }

    // Get view container
    if (this.config.viewContainerId) {
      this.viewContainer = document.getElementById(this.config.viewContainerId);
    }
    if (!this.viewContainer) {
      this.viewContainer = this.searchInput.closest('.container');
    }

    // Get cards and sections
    this.cards = document.querySelectorAll(this.config.cardSelector);
    this.sections = document.querySelectorAll(this.config.sectionSelector);
    this.totalItems = this.cards.length;

    // Get table rows if configured
    if (this.config.tableRowSelector) {
      this.tableRows = document.querySelectorAll(this.config.tableRowSelector);
    }

    // Store original order
    this.originalOrder = Array.from(this.cards);

    // Create flat container for search results
    this.createFlatContainer();

    // Load data for filtering
    this.loadData();

    // Debug logging
    console.log('[PageSearch] Initialized:', this.config.searchInputId,
      '| Cards:', this.cards.length,
      '| Selector:', this.config.cardSelector,
      '| Sections:', this.sections.length);

    // Event listeners
    this.searchInput.addEventListener('input', function(e) {
      clearTimeout(self.debounceTimer);
      self.debounceTimer = setTimeout(function() {
        self.currentSearch = e.target.value.trim();
        self.filterItems();
        self.toggleClearButton();
      }, 150);
    });

    // Focus event to trigger model loading
    this.searchInput.addEventListener('focus', function() {
      if (self.unifiedSearch && CONFIG.semanticSearchOnFocus) {
        self.unifiedSearch.loadModel();
      }
    });

    if (this.clearBtn) {
      this.clearBtn.addEventListener('click', function() {
        self.clearSearch();
      });
    }

    if (this.categorySelect) {
      this.categorySelect.addEventListener('change', function() {
        self.currentCategory = this.value;
        self.filterItems();
      });
    }

    // Setup extra filters
    this.config.extraFilters.forEach(function(filter) {
      var selectEl = document.getElementById(filter.selectId);
      if (selectEl) {
        self.extraFilterValues[filter.dataKey] = 'all';
        selectEl.addEventListener('change', function() {
          self.extraFilterValues[filter.dataKey] = this.value;
          self.filterItems();
        });
      }
    });

    // Initial state
    this.toggleClearButton();
    this.updateResultCount(this.totalItems);

    console.log('[PageSearchHandler] Initialized:', this.config.searchInputId, '(' + this.totalItems + ' items)');
  };

  /**
   * Create flat container for search results
   */
  PageSearchHandler.prototype.createFlatContainer = function() {
    var firstSection = this.sections[0];
    if (!firstSection) return;

    this.flatContainer = document.createElement('div');
    this.flatContainer.className = 'cards-row flat-results';
    this.flatContainer.style.display = 'none';
    firstSection.parentNode.insertBefore(this.flatContainer, firstSection);
  };

  /**
   * Load search data from inline script and init Fuse.js
   */
  PageSearchHandler.prototype.loadData = function() {
    var searchDataEl = document.getElementById(this.config.searchDataId);
    if (searchDataEl) {
      try {
        this.data = JSON.parse(searchDataEl.textContent);
      } catch (e) {
        console.error('[PageSearch] Failed to parse search data:', e);
        this.data = [];
      }
    }

    // Initialize Fuse.js for local page search
    if (typeof Fuse !== 'undefined' && this.data.length > 0) {
      var fuseKeys = this.config.fuseKeys || ['name', 'description'];
      this.fuse = new Fuse(this.data, {
        keys: fuseKeys,
        threshold: 0.4,
        ignoreLocation: true,
        includeScore: true
      });
    }
  };

  /**
   * Filter items based on current search and filters
   */
  PageSearchHandler.prototype.filterItems = function() {
    var self = this;

    if (this.currentSearch && this.fuse) {
      // Use Fuse.js for local page search
      var fuseResults = this.fuse.search(this.currentSearch);
      var results = fuseResults.map(function(r) {
        return { name: r.item.name, score: r.score };
      });
      this.showFlatResults(results);
      if (this.tableRows) {
        this.filterTableRows(results);
      }
    } else {
      this.showCategoryLayout();
      if (this.tableRows) {
        this.filterTableRows(null);
      }
    }
  };

  /**
   * Check if element matches extra filters
   */
  PageSearchHandler.prototype.matchesExtraFilters = function(element) {
    var self = this;
    var matches = true;
    Object.keys(this.extraFilterValues).forEach(function(dataKey) {
      var filterValue = self.extraFilterValues[dataKey];
      if (filterValue !== 'all') {
        var elementValue = element.dataset[dataKey] || '';
        if (elementValue.toLowerCase() !== filterValue.toLowerCase()) {
          matches = false;
        }
      }
    });
    return matches;
  };

  /**
   * Filter table rows (with optional search results)
   */
  PageSearchHandler.prototype.filterTableRows = function(searchResults) {
    var self = this;

    // Build score map from search results if provided
    var scoreMap = new Map();
    if (searchResults && searchResults.length > 0) {
      searchResults.forEach(function(result, index) {
        var key = (result.name || '').toLowerCase();
        scoreMap.set(key, index);
      });
    }

    this.tableRows.forEach(function(row) {
      var name = (row.dataset.name || '').toLowerCase();
      var category = row.dataset.category || '';

      var matchesCategory = self.currentCategory === 'all' || category === self.currentCategory;
      var matchesExtra = self.matchesExtraFilters(row);
      // If searching, only show rows that match search results
      var matchesSearch = !searchResults || scoreMap.has(name);

      if (matchesCategory && matchesExtra && matchesSearch) {
        row.style.display = '';
        // Apply opacity based on search rank
        if (searchResults && scoreMap.has(name)) {
          var rank = scoreMap.get(name);
          row.style.opacity = rank < 10 ? '1' : rank < 30 ? '0.9' : '0.7';
        } else {
          row.style.opacity = '1';
        }
      } else {
        row.style.display = 'none';
      }
    });
  };

  /**
   * Show flat results sorted by relevance
   */
  PageSearchHandler.prototype.showFlatResults = function(results) {
    var self = this;

    // Hide category sections
    this.sections.forEach(function(section) {
      section.style.display = 'none';
    });

    // Show flat container
    if (this.flatContainer) {
      this.flatContainer.style.display = 'grid';
    }

    // Build score map from results
    var scoreMap = new Map();
    results.forEach(function(result, index) {
      var key = (result.name || '').toLowerCase();
      scoreMap.set(key, index);
    });

    // Sort cards by relevance
    var cardsArray = Array.from(this.cards);
    cardsArray.sort(function(a, b) {
      var nameA = (a.dataset.name || '').toLowerCase();
      var nameB = (b.dataset.name || '').toLowerCase();
      var scoreA = scoreMap.has(nameA) ? scoreMap.get(nameA) : 999999;
      var scoreB = scoreMap.has(nameB) ? scoreMap.get(nameB) : 999999;
      return scoreA - scoreB;
    });

    // Filter by category if needed
    if (this.currentCategory !== 'all') {
      cardsArray = cardsArray.filter(function(card) {
        return card.dataset.category === self.currentCategory;
      });
    }

    // Filter by extra filters
    cardsArray = cardsArray.filter(function(card) {
      return self.matchesExtraFilters(card);
    });

    // Hide all cards first
    this.cards.forEach(function(card) {
      card.classList.add('hidden');
      card.classList.remove('visible');
    });

    // Move matching cards to flat container in sorted order
    var visibleCount = 0;
    cardsArray.forEach(function(card, index) {
      var cardName = (card.dataset.name || '').toLowerCase();
      var isMatch = scoreMap.has(cardName);

      if (isMatch || self.currentSearch.length < 2) {
        card.classList.remove('hidden');
        card.classList.add('visible');
        visibleCount++;

        // Visual indicator for match quality
        var rank = scoreMap.get(cardName);
        if (rank !== undefined && rank < 10) {
          card.style.opacity = '1';
        } else if (rank !== undefined && rank < 30) {
          card.style.opacity = '0.9';
        } else {
          card.style.opacity = '0.7';
        }

        self.flatContainer.appendChild(card);
      }
    });

    this.updateResultCount(visibleCount);
  };

  /**
   * Show category layout (no search active)
   */
  PageSearchHandler.prototype.showCategoryLayout = function() {
    var self = this;

    // Reset section visibility
    this.sections.forEach(function(section) {
      section.classList.remove('section-hidden');
      var cat = section.dataset.sectionCategory;
      var shouldShow = self.currentCategory === 'all' || cat === self.currentCategory;
      section.style.display = shouldShow ? '' : 'none';
    });

    // Hide flat container
    if (this.flatContainer) {
      this.flatContainer.style.display = 'none';
    }

    // Restore cards to original positions
    var visibleCount = 0;
    this.originalOrder.forEach(function(card) {
      var cardCategory = card.dataset.category;
      var matchesCategory = self.currentCategory === 'all' || cardCategory === self.currentCategory;
      var matchesExtra = self.matchesExtraFilters(card);

      // Find original parent
      var section = document.querySelector('[data-section-category="' + cardCategory + '"]');
      if (section) {
        var cardsRow = section.querySelector('.cards-row');
        if (cardsRow && card.parentNode !== cardsRow) {
          cardsRow.appendChild(card);
        }
      }

      if (matchesCategory && matchesExtra) {
        card.classList.remove('hidden');
        card.classList.add('visible');
        card.style.opacity = '1';
        visibleCount++;
      } else {
        card.classList.add('hidden');
        card.classList.remove('visible');
      }
    });

    // Update section visibility based on visible cards
    this.sections.forEach(function(section) {
      var visibleCards = section.querySelectorAll(self.config.cardSelector + ':not(.hidden)');
      if (visibleCards.length === 0) {
        section.classList.add('section-hidden');
      } else {
        section.classList.remove('section-hidden');
      }
    });

    this.updateResultCount(visibleCount);
  };

  /**
   * Update result count display
   */
  PageSearchHandler.prototype.updateResultCount = function(count) {
    if (!this.resultCount) return;
    var text = count === 1 ? '1 ' + this.config.itemLabel.replace(/s$/, '') : count + ' ' + this.config.itemLabel;
    if (this.currentSearch) {
      text += ' (sorted by relevance)';
    }
    this.resultCount.textContent = text;
  };

  /**
   * Toggle clear button visibility
   */
  PageSearchHandler.prototype.toggleClearButton = function() {
    if (!this.clearBtn) return;
    this.clearBtn.style.display = this.searchInput.value ? 'flex' : 'none';
  };

  /**
   * Clear search
   */
  PageSearchHandler.prototype.clearSearch = function() {
    this.searchInput.value = '';
    this.currentSearch = '';
    this.filterItems();
    this.toggleClearButton();
    this.searchInput.focus();
  };

  // Expose PageSearchHandler for direct use
  global.PageSearch = PageSearchHandler;

  // ============================================
  // Utility Functions
  // ============================================

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
  }

  function smartTruncate(str, len) {
    if (!str) return '';
    if (str.length <= len) return str;

    // Try to cut at sentence boundary (. ! ?)
    var truncated = str.substring(0, len);
    var sentenceEnd = Math.max(
      truncated.lastIndexOf('. '),
      truncated.lastIndexOf('! '),
      truncated.lastIndexOf('? ')
    );
    if (sentenceEnd > len * 0.5) {
      return str.substring(0, sentenceEnd + 1);
    }

    // Fall back to word boundary
    var lastSpace = truncated.lastIndexOf(' ');
    if (lastSpace > len * 0.7) {
      return str.substring(0, lastSpace) + '...';
    }

    return truncated + '...';
  }

  function highlightText(text, query) {
    if (!text || !query) return escapeHtml(text);
    var escaped = escapeHtml(text);
    var regex = new RegExp('(' + escapeRegex(query) + ')', 'gi');
    return escaped.replace(regex, '<mark>$1</mark>');
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * Generate a contextual snippet around matching text
   * @param {string} text - Full text to extract snippet from
   * @param {string} query - Search query
   * @param {number} maxLength - Maximum snippet length
   * @returns {string} - Snippet with match context
   */
  function generateSnippet(text, query, maxLength) {
    if (!text || !query) return text || '';
    maxLength = maxLength || 150;

    var textLower = text.toLowerCase();
    var queryLower = query.toLowerCase().trim();
    var queryWords = queryLower.split(/\s+/).filter(function(w) { return w.length > 2; });

    // Find the best match position (prefer full query, then individual words)
    var matchIndex = textLower.indexOf(queryLower);

    if (matchIndex === -1 && queryWords.length > 0) {
      // Try to find any query word
      for (var i = 0; i < queryWords.length; i++) {
        matchIndex = textLower.indexOf(queryWords[i]);
        if (matchIndex !== -1) break;
      }
    }

    // If no match found, return truncated start
    if (matchIndex === -1) {
      return smartTruncate(text, maxLength);
    }

    // Calculate window around match
    var contextBefore = 40;
    var start = Math.max(0, matchIndex - contextBefore);
    var end = Math.min(text.length, start + maxLength);

    // Adjust start to not cut in the middle of a word
    if (start > 0) {
      var firstSpaceAfterStart = text.indexOf(' ', start);
      if (firstSpaceAfterStart > start && firstSpaceAfterStart < start + 15) {
        start = firstSpaceAfterStart + 1;
      }
    }

    var snippet = text.substring(start, end);

    // Clean up boundaries
    if (start > 0) {
      snippet = '...' + snippet.trimStart();
    }

    if (end < text.length) {
      // Try to cut at word boundary
      var lastSpace = snippet.lastIndexOf(' ');
      if (lastSpace > snippet.length - 20 && lastSpace > 0) {
        snippet = snippet.substring(0, lastSpace) + '...';
      } else {
        snippet = snippet + '...';
      }
    }

    return snippet;
  }

  /**
   * Enhanced highlight with multi-word support
   */
  function highlightTextEnhanced(text, query) {
    if (!text || !query) return escapeHtml(text);

    var escaped = escapeHtml(text);
    var queryLower = query.toLowerCase().trim();

    // First highlight full query match (if present)
    var fullRegex = new RegExp('(' + escapeRegex(queryLower) + ')', 'gi');
    escaped = escaped.replace(fullRegex, '<mark>$1</mark>');

    // Then highlight individual words (skip very short words)
    var words = queryLower.split(/\s+/).filter(function(w) { return w.length > 2; });
    words.forEach(function(word) {
      // Don't highlight if already inside a mark tag
      var wordRegex = new RegExp('(?![^<]*>)(' + escapeRegex(word) + ')(?![^<]*</mark>)', 'gi');
      escaped = escaped.replace(wordRegex, '<mark class="partial">$1</mark>');
    });

    return escaped;
  }

  // ============================================
  // LLM Enhancement Methods
  // ============================================

  /**
   * Initialize LLM toggle button and load preference
   */
  UnifiedSearch.prototype.initLLMToggle = function() {
    var self = this;
    console.log('[UnifiedSearch] initLLMToggle called, LLM_CONFIG:', window.LLM_CONFIG);

    // Get endpoint from config
    if (typeof window !== 'undefined' && window.LLM_CONFIG && window.LLM_CONFIG.enabled) {
      this.llmEndpoint = window.LLM_CONFIG.endpoint;
      console.log('[UnifiedSearch] LLM enabled, endpoint:', this.llmEndpoint);
    } else {
      // LLM not configured, hide toggle button
      console.log('[UnifiedSearch] LLM not enabled, hiding button');
      var toggleBtn = document.getElementById('llm-search-toggle');
      if (toggleBtn) {
        toggleBtn.style.display = 'none';
      }
      return;
    }

    this.llmToggleBtn = document.getElementById('llm-search-toggle');
    this.llmExpandedTermsContainer = document.getElementById('llm-expanded-terms');
    this.llmExplanationPanel = document.getElementById('llm-explanation-panel');
    console.log('[UnifiedSearch] Found toggle button:', !!this.llmToggleBtn);

    if (!this.llmToggleBtn) return;

    // Load saved preference (following theme.js pattern)
    try {
      var saved = localStorage.getItem(CONFIG.llmSearchKey);
      this.llmEnabled = saved === 'true';
    } catch(e) {
      this.llmEnabled = false;
    }

    this.updateLLMToggleUI();

    // Toggle click handler
    console.log('[UnifiedSearch] Adding click handler to toggle button');
    this.llmToggleBtn.addEventListener('click', function(e) {
      console.log('[UnifiedSearch] Toggle button clicked!');
      e.stopPropagation();
      e.preventDefault();
      self.llmEnabled = !self.llmEnabled;
      console.log('[UnifiedSearch] LLM enabled:', self.llmEnabled);
      try {
        localStorage.setItem(CONFIG.llmSearchKey, String(self.llmEnabled));
      } catch(e) {}
      self.updateLLMToggleUI();

      // Clear expanded terms when toggling off
      if (!self.llmEnabled) {
        self.clearExpandedTerms();
        self.hideExplanationPanel();
      }

      // Re-run current search with new setting if there's a query
      if (self.input && self.input.value.trim().length >= 2) {
        self.performGlobalSearch();
      }
    });

    // Explanation panel close button
    var closeBtn = document.getElementById('llm-explanation-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        self.hideExplanationPanel();
      });
    }
  };

  /**
   * Update LLM toggle button UI
   */
  UnifiedSearch.prototype.updateLLMToggleUI = function() {
    if (!this.llmToggleBtn) return;

    if (this.llmEnabled) {
      this.llmToggleBtn.classList.add('active');
      this.llmToggleBtn.title = 'AI search enabled (click to disable)';
      if (this.resultsContainer) {
        this.resultsContainer.classList.add('llm-enabled');
      }
    } else {
      this.llmToggleBtn.classList.remove('active');
      this.llmToggleBtn.title = 'Enable AI-enhanced search';
      if (this.resultsContainer) {
        this.resultsContainer.classList.remove('llm-enabled');
      }
    }
  };

  /**
   * Expand query using LLM
   * @param {string} query - The search query
   * @returns {Promise<Array<string>>} - Array of expanded terms
   */
  UnifiedSearch.prototype.expandQueryWithLLM = function(query) {
    var self = this;

    if (!this.llmEnabled || !this.llmEndpoint) {
      return Promise.resolve([]);
    }

    this.isExpandingQuery = true;
    this.showLLMStatus('Enhancing search...');

    var controller = new AbortController();
    var timeoutId = setTimeout(function() {
      controller.abort();
    }, CONFIG.llmExpandTimeout);

    return fetch(this.llmEndpoint + '/expand', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query }),
      signal: controller.signal
    })
    .then(function(response) {
      clearTimeout(timeoutId);
      if (!response.ok) throw new Error('LLM expand failed');
      return response.json();
    })
    .then(function(data) {
      self.isExpandingQuery = false;
      self.hideLLMStatus();
      self.expandedTerms = data.expandedTerms || [];
      if (self.expandedTerms.length > 0) {
        self.showExpandedTerms(self.expandedTerms);
      }
      return self.expandedTerms;
    })
    .catch(function(error) {
      clearTimeout(timeoutId);
      if (error.name !== 'AbortError') {
        console.warn('[UnifiedSearch] LLM expand failed:', error);
      }
      self.isExpandingQuery = false;
      self.hideLLMStatus();
      self.expandedTerms = [];
      return [];
    });
  };

  /**
   * Get explanation for a result (streaming)
   * @param {Object} result - The result to explain
   * @param {string} query - The search query
   */
  UnifiedSearch.prototype.explainResult = function(result, query) {
    var self = this;

    if (!this.llmEnabled || !this.llmEndpoint) return;

    // Abort any previous explanation request
    if (this.explanationAbortController) {
      this.explanationAbortController.abort();
    }
    this.explanationAbortController = new AbortController();

    var panel = this.llmExplanationPanel;
    var content = document.getElementById('llm-explanation-content');
    if (!panel || !content) return;

    panel.style.display = 'block';
    content.innerHTML = '<span class="streaming-cursor"></span>';

    var timeoutId = setTimeout(function() {
      self.explanationAbortController.abort();
    }, CONFIG.llmExplainTimeout);

    fetch(this.llmEndpoint + '/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        result: {
          name: result.name,
          description: result.description,
          type: result.type,
          category: result.category
        }
      }),
      signal: this.explanationAbortController.signal
    })
    .then(function(response) {
      clearTimeout(timeoutId);
      if (!response.ok) throw new Error('Explain failed');
      return self.handleStreamingResponse(response, content);
    })
    .catch(function(error) {
      clearTimeout(timeoutId);
      if (error.name !== 'AbortError') {
        content.innerHTML = '<em>Could not generate explanation.</em>';
      }
    });
  };

  /**
   * Handle SSE streaming response
   * @param {Response} response - Fetch response
   * @param {HTMLElement} container - Container to render into
   */
  UnifiedSearch.prototype.handleStreamingResponse = function(response, container) {
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var text = '';

    function read() {
      return reader.read().then(function(result) {
        if (result.done) {
          container.innerHTML = text || '<em>No explanation available.</em>';
          return;
        }

        var chunk = decoder.decode(result.value, { stream: true });
        // Parse SSE format: data: {...}
        var lines = chunk.split('\n');
        lines.forEach(function(line) {
          if (line.startsWith('data: ')) {
            var data = line.slice(6);
            if (data === '[DONE]') return;
            try {
              var parsed = JSON.parse(data);
              if (parsed.content) {
                text += parsed.content;
                container.innerHTML = text + '<span class="streaming-cursor"></span>';
              } else if (parsed.error) {
                container.innerHTML = '<em>' + escapeHtml(parsed.error) + '</em>';
              }
            } catch(e) {}
          }
        });

        return read();
      });
    }

    return read();
  };

  /**
   * Show LLM status indicator
   */
  UnifiedSearch.prototype.showLLMStatus = function(message) {
    var existingStatus = document.getElementById('llm-status');
    if (!existingStatus && this.filtersContainer) {
      existingStatus = document.createElement('span');
      existingStatus.id = 'llm-status';
      existingStatus.className = 'llm-status-indicator expanding';
      this.filtersContainer.parentNode.insertBefore(existingStatus, this.filtersContainer);
    }
    if (existingStatus) {
      existingStatus.textContent = message;
      existingStatus.style.display = 'inline-flex';
    }
  };

  /**
   * Hide LLM status indicator
   */
  UnifiedSearch.prototype.hideLLMStatus = function() {
    var status = document.getElementById('llm-status');
    if (status) {
      status.style.display = 'none';
    }
  };

  /**
   * Show expanded query terms as chips
   */
  UnifiedSearch.prototype.showExpandedTerms = function(terms) {
    if (!terms || terms.length === 0 || !this.llmExpandedTermsContainer) return;

    var html = '<span class="llm-expanded-label">AI added:</span>';
    html += terms.map(function(term) {
      return '<span class="llm-expanded-chip">' + escapeHtml(term) + '</span>';
    }).join('');

    this.llmExpandedTermsContainer.innerHTML = html;
    this.llmExpandedTermsContainer.style.display = 'flex';
  };

  /**
   * Clear expanded terms display
   */
  UnifiedSearch.prototype.clearExpandedTerms = function() {
    if (this.llmExpandedTermsContainer) {
      this.llmExpandedTermsContainer.innerHTML = '';
      this.llmExpandedTermsContainer.style.display = 'none';
    }
    this.expandedTerms = [];
  };

  /**
   * Hide explanation panel
   */
  UnifiedSearch.prototype.hideExplanationPanel = function() {
    if (this.llmExplanationPanel) {
      this.llmExplanationPanel.style.display = 'none';
    }
    if (this.explanationAbortController) {
      this.explanationAbortController.abort();
      this.explanationAbortController = null;
    }
  };

  // ============================================
  // Initialization
  // ============================================

  // Create singleton instance
  var unifiedSearch = new UnifiedSearch();

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      unifiedSearch.init();
    });
  } else {
    unifiedSearch.init();
  }

  // Export
  global.UnifiedSearch = unifiedSearch;

})(typeof window !== 'undefined' ? window : this);
