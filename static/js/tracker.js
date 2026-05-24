/**
 * Tech-Econ Analytics Tracker v2.1
 * ML-ready, privacy-respecting telemetry with user identity
 * Target: <5KB gzipped
 */
(function(global) {
  'use strict';

  var CONFIG = global.TRACKER_CONFIG || { endpoint: null, enabled: true, debug: false };
  var eventQueue = [];
  var sessionId = null;
  var sessionState = null;
  var BATCH_SIZE = 10;
  var FLUSH_INTERVAL = 30000;
  var WPM = 238; // Average reading speed

  // User identity state
  var userId = null;
  var sessionNumber = 0;
  var isReturningUser = false;
  var deviceType = null;
  var cookieReady = false;

  // ============================================
  // User Identity (Cookie-based)
  // ============================================

  function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function setCookie(name, value, maxAgeDays) {
    var maxAge = (maxAgeDays || 365) * 86400;
    var parts = [
      name + '=' + encodeURIComponent(value),
      'path=/',
      'max-age=' + maxAge,
      'SameSite=Lax'
    ];
    if (location.protocol === 'https:') parts.push('Secure');
    document.cookie = parts.join('; ');
  }

  function initUserIdentity() {
    var existingUid = getCookie('te_uid');
    var existingSn = getCookie('te_sn');

    if (existingUid) {
      userId = existingUid;
      isReturningUser = true;
      sessionNumber = parseInt(existingSn || '0', 10) + 1;
      setCookie('te_sn', String(sessionNumber), 365);
      cookieReady = true;
    } else {
      userId = generateUUID();
      isReturningUser = false;
      sessionNumber = 1;
      // Write te_uid eagerly at page load so experiments.js reads the same
      // UUID on first impression. The old pattern deferred to first click/scroll
      // (setOnInteraction), which caused first-visit users to receive a different
      // ephemeral UUID for impressions vs. a real UID after interaction —
      // resulting in the same user appearing in both A/B variants (A.5 audit,
      // 57 contaminated users, 19 days of harness_aa_v1 data poisoned).
      cookieReady = true;
      setCookie('te_uid', userId, 365);
      setCookie('te_sn', '1', 365);
    }
    deviceType = getDeviceType();
  }


  // ============================================
  // Initialization
  // ============================================

  function init() {
    // Respect Do Not Track AND Global Privacy Control
    if (navigator.doNotTrack === '1' || navigator.globalPrivacyControl === true || !CONFIG.enabled || !CONFIG.endpoint) {
      log('Tracker disabled');
      return;
    }

    sessionId = getSessionId();
    sessionState = getSessionState();
    initUserIdentity();

    // Add current page to sequence
    addToSequence('page', { pid: location.pathname, ts: Date.now() });

    // Initialize all tracking modules
    initClickTracking();
    initDwellTracking();
    initScrollMilestones();
    initSearchAttribution();
    initFrustrationTracking();
    initPerformanceTracking();
    initErrorTracking();

    // Periodic flush
    setInterval(flush, FLUSH_INTERVAL);

    // Flush and send session on page hide
    document.addEventListener('visibilitychange', function() {
      if (document.visibilityState === 'hidden') {
        flushDwellData();
        sendSessionData();
        flush(true);
      }
    });

    // Backup: pagehide for mobile
    window.addEventListener('pagehide', function() {
      flushDwellData();
      sendSessionData();
      flush(true);
    });

    // Track pageview with device and referrer source
    track('pageview', {
      path: location.pathname,
      ref: document.referrer ? hash(document.referrer) : null,
      refSource: getReferrerSource(),
      device: getDeviceType()
    });

    log('Tracker v2.0 initialized');
  }

  // ============================================
  // Session Management
  // ============================================

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

  function getSessionState() {
    try {
      var stored = sessionStorage.getItem('_tstate');
      if (stored) return JSON.parse(stored);
    } catch (e) {}
    return { seq: [], items: [], clicks: [], searches: [], startTs: Date.now() };
  }

  function saveSessionState() {
    try {
      sessionStorage.setItem('_tstate', JSON.stringify(sessionState));
    } catch (e) {}
  }

  function addToSequence(type, data) {
    if (type === 'page') {
      sessionState.seq.push(data);
    } else if (type === 'item') {
      if (!sessionState.items.find(function(i) { return i.name === data.name; })) {
        sessionState.items.push(data);
      }
    } else if (type === 'click') {
      sessionState.clicks.push(data);
    }
    saveSessionState();
  }

  function sendSessionData() {
    if (sessionState.seq.length > 1 || sessionState.items.length > 0) {
      track('sequence', {
        pages: sessionState.seq,
        items: sessionState.items,
        clicks: sessionState.clicks,
        duration: Date.now() - sessionState.startTs
      });
    }
  }

  // ============================================
  // Core Tracking
  // ============================================

  // ============================================
  // Experiment Assignments (Phase 7 server-side hookup)
  // ============================================
  //
  // Reads window.Experiments.getAllAssignments() (defined in
  // static/js/experiments.js, loaded earlier in baseof.html) and returns a
  // {experiment_id: variant_id, ...} map for the current user. Returns {}
  // if Experiments isn't loaded, throws, or yields no assignments.
  //
  // The worker side currently ignores event.exp (it stores event.d as JSON
  // and reads only the named top-level fields it knows about). A follow-up
  // PR adds an `experiment_id`/`variant_id` ingestion path so the data
  // attached here actually flows into D1. Until then, this is forward-
  // compat scaffolding -- harmless to current ingestion, immediately
  // useful once the worker side lands.

  function getExperimentAssignments() {
    try {
      var Exp = global.Experiments;
      if (!Exp || typeof Exp.getAllAssignments !== 'function') return {};
      var assignments = Exp.getAllAssignments();
      if (!assignments || typeof assignments !== 'object') return {};
      // Guard against accidental array / non-plain-object returns; we
      // want a string->string dict to match worker schema expectations.
      var out = {};
      for (var key in assignments) {
        if (Object.prototype.hasOwnProperty.call(assignments, key)) {
          var val = assignments[key];
          if (typeof key === 'string' && typeof val === 'string') {
            out[key] = val;
          }
        }
      }
      return out;
    } catch (e) {
      log('getExperimentAssignments failed:', e);
      return {};
    }
  }

  function hasAnyAssignment(map) {
    if (!map) return false;
    for (var k in map) {
      if (Object.prototype.hasOwnProperty.call(map, k)) return true;
    }
    return false;
  }

  function track(type, data) {
    if (!sessionId) return;
    var event = {
      t: type,
      ts: Date.now(),
      sid: sessionId,
      p: location.pathname,
      d: data || {}
    };
    if (userId) event.uid = userId;
    if (sessionNumber) event.sn = sessionNumber;
    if (isReturningUser) event.ret = true;
    if (deviceType) event.dev = deviceType;
    var exp = getExperimentAssignments();
    if (hasAnyAssignment(exp)) event.exp = exp;
    eventQueue.push(event);
    log('Event:', type, data);
    if (eventQueue.length >= BATCH_SIZE) flush();
  }

  function flush(immediate) {
    if (eventQueue.length === 0) return;
    var events = eventQueue.splice(0);
    var payload = JSON.stringify({ v: 2, events: events });
    log('Flushing', events.length, 'events');
    if (immediate && navigator.sendBeacon) {
      navigator.sendBeacon(CONFIG.endpoint, payload);
    } else {
      fetch(CONFIG.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true
      }).catch(function(e) { log('Flush failed:', e); });
    }
  }

  // ============================================
  // Click Tracking with Sequence
  // ============================================

  function initClickTracking() {
    document.addEventListener('click', function(e) {
      var card = e.target.closest('[data-name]');
      if (card) {
        var data = {
          type: 'card',
          name: card.dataset.name,
          section: getSection(card),
          category: card.dataset.category || null
        };
        track('click', data);

        // Add to sequence with source page
        addToSequence('click', {
          from: location.pathname,
          to: card.dataset.name,
          ts: Date.now(),
          el: card.tagName.toLowerCase()
        });
      }

      var link = e.target.closest('a');
      if (link) {
        var href = link.getAttribute('href');
        if (href && link.hostname !== location.hostname) {
          track('click', { type: 'external', url: hash(href), text: truncate(link.textContent, 50) });
        } else if (href && href.startsWith('/')) {
          track('click', { type: 'internal', to: href });
        }
      }
    });
  }

  // ============================================
  // Dwell Time Tracking (per-item)
  // ============================================

  var dwellData = new Map();
  var dwellObserver = null;
  var viewabilityTimers = new Map();
  var impressedItems = new Set();  // Track impressions (dedupe per session)

  function initDwellTracking() {
    if (!('IntersectionObserver' in window)) return;

    dwellObserver = new IntersectionObserver(function(entries) {
      var now = performance.now();
      entries.forEach(function(entry) {
        var el = entry.target;
        var name = el.dataset.name;
        if (!name) return;
        var key = name + '|' + getSection(el);

        if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
          // Start tracking
          if (!dwellData.has(key)) {
            dwellData.set(key, {
              name: name,
              section: getSection(el),
              startTime: now,
              totalVisible: 0,
              viewableStart: null,
              viewableSeconds: 0,
              wordCount: getWordCount(el)
            });
          }
          var data = dwellData.get(key);
          data.startTime = now;

          // IAB viewability: start 1-second timer
          if (!viewabilityTimers.has(key)) {
            viewabilityTimers.set(key, setTimeout(function() {
              var d = dwellData.get(key);
              if (d) d.viewableStart = performance.now();
            }, 1000));
          }

          // Add to item sequence
          addToSequence('item', { name: name, section: getSection(el), ts: Date.now() });

          // Track impression (first time visible per session)
          if (!impressedItems.has(key)) {
            impressedItems.add(key);
            track('impression', {
              name: name,
              section: getSection(el)
            });
          }

        } else if (dwellData.has(key)) {
          // Stop tracking
          var data = dwellData.get(key);
          if (data.startTime) {
            data.totalVisible += now - data.startTime;
            data.startTime = null;
          }
          if (data.viewableStart) {
            data.viewableSeconds += (now - data.viewableStart) / 1000;
            data.viewableStart = null;
          }
          // Clear viewability timer
          clearTimeout(viewabilityTimers.get(key));
          viewabilityTimers.delete(key);
        }
      });
    }, { threshold: [0, 0.5, 1.0] });

    // Handle visibility changes
    document.addEventListener('visibilitychange', function() {
      var now = performance.now();
      dwellData.forEach(function(data, key) {
        if (document.visibilityState === 'hidden') {
          if (data.startTime) {
            data.totalVisible += now - data.startTime;
            data.startTime = null;
          }
          if (data.viewableStart) {
            data.viewableSeconds += (now - data.viewableStart) / 1000;
            data.viewableStart = null;
          }
        } else if (data.startTime === null) {
          data.startTime = now;
        }
      });
    });

    // Observe items
    observeItems();

    // Re-observe on DOM changes
    new MutationObserver(function(mutations) {
      mutations.forEach(function(m) {
        m.addedNodes.forEach(function(node) {
          if (node.nodeType === 1) {
            if (node.dataset && node.dataset.name) dwellObserver.observe(node);
            if (node.querySelectorAll) {
              node.querySelectorAll('[data-name]').forEach(function(el) {
                dwellObserver.observe(el);
              });
            }
          }
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  }

  function observeItems() {
    document.querySelectorAll('[data-name]').forEach(function(el) {
      if (dwellObserver) dwellObserver.observe(el);
    });
  }

  function flushDwellData() {
    var now = performance.now();
    dwellData.forEach(function(data, key) {
      // Finalize timing
      if (data.startTime) {
        data.totalVisible += now - data.startTime;
      }
      if (data.viewableStart) {
        data.viewableSeconds += (now - data.viewableStart) / 1000;
      }

      var dwellMs = Math.round(data.totalVisible);
      if (dwellMs > 1000) { // Only track if >1s
        var readingRatio = data.wordCount > 0
          ? Math.round((dwellMs / 1000) / (data.wordCount / WPM / 60) * 100) / 100
          : null;

        track('dwell', {
          name: data.name,
          section: data.section,
          dwellMs: dwellMs,
          viewableSec: Math.round(data.viewableSeconds * 10) / 10,
          readingRatio: readingRatio
        });
      }
    });
    dwellData.clear();
    viewabilityTimers.forEach(function(t) { clearTimeout(t); });
    viewabilityTimers.clear();
  }

  function getWordCount(el) {
    var text = el.textContent || '';
    return text.split(/\s+/).filter(function(w) { return w.length > 0; }).length;
  }

  // ============================================
  // Scroll Milestones (25/50/75/90%)
  // ============================================

  function initScrollMilestones() {
    var milestones = [25, 50, 75, 90];
    var reached = new Set();

    window.addEventListener('scroll', function() {
      var scrollTop = window.scrollY || document.documentElement.scrollTop;
      var docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) return;

      var depth = Math.round((scrollTop / docHeight) * 100);
      milestones.forEach(function(m) {
        if (depth >= m && !reached.has(m)) {
          reached.add(m);
          track('scroll_milestone', { milestone: m });
        }
      });
    }, { passive: true });
  }

  // ============================================
  // Search Attribution
  // ============================================

  var searchContext = null;

  function initSearchAttribution() {
    // Load existing search context
    try {
      var stored = sessionStorage.getItem('_tsearch');
      if (stored) searchContext = JSON.parse(stored);
    } catch (e) {}

    var debounceTimers = {};

    document.addEventListener('input', function(e) {
      var input = e.target;
      if (!input.matches('input[type="text"], input[type="search"], input:not([type])')) return;
      if (!input.id || !input.id.toLowerCase().includes('search')) return;

      clearTimeout(debounceTimers[input.id]);
      debounceTimers[input.id] = setTimeout(function() {
        var query = input.value.trim();
        if (query.length >= 2) {
          var queryId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
          var isReformulation = searchContext && jaccard(query, searchContext.query) > 0.3;

          var newContext = {
            queryId: queryId,
            query: query.toLowerCase(),
            timestamp: Date.now(),
            prevQueryId: isReformulation ? searchContext.queryId : null
          };

          searchContext = newContext;
          sessionStorage.setItem('_tsearch', JSON.stringify(searchContext));
          sessionState.searches.push({ q: query, qid: queryId, ts: Date.now() });
          saveSessionState();

          track('search', {
            q: query.toLowerCase(),
            qid: queryId,
            reformulation: isReformulation,
            prevQid: isReformulation ? searchContext.prevQueryId : null
          });
        }
      }, 1000);
    });

    // Track search result clicks
    document.addEventListener('click', function(e) {
      if (!searchContext) return;

      var result = e.target.closest('[data-search-position]');
      if (result) {
        var position = parseInt(result.dataset.searchPosition, 10);
        track('search_click', {
          qid: searchContext.queryId,
          position: position,
          resultId: result.dataset.name || result.dataset.resultId || null
        });
      }
    });

    // Detect search abandonment on page leave
    window.addEventListener('beforeunload', function() {
      if (searchContext && Date.now() - searchContext.timestamp < 30000) {
        var scrollDepth = Math.round((window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100) || 0;
        var dwellMs = Date.now() - searchContext.timestamp;

        // Classify abandonment
        var type = 'unknown';
        if (dwellMs > 10000 && scrollDepth > 30) {
          type = 'good'; // Likely found answer in snippets
        } else if (dwellMs < 2000) {
          type = 'bad'; // Quick abandon
        }

        track('search_abandon', {
          qid: searchContext.queryId,
          type: type,
          dwellMs: dwellMs,
          scrollDepth: scrollDepth
        });
      }
    });
  }

  function jaccard(a, b) {
    var setA = new Set(a.toLowerCase().split(/\s+/));
    var setB = new Set(b.toLowerCase().split(/\s+/));
    var intersection = new Set([...setA].filter(function(x) { return setB.has(x); }));
    var union = new Set([...setA, ...setB]);
    return intersection.size / union.size;
  }

  // ============================================
  // Frustration Signals
  // ============================================

  function initFrustrationTracking() {
    var clickTimes = [];
    var lastClickEl = null;
    var pageLoadTime = Date.now();

    // Rage clicks: 3+ clicks on same element within 2 seconds
    document.addEventListener('click', function(e) {
      var now = Date.now();
      var el = e.target;

      if (el === lastClickEl) {
        clickTimes.push(now);
        clickTimes = clickTimes.filter(function(t) { return now - t < 2000; });

        if (clickTimes.length >= 3) {
          track('frustration', {
            type: 'rage_click',
            element: truncate(el.tagName + (el.className ? '.' + el.className.split(' ')[0] : ''), 50)
          });
          clickTimes = [];
        }
      } else {
        lastClickEl = el;
        clickTimes = [now];
      }
    });

    // Quick bounce: <10 seconds with back navigation
    window.addEventListener('popstate', function() {
      if (Date.now() - pageLoadTime < 10000) {
        track('frustration', { type: 'quick_bounce' });
      }
    });
  }

  // ============================================
  // Performance (Web Vitals)
  // ============================================

  function initPerformanceTracking() {
    if (!('PerformanceObserver' in window)) return;

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

  // ============================================
  // Error Tracking
  // ============================================

  function initErrorTracking() {
    window.addEventListener('error', function(e) {
      track('error', {
        type: 'error',
        message: truncate(e.message, 200),
        file: e.filename ? hash(e.filename) : null,
        line: e.lineno,
        stack: e.error && e.error.stack ? truncate(e.error.stack, 500) : null
      });
    });

    window.addEventListener('unhandledrejection', function(e) {
      track('error', {
        type: 'unhandledrejection',
        message: truncate(String(e.reason), 200),
        stack: e.reason && e.reason.stack ? truncate(e.reason.stack, 500) : null
      });
    });
  }

  // ============================================
  // Utilities
  // ============================================

  function getSection(el) {
    var section = el.closest('[data-section-category]');
    if (section) return section.dataset.sectionCategory;
    var path = location.pathname;
    if (path.includes('/packages')) return 'packages';
    if (path.includes('/datasets')) return 'datasets';
    if (path.includes('/learning')) return 'learning';
    if (path.includes('/books')) return 'books';
    if (path.includes('/talks')) return 'talks';
    if (path.includes('/papers')) return 'papers';
    return 'other';
  }

  function getDeviceType() {
    var ua = navigator.userAgent.toLowerCase();
    var width = window.innerWidth || document.documentElement.clientWidth;
    if (/mobile|android|iphone|ipod|blackberry|windows phone/.test(ua) || width < 768) {
      return 'mobile';
    }
    if (/ipad|tablet/.test(ua) || (width >= 768 && width < 1024)) {
      return 'tablet';
    }
    return 'desktop';
  }

  function getReferrerSource() {
    var ref = document.referrer;
    if (!ref) return 'direct';
    try {
      var url = new URL(ref);
      var host = url.hostname.toLowerCase();
      // Search engines
      if (host.includes('google.')) return 'google';
      if (host.includes('bing.')) return 'bing';
      if (host.includes('duckduckgo.')) return 'duckduckgo';
      if (host.includes('yahoo.')) return 'yahoo';
      // Social
      if (host.includes('twitter.') || host.includes('x.com')) return 'twitter';
      if (host.includes('linkedin.')) return 'linkedin';
      if (host.includes('facebook.')) return 'facebook';
      if (host.includes('reddit.')) return 'reddit';
      // Tech communities
      if (host.includes('news.ycombinator.') || host.includes('hacker')) return 'hackernews';
      if (host.includes('lobste.rs')) return 'lobsters';
      if (host.includes('github.')) return 'github';
      if (host.includes('stackoverflow.')) return 'stackoverflow';
      // Self-referral (same domain)
      if (host.includes('tech-econ.com')) return 'internal';
      return 'referral';
    } catch (e) {
      return 'unknown';
    }
  }

  function hash(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) {
      h = ((h << 5) - h) + str.charCodeAt(i);
      h = h & h;
    }
    return h.toString(36);
  }

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
  global.Tracker = {
    track: track,
    flush: flush,
    setSearchResults: function(results) {
      // Call this when showing search results to enable position tracking
      // results = [{id: 'item1', position: 1}, ...]
      if (searchContext) {
        searchContext.results = results;
        sessionStorage.setItem('_tsearch', JSON.stringify(searchContext));
      }
    },
    // Internal: exposed for tests so we can drive these without going through
    // the full track() pipeline. Underscored to signal "not for production
    // callers" -- public callers should use track().
    _getExperimentAssignments: getExperimentAssignments,
    _hasAnyAssignment: hasAnyAssignment
  };

  // Initialize
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})(window);
