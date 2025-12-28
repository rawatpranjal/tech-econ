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
    maxResultsPerType: 5,
    maxTotalResults: 20,
    recentSearchesKey: 'global-recent-searches',
    maxRecentSearches: 5,
    suggestions: ['causal inference', 'experimentation', 'pricing', 'machine learning', 'A/B testing'],
    enableSemanticSearch: true,
    semanticSearchOnFocus: true,  // Start loading model on focus
    workerPath: '/js/search/search-worker.js'
  };

  // Type display configuration
  var TYPE_CONFIG = {
    package: { label: 'Package', icon: 'pkg', color: '#0066cc', href: '/packages/' },
    dataset: { label: 'Dataset', icon: 'data', color: '#2e7d32', href: '/datasets/' },
    resource: { label: 'Resource', icon: 'book', color: '#7b1fa2', href: '/resources/' },
    talk: { label: 'Talk', icon: 'mic', color: '#e65100', href: '/talks/' },
    career: { label: 'Career', icon: 'job', color: '#c2185b', href: '/career/' },
    community: { label: 'Community', icon: 'people', color: '#00796b', href: '/community/' },
    roadmap: { label: 'Roadmap', icon: 'map', color: '#1565c0', href: '/start/' }
  };

  /**
   * UnifiedSearch class
   */
  function UnifiedSearch() {
    // Worker
    this.worker = null;
    this.workerReady = false;
    this.pendingSearches = new Map();
    this.searchId = 0;

    // State
    this.isIndexLoaded = false;
    this.isEmbeddingsLoaded = false;
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

    // Page search instances
    this.pageSearchInstances = [];
  }

  /**
   * Initialize the search system
   */
  UnifiedSearch.prototype.init = function() {
    var self = this;

    // Initialize worker
    this.initWorker();

    // Load search index and embeddings
    this.loadSearchAssets();

    // Initialize global search UI
    this.initGlobalSearchUI();

    // Initialize page search if applicable
    this.initPageSearch();

    console.log('[UnifiedSearch] Initialized');
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
   * Load search assets (index and embeddings)
   */
  UnifiedSearch.prototype.loadSearchAssets = function() {
    var self = this;

    // Load search index
    fetch('/embeddings/search-index.json')
      .then(function(response) {
        if (!response.ok) throw new Error('Failed to load search index');
        return response.json();
      })
      .then(function(indexData) {
        self.searchIndex = indexData;
        if (self.workerReady) {
          self.worker.postMessage({
            type: 'LOAD_INDEX',
            payload: { indexData: indexData }
          });
        }
      })
      .catch(function(error) {
        console.warn('[UnifiedSearch] Failed to load search index:', error);
        // Fallback to inline data
        self.loadFallbackIndex();
      });

    // Load embeddings (try cache first)
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
              boost: { name: 3, tags: 1.5, best_for: 1.2, description: 1, category: 0.8 },
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
          console.log('[UnifiedSearch] Using cached embeddings');
          self.sendEmbeddingsToWorker(cached.metadata, cached.embeddings.buffer);
          return;
        }
        self.fetchEmbeddings();
      });
    } else {
      this.fetchEmbeddings();
    }
  };

  /**
   * Fetch embeddings from server
   */
  UnifiedSearch.prototype.fetchEmbeddings = function() {
    var self = this;

    Promise.all([
      fetch('/embeddings/search-metadata.json').then(function(r) {
        if (!r.ok) throw new Error('Failed to load metadata');
        return r.json();
      }),
      fetch('/embeddings/search-embeddings.bin').then(function(r) {
        if (!r.ok) throw new Error('Failed to load embeddings');
        return r.arrayBuffer();
      })
    ]).then(function(results) {
      var metadata = results[0];
      var buffer = results[1];

      // Cache for next time
      if (global.SearchCache) {
        global.SearchCache.setEmbeddings(metadata, buffer);
      }

      self.sendEmbeddingsToWorker(metadata, buffer);
    }).catch(function(error) {
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
   */
  UnifiedSearch.prototype.sendEmbeddingsToWorker = function(metadata, buffer) {
    if (!this.workerReady) return;

    this.worker.postMessage({
      type: 'LOAD_EMBEDDINGS',
      payload: {
        metadata: metadata,
        embeddingsBuffer: buffer
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
   * Perform search (internal)
   */
  UnifiedSearch.prototype._doSearch = function(query, options) {
    var self = this;

    return new Promise(function(resolve) {
      var id = ++self.searchId;
      self.pendingSearches.set(id, resolve);

      self.worker.postMessage({
        type: 'SEARCH',
        id: id,
        payload: {
          query: query,
          topK: options.topK || CONFIG.maxTotalResults,
          semantic: options.semantic !== false && self.isEmbeddingsLoaded && self.isModelLoaded
        }
      });

      // Timeout after 5 seconds
      setTimeout(function() {
        if (self.pendingSearches.has(id)) {
          self.pendingSearches.delete(id);
          resolve([]);
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
   * Handle search results from worker
   */
  UnifiedSearch.prototype.handleSearchResults = function(id, payload) {
    var resolve = this.pendingSearches.get(id);
    if (resolve) {
      this.pendingSearches.delete(id);
      resolve(payload.results);
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
    this.emptyState = document.getElementById('global-search-empty');
    this.hint = document.getElementById('global-search-hint');
    this.triggers = document.querySelectorAll('.global-search-trigger');

    this.bindGlobalSearchEvents();
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
        var item = e.target.closest('.result-item');
        if (item) {
          self.closeModal();
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
      return;
    }

    // Save to recent searches
    this.addRecentSearch(query);

    // Perform search
    this.search(query, { topK: CONFIG.maxTotalResults * 2 })
      .then(function(results) {
        self.currentResults = results.slice(0, CONFIG.maxTotalResults);

        if (self.currentResults.length === 0) {
          self.showEmpty();
          self.flatResults = [];
        } else {
          self.renderGlobalResults(self.currentResults, query);
        }
      });
  };

  /**
   * Render global search results
   */
  UnifiedSearch.prototype.renderGlobalResults = function(results, query) {
    var self = this;
    this.hint.style.display = 'none';
    this.emptyState.style.display = 'none';

    // Group by type
    var grouped = {};
    results.forEach(function(result) {
      var type = result.type;
      if (!grouped[type]) grouped[type] = [];
      if (grouped[type].length < CONFIG.maxResultsPerType) {
        grouped[type].push(result);
      }
    });

    var html = '';
    this.flatResults = [];
    var globalIndex = 0;

    // Order of types
    var typeOrder = ['package', 'dataset', 'resource', 'talk', 'career', 'community', 'roadmap'];

    typeOrder.forEach(function(type) {
      if (!grouped[type]) return;

      var typeConfig = TYPE_CONFIG[type] || { label: type, icon: 'file', color: '#666' };

      html += '<div class="result-group">';
      html += '<div class="result-group-header">';
      html += '<span class="result-type-label">' + typeConfig.label + 's</span>';
      html += '</div>';

      grouped[type].forEach(function(result) {
        var isSelected = globalIndex === self.selectedIndex;
        self.flatResults.push(result);

        html += '<a href="' + escapeHtml(result.url) + '" ';
        html += 'class="result-item' + (isSelected ? ' selected' : '') + '" ';
        html += 'data-index="' + globalIndex + '" ';
        html += 'target="_blank" rel="noopener">';
        html += '<div class="result-content">';
        html += '<span class="result-name">' + highlightText(result.name, query) + '</span>';
        html += '<span class="result-description">' + highlightText(truncate(result.description, 80), query) + '</span>';
        html += '</div>';
        html += '<span class="result-category">' + escapeHtml(result.category) + '</span>';
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
   * Show hint (recent searches + suggestions)
   */
  UnifiedSearch.prototype.showHint = function() {
    var self = this;
    this.emptyState.style.display = 'none';
    this.hint.style.display = 'none';

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

  function highlightText(text, query) {
    if (!text || !query) return escapeHtml(text);
    var escaped = escapeHtml(text);
    var regex = new RegExp('(' + escapeRegex(query) + ')', 'gi');
    return escaped.replace(regex, '<mark>$1</mark>');
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

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
