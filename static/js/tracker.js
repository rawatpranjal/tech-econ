/**
 * Tech-Econ Analytics Tracker
 * Privacy-respecting telemetry for search, clicks, and performance
 */
(function(global) {
  'use strict';

  // Configuration (injected from Hugo template)
  var CONFIG = global.TRACKER_CONFIG || {
    endpoint: null,
    enabled: true,
    debug: false
  };

  // State
  var eventQueue = [];
  var sessionId = null;
  var BATCH_SIZE = 10;
  var FLUSH_INTERVAL = 30000;

  /**
   * Initialize tracker
   */
  function init() {
    // Respect Do Not Track
    if (navigator.doNotTrack === '1' || !CONFIG.enabled || !CONFIG.endpoint) {
      log('Tracker disabled');
      return;
    }

    // Generate anonymous session ID
    sessionId = getSessionId();

    // Set up tracking
    initSearchTracking();
    initClickTracking();
    initPerformanceTracking();
    initErrorTracking();

    // Periodic flush
    setInterval(flush, FLUSH_INTERVAL);

    // Flush on page hide
    document.addEventListener('visibilitychange', function() {
      if (document.visibilityState === 'hidden') {
        flush(true);
      }
    });

    // Track page view
    track('pageview', {
      path: window.location.pathname,
      ref: document.referrer ? hashString(document.referrer) : null
    });

    log('Tracker initialized');
  }

  /**
   * Get or create session ID
   */
  function getSessionId() {
    try {
      var stored = sessionStorage.getItem('_tid');
      if (stored) return stored;
      var id = Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem('_tid', id);
      return id;
    } catch (e) {
      return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    }
  }

  /**
   * Hash a string for privacy
   */
  function hashString(str) {
    var hash = 0;
    for (var i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash = hash & hash;
    }
    return hash.toString(36);
  }

  /**
   * Track an event
   */
  function track(type, data) {
    if (!sessionId) return;

    eventQueue.push({
      t: type,
      ts: Date.now(),
      sid: sessionId,
      p: window.location.pathname,
      d: data || {}
    });

    log('Event:', type, data);

    if (eventQueue.length >= BATCH_SIZE) {
      flush();
    }
  }

  /**
   * Flush events to backend
   */
  function flush(immediate) {
    if (eventQueue.length === 0) return;

    var events = eventQueue.splice(0);
    var payload = JSON.stringify({ v: 1, events: events });

    log('Flushing', events.length, 'events');

    if (immediate && navigator.sendBeacon) {
      navigator.sendBeacon(CONFIG.endpoint, payload);
    } else {
      fetch(CONFIG.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true
      }).catch(function(err) {
        log('Flush failed:', err);
      });
    }
  }

  // ============================================
  // Search Tracking
  // ============================================

  function initSearchTracking() {
    var debounceTimers = {};

    document.addEventListener('input', function(e) {
      var input = e.target;
      if (!input.matches('input[type="text"], input[type="search"], input:not([type])')) return;
      if (!input.id || !input.id.toLowerCase().includes('search')) return;

      clearTimeout(debounceTimers[input.id]);
      debounceTimers[input.id] = setTimeout(function() {
        var query = input.value.trim();
        if (query.length >= 2) {
          track('search', {
            q: query.toLowerCase(),
            src: input.id
          });
        }
      }, 1000);
    });
  }

  // ============================================
  // Click Tracking
  // ============================================

  function initClickTracking() {
    document.addEventListener('click', function(e) {
      var link = e.target.closest('a');
      if (!link) return;

      var href = link.getAttribute('href');
      if (!href) return;

      // External links
      if (link.hostname && link.hostname !== window.location.hostname) {
        track('click', {
          type: 'external',
          url: hashString(href),
          text: truncate(link.textContent, 50),
          section: getSection(link)
        });
      }
      // Internal links
      else if (href.startsWith('/')) {
        track('click', {
          type: 'internal',
          to: href,
          section: getSection(link)
        });
      }
    });

    // Card clicks
    document.addEventListener('click', function(e) {
      var card = e.target.closest('[data-name]');
      if (card) {
        track('click', {
          type: 'card',
          name: card.dataset.name,
          category: card.dataset.category || null
        });
      }
    });
  }

  function getSection(el) {
    var section = el.closest('[data-section-category]');
    if (section) return section.dataset.sectionCategory;

    var path = window.location.pathname;
    if (path.includes('/packages')) return 'packages';
    if (path.includes('/datasets')) return 'datasets';
    if (path.includes('/learning')) return 'learning';
    if (path.includes('/books')) return 'books';
    if (path.includes('/talks')) return 'talks';
    return 'other';
  }

  // ============================================
  // Performance Tracking
  // ============================================

  function initPerformanceTracking() {
    if (document.readyState === 'complete') {
      setTimeout(trackPerformance, 1000);
    } else {
      window.addEventListener('load', function() {
        setTimeout(trackPerformance, 1000);
      });
    }

    // Core Web Vitals
    if ('PerformanceObserver' in window) {
      // LCP
      try {
        new PerformanceObserver(function(list) {
          var entries = list.getEntries();
          var last = entries[entries.length - 1];
          track('vitals', {
            metric: 'LCP',
            value: Math.round(last.startTime),
            rating: last.startTime < 2500 ? 'good' : last.startTime < 4000 ? 'needs-improvement' : 'poor'
          });
        }).observe({ type: 'largest-contentful-paint', buffered: true });
      } catch (e) {}

      // FID
      try {
        new PerformanceObserver(function(list) {
          list.getEntries().forEach(function(entry) {
            var fid = entry.processingStart - entry.startTime;
            track('vitals', {
              metric: 'FID',
              value: Math.round(fid),
              rating: fid < 100 ? 'good' : fid < 300 ? 'needs-improvement' : 'poor'
            });
          });
        }).observe({ type: 'first-input', buffered: true });
      } catch (e) {}

      // CLS
      try {
        var clsValue = 0;
        new PerformanceObserver(function(list) {
          list.getEntries().forEach(function(entry) {
            if (!entry.hadRecentInput) clsValue += entry.value;
          });
        }).observe({ type: 'layout-shift', buffered: true });

        document.addEventListener('visibilitychange', function() {
          if (document.visibilityState === 'hidden') {
            track('vitals', {
              metric: 'CLS',
              value: Math.round(clsValue * 1000) / 1000,
              rating: clsValue < 0.1 ? 'good' : clsValue < 0.25 ? 'needs-improvement' : 'poor'
            });
          }
        });
      } catch (e) {}
    }
  }

  function trackPerformance() {
    var timing = performance.timing;
    if (!timing) return;

    var metrics = {
      ttfb: timing.responseStart - timing.requestStart,
      domLoad: timing.domContentLoadedEventEnd - timing.navigationStart,
      fullLoad: timing.loadEventEnd - timing.navigationStart
    };

    // Filter invalid values
    Object.keys(metrics).forEach(function(k) {
      if (metrics[k] < 0 || metrics[k] > 60000) delete metrics[k];
    });

    if (Object.keys(metrics).length > 0) {
      track('perf', metrics);
    }
  }

  // ============================================
  // Error Tracking
  // ============================================

  function initErrorTracking() {
    window.addEventListener('error', function(e) {
      track('error', {
        msg: truncate(e.message, 200),
        file: e.filename ? hashString(e.filename) : null,
        line: e.lineno
      });
    });

    window.addEventListener('unhandledrejection', function(e) {
      track('error', {
        type: 'promise',
        msg: truncate(String(e.reason), 200)
      });
    });
  }

  // ============================================
  // Utilities
  // ============================================

  function truncate(str, len) {
    if (!str) return '';
    str = String(str).trim();
    return str.length > len ? str.substring(0, len) + '...' : str;
  }

  function log() {
    if (CONFIG.debug) {
      console.log.apply(console, ['[Tracker]'].concat(Array.from(arguments)));
    }
  }

  // Public API
  global.Tracker = { track: track, flush: flush };

  // Initialize
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})(window);
