/**
 * Tech-Econ Analytics Endpoint
 * Cloudflare Worker for receiving and aggregating analytics events
 */

const ALLOWED_ORIGINS = [
  'https://tech-econ.com',
  'https://www.tech-econ.com',
  'https://rawatpranjal.github.io',
  'http://localhost:1313'
];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin');

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return handleCORS(request);
    }

    // Route: GET /stats - Return aggregated analytics
    if (request.method === 'GET' && url.pathname === '/stats') {
      return handleStats(request, env, origin);
    }

    // Route: POST /events - Receive events
    if (request.method === 'POST' && (url.pathname === '/events' || url.pathname === '/')) {
      return handleEvents(request, env, ctx, origin);
    }

    return new Response('Not found', { status: 404 });
  }
};

// ============================================
// POST /events - Receive and store events
// ============================================

async function handleEvents(request, env, ctx, origin) {
  if (!isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  try {
    const payload = await request.json();

    if (!payload.v || !payload.events || !Array.isArray(payload.events)) {
      return new Response('Invalid payload', { status: 400 });
    }

    const enrichedEvents = payload.events.map(event => ({
      ...event,
      _received: Date.now(),
      _country: request.cf?.country || 'unknown'
    }));

    const key = `events:${Date.now()}:${crypto.randomUUID()}`;
    ctx.waitUntil(
      env.ANALYTICS_EVENTS.put(key, JSON.stringify(enrichedEvents), {
        expirationTtl: 86400 * 30
      })
    );

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders(origin)
      }
    });

  } catch (err) {
    console.error('Analytics error:', err);
    return new Response('Server error', { status: 500 });
  }
}

// ============================================
// GET /stats - Return aggregated statistics
// ============================================

async function handleStats(request, env, origin) {
  // Allow stats from allowed origins or no origin (direct access)
  if (origin && !isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  const CACHE_KEY = 'stats:cached';
  const CACHE_TTL = 1800; // 30 minutes

  try {
    const now = Date.now();

    // Check cache first
    const cached = await env.ANALYTICS_EVENTS.get(CACHE_KEY);
    if (cached) {
      try {
        const { data, ts } = JSON.parse(cached);
        if (now - ts < CACHE_TTL * 1000) {
          // Cache hit - return cached data
          return new Response(JSON.stringify({ ...data, _cached: true }), {
            status: 200,
            headers: {
              'Content-Type': 'application/json',
              'Cache-Control': 'public, max-age=1800',
              ...corsHeaders(origin || '*')
            }
          });
        }
      } catch (e) {
        // Invalid cache, continue to regenerate
      }
    }

    // Cache miss or stale - fetch and aggregate
    const sevenDaysAgo = now - (7 * 24 * 60 * 60 * 1000);
    const allEvents = [];
    let cursor = null;

    do {
      const list = await env.ANALYTICS_EVENTS.list({ prefix: 'events:', cursor, limit: 1000 });

      // Fetch all keys in parallel (batch of 50 to avoid overwhelming)
      const BATCH_SIZE = 50;
      for (let i = 0; i < list.keys.length; i += BATCH_SIZE) {
        const batch = list.keys.slice(i, i + BATCH_SIZE);
        const results = await Promise.all(
          batch.map(key => env.ANALYTICS_EVENTS.get(key.name))
        );

        for (const data of results) {
          if (data) {
            try {
              const events = JSON.parse(data);
              allEvents.push(...events);
            } catch (e) {}
          }
        }
      }

      cursor = list.list_complete ? null : list.cursor;
    } while (cursor);

    // Filter to recent events
    const recentEvents = allEvents.filter(e => e.ts >= sevenDaysAgo);

    // Aggregate statistics
    const stats = aggregateEvents(recentEvents, now);

    // Store in cache
    await env.ANALYTICS_EVENTS.put(CACHE_KEY, JSON.stringify({
      data: stats,
      ts: now
    }), { expirationTtl: CACHE_TTL });

    return new Response(JSON.stringify(stats), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=1800',
        ...corsHeaders(origin || '*')
      }
    });

  } catch (err) {
    console.error('Stats error:', err);
    return new Response(JSON.stringify({ error: 'Failed to fetch stats' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// ============================================
// Aggregation Logic
// ============================================

function aggregateEvents(events, now) {
  const stats = {
    updated: now,
    totalEvents: events.length,
    summary: {
      pageviews: 0,
      sessions: new Set(),
      searches: 0,
      clicks: 0,
      avgTimeOnPage: 0
    },
    topSearches: {},
    topPages: {},
    topClicks: {
      packages: {},
      datasets: {},
      learning: {},
      other: {}
    },
    externalLinks: {},  // Track external link clicks
    hourlyActivity: {},  // Track activity by hour (0-23)
    dailyPageviews: {},
    countries: {},
    _countryBySid: {},  // Track unique country+session pairs
    performance: {
      lcp: [],
      fid: [],
      cls: []
    }
  };

  let totalTimeOnPage = 0;
  let timeOnPageCount = 0;

  for (const event of events) {
    // Count sessions
    if (event.sid) {
      stats.summary.sessions.add(event.sid);
    }

    // Count by type
    switch (event.t) {
      case 'pageview':
        stats.summary.pageviews++;

        // Daily pageviews
        const day = new Date(event.ts).toISOString().split('T')[0];
        stats.dailyPageviews[day] = (stats.dailyPageviews[day] || 0) + 1;

        // Top pages
        if (event.d?.path) {
          stats.topPages[event.d.path] = (stats.topPages[event.d.path] || 0) + 1;
        }
        break;

      case 'search':
        stats.summary.searches++;
        if (event.d?.q) {
          const query = event.d.q.toLowerCase().trim();
          stats.topSearches[query] = (stats.topSearches[query] || 0) + 1;
        }
        break;

      case 'click':
        stats.summary.clicks++;
        if (event.d?.type === 'card' && event.d?.name) {
          const section = event.d.section || 'other';
          const bucket = stats.topClicks[section] || stats.topClicks.other;
          bucket[event.d.name] = (bucket[event.d.name] || 0) + 1;
        }
        // Track external link clicks
        if (event.d?.type === 'external' && event.d?.text) {
          const linkText = event.d.text.trim().toLowerCase();
          if (linkText) {
            stats.externalLinks[linkText] = (stats.externalLinks[linkText] || 0) + 1;
          }
        }
        break;

      case 'engage':
        if (event.d?.timeOnPage) {
          totalTimeOnPage += event.d.timeOnPage;
          timeOnPageCount++;
        }
        break;

      case 'vitals':
        if (event.d?.metric && event.d?.value !== undefined) {
          const metric = event.d.metric.toLowerCase();
          if (stats.performance[metric]) {
            stats.performance[metric].push(event.d.value);
          }
        }
        break;
    }

    // Countries (count by unique session, not every event)
    if (event._country && event._country !== 'unknown' && event.sid) {
      const key = `${event._country}:${event.sid}`;
      if (!stats._countryBySid[key]) {
        stats._countryBySid[key] = true;
        stats.countries[event._country] = (stats.countries[event._country] || 0) + 1;
      }
    }

    // Track hourly activity (for pageviews only)
    if (event.t === 'pageview' && event.ts) {
      const hour = new Date(event.ts).getUTCHours();
      stats.hourlyActivity[hour] = (stats.hourlyActivity[hour] || 0) + 1;
    }
  }

  // Calculate averages
  stats.summary.sessions = stats.summary.sessions.size;
  stats.summary.avgTimeOnPage = timeOnPageCount > 0
    ? Math.round(totalTimeOnPage / timeOnPageCount)
    : 0;

  // Sort and limit top items
  stats.topSearches = sortAndLimit(stats.topSearches, 20);
  stats.topPages = sortAndLimit(stats.topPages, 10);
  stats.topClicks.packages = sortAndLimit(stats.topClicks.packages, 10);
  stats.topClicks.datasets = sortAndLimit(stats.topClicks.datasets, 10);
  stats.topClicks.learning = sortAndLimit(stats.topClicks.learning, 10);
  stats.externalLinks = sortAndLimit(stats.externalLinks, 10);
  stats.countries = sortAndLimit(stats.countries, 10);

  // Calculate performance averages
  for (const metric of ['lcp', 'fid', 'cls']) {
    const values = stats.performance[metric];
    if (values.length > 0) {
      const avg = values.reduce((a, b) => a + b, 0) / values.length;
      stats.performance[metric] = {
        avg: Math.round(avg * 100) / 100,
        samples: values.length
      };
    } else {
      stats.performance[metric] = { avg: null, samples: 0 };
    }
  }

  // Sort daily pageviews by date
  const sortedDaily = Object.entries(stats.dailyPageviews)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-7);
  stats.dailyPageviews = Object.fromEntries(sortedDaily);

  // Remove helper properties
  delete stats._countryBySid;

  return stats;
}

function sortAndLimit(obj, limit) {
  return Object.entries(obj)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

// ============================================
// CORS Helpers
// ============================================

function isAllowedOrigin(origin) {
  if (!origin) return false;
  return ALLOWED_ORIGINS.some(allowed => origin.startsWith(allowed));
}

function handleCORS(request) {
  const origin = request.headers.get('Origin');
  if (!isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  return new Response(null, {
    status: 204,
    headers: {
      ...corsHeaders(origin),
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400'
    }
  });
}

function corsHeaders(origin) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Credentials': 'false'
  };
}
