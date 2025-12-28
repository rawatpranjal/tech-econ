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
   * Perform search
   */
  UnifiedSearch.prototype.search = function(query, options) {
    var self = this;
    options = options || {};

    if (!this.workerReady || !this.isIndexLoaded) {
      return Promise.resolve([]);
    }

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
    var self = this;

    // Look for page search elements
    var pageConfigs = [
      { inputId: 'package-search', itemLabel: 'packages' },
      { inputId: 'talk-search', itemLabel: 'talks' },
      { inputId: 'dataset-search', itemLabel: 'datasets' },
      { inputId: 'resource-search', itemLabel: 'resources' },
      { inputId: 'career-search', itemLabel: 'resources' },
      { inputId: 'community-search', itemLabel: 'events & communities' }
    ];

    pageConfigs.forEach(function(config) {
      var input = document.getElementById(config.inputId);
      if (input) {
        self.createPageSearchInstance(config);
      }
    });
  };

  /**
   * Create page search instance (uses existing PageSearch if available, otherwise creates minimal implementation)
   */
  UnifiedSearch.prototype.createPageSearchInstance = function(config) {
    // For now, just ensure the existing PageSearch works
    // The unified search provides the backend, PageSearch handles the UI
    console.log('[UnifiedSearch] Page search active:', config.inputId);
  };

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
