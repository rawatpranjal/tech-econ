/**
 * Search Cache Module - IndexedDB caching for search assets
 *
 * Caches:
 * - Embeddings (binary Float32Array, ~1MB)
 * - Transformers.js model weights (~23MB)
 * - Search index (~50KB)
 */
(function(global) {
  'use strict';

  var DB_NAME = 'tech-econ-search';
  var DB_VERSION = 1;
  var STORE_NAME = 'cache';

  var SearchCache = {
    db: null,
    isReady: false,
    _initPromise: null
  };

  /**
   * Initialize IndexedDB
   * @returns {Promise<boolean>}
   */
  SearchCache.init = function() {
    if (this.isReady) return Promise.resolve(true);
    if (this._initPromise) return this._initPromise;

    var self = this;
    this._initPromise = new Promise(function(resolve, reject) {
      if (!window.indexedDB) {
        console.warn('[SearchCache] IndexedDB not supported');
        resolve(false);
        return;
      }

      var request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = function(event) {
        console.warn('[SearchCache] Failed to open database:', event.target.error);
        resolve(false);
      };

      request.onsuccess = function(event) {
        self.db = event.target.result;
        self.isReady = true;
        console.log('[SearchCache] Database ready');
        resolve(true);
      };

      request.onupgradeneeded = function(event) {
        var db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      };
    });

    return this._initPromise;
  };

  /**
   * Get cached item
   * @param {string} key - Cache key
   * @returns {Promise<any>}
   */
  SearchCache.get = function(key) {
    var self = this;
    return this.init().then(function(ready) {
      if (!ready || !self.db) return null;

      return new Promise(function(resolve) {
        try {
          var transaction = self.db.transaction([STORE_NAME], 'readonly');
          var store = transaction.objectStore(STORE_NAME);
          var request = store.get(key);

          request.onsuccess = function() {
            resolve(request.result || null);
          };

          request.onerror = function() {
            resolve(null);
          };
        } catch (e) {
          resolve(null);
        }
      });
    });
  };

  /**
   * Set cached item
   * @param {string} key - Cache key
   * @param {any} value - Value to cache
   * @returns {Promise<boolean>}
   */
  SearchCache.set = function(key, value) {
    var self = this;
    return this.init().then(function(ready) {
      if (!ready || !self.db) return false;

      return new Promise(function(resolve) {
        try {
          var transaction = self.db.transaction([STORE_NAME], 'readwrite');
          var store = transaction.objectStore(STORE_NAME);
          var request = store.put(value, key);

          request.onsuccess = function() {
            resolve(true);
          };

          request.onerror = function() {
            console.warn('[SearchCache] Failed to cache:', key);
            resolve(false);
          };
        } catch (e) {
          resolve(false);
        }
      });
    });
  };

  /**
   * Delete cached item
   * @param {string} key - Cache key
   * @returns {Promise<boolean>}
   */
  SearchCache.delete = function(key) {
    var self = this;
    return this.init().then(function(ready) {
      if (!ready || !self.db) return false;

      return new Promise(function(resolve) {
        try {
          var transaction = self.db.transaction([STORE_NAME], 'readwrite');
          var store = transaction.objectStore(STORE_NAME);
          var request = store.delete(key);

          request.onsuccess = function() {
            resolve(true);
          };

          request.onerror = function() {
            resolve(false);
          };
        } catch (e) {
          resolve(false);
        }
      });
    });
  };

  /**
   * Clear all cached items
   * @returns {Promise<boolean>}
   */
  SearchCache.clear = function() {
    var self = this;
    return this.init().then(function(ready) {
      if (!ready || !self.db) return false;

      return new Promise(function(resolve) {
        try {
          var transaction = self.db.transaction([STORE_NAME], 'readwrite');
          var store = transaction.objectStore(STORE_NAME);
          var request = store.clear();

          request.onsuccess = function() {
            console.log('[SearchCache] Cache cleared');
            resolve(true);
          };

          request.onerror = function() {
            resolve(false);
          };
        } catch (e) {
          resolve(false);
        }
      });
    });
  };

  // Cache keys
  SearchCache.KEYS = {
    EMBEDDINGS: 'embeddings-v2',
    EMBEDDINGS_METADATA: 'embeddings-metadata-v2',
    SEARCH_INDEX: 'search-index-v1',
    MODEL_LOADED: 'model-loaded-v1'
  };

  /**
   * Get cached embeddings
   * @param {string} contentHash - Expected content hash for validation
   * @returns {Promise<{metadata: Object, embeddings: Float32Array}|null>}
   */
  SearchCache.getEmbeddings = function(contentHash) {
    var self = this;
    return Promise.all([
      this.get(this.KEYS.EMBEDDINGS_METADATA),
      this.get(this.KEYS.EMBEDDINGS)
    ]).then(function(results) {
      var metadata = results[0];
      var embeddings = results[1];

      if (!metadata || !embeddings) {
        return null;
      }

      // Validate content hash if provided
      if (contentHash && metadata.contentHash !== contentHash) {
        console.log('[SearchCache] Embeddings cache invalidated (content changed)');
        return null;
      }

      return {
        metadata: metadata,
        embeddings: new Float32Array(embeddings)
      };
    });
  };

  /**
   * Cache embeddings
   * @param {Object} metadata - Metadata object
   * @param {ArrayBuffer} embeddingsBuffer - Binary embeddings
   * @returns {Promise<boolean>}
   */
  SearchCache.setEmbeddings = function(metadata, embeddingsBuffer) {
    return Promise.all([
      this.set(this.KEYS.EMBEDDINGS_METADATA, metadata),
      this.set(this.KEYS.EMBEDDINGS, embeddingsBuffer)
    ]).then(function(results) {
      return results[0] && results[1];
    });
  };

  /**
   * Get cached search index
   * @returns {Promise<Object|null>}
   */
  SearchCache.getSearchIndex = function() {
    return this.get(this.KEYS.SEARCH_INDEX);
  };

  /**
   * Cache search index
   * @param {Object} index - Search index data
   * @returns {Promise<boolean>}
   */
  SearchCache.setSearchIndex = function(index) {
    return this.set(this.KEYS.SEARCH_INDEX, index);
  };

  // Export
  if (typeof module === 'object' && module.exports) {
    module.exports = SearchCache;
  } else {
    global.SearchCache = SearchCache;
  }

})(typeof window !== 'undefined' ? window : typeof self !== 'undefined' ? self : this);
