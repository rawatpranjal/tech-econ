/**
 * Tech-Econ Analytics Endpoint
 * Cloudflare Worker with D1 database for analytics storage
 */

const ALLOWED_ORIGINS = [
  'https://tech-econ.com',
  'https://www.tech-econ.com',
  'https://rawatpranjal.github.io',
  'http://localhost:1313'
];

const CACHE_TTL = 3600; // 1 hour cache

// Safety limits
const RATE_LIMIT = {
  MAX_REQUESTS_PER_MINUTE: 60,    // Per IP
  MAX_EVENTS_PER_REQUEST: 50,     // Per payload
  MAX_PAYLOAD_SIZE: 50000,        // 50KB
  RETENTION_DAYS: 0               // 0 = keep forever (D1 free tier is 5GB, ~90 years at current rate)
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin');

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return handleCORS(request);
    }

    try {
      // Route: POST /events - Receive events
      if (request.method === 'POST' && (url.pathname === '/events' || url.pathname === '/')) {
        return handleEvents(request, env, ctx, origin);
      }

      // Route: GET /stats - Dashboard summary
      if (request.method === 'GET' && url.pathname === '/stats') {
        return handleStats(request, env, origin);
      }

      // Route: GET /timeseries - Time-series data
      if (request.method === 'GET' && url.pathname === '/timeseries') {
        return handleTimeseries(request, env, origin, url);
      }

      // Route: GET /clicks - Top clicked content
      if (request.method === 'GET' && url.pathname === '/clicks') {
        return handleClicks(request, env, origin, url);
      }

      // Route: GET /searches - Top searches
      if (request.method === 'GET' && url.pathname === '/searches') {
        return handleSearches(request, env, origin, url);
      }

      // Route: GET /export - CSV export
      if (request.method === 'GET' && url.pathname === '/export') {
        return handleExport(request, env, origin, url);
      }

      // Route: GET /cf-stats - Cloudflare analytics
      if (request.method === 'GET' && url.pathname === '/cf-stats') {
        return handleCfStats(request, env, origin);
      }

      // Route: GET /migrate - Migrate KV data to D1 (protected, one-time)
      if (request.method === 'GET' && url.pathname === '/migrate') {
        // Require secret key
        const key = url.searchParams.get('key');
        if (!env.ADMIN_KEY || key !== env.ADMIN_KEY) {
          return new Response('Unauthorized', { status: 401 });
        }
        return handleMigrate(request, env);
      }

      // Route: GET /health - Health check
      if (request.method === 'GET' && url.pathname === '/health') {
        return jsonResponse({
          status: 'ok',
          d1: !!env.DB,
          kv: !!env.ANALYTICS_EVENTS,
          timestamp: Date.now()
        }, null);
      }

      return new Response('Not found', { status: 404 });
    } catch (err) {
      console.error('Worker error:', err);
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};

// ============================================
// POST /events - Receive and store events
// ============================================

async function handleEvents(request, env, ctx, origin) {
  if (!isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';
  const userAgent = request.headers.get('User-Agent') || '';

  try {
    // Check payload size
    const contentLength = parseInt(request.headers.get('Content-Length') || '0', 10);
    if (contentLength > RATE_LIMIT.MAX_PAYLOAD_SIZE) {
      return new Response('Payload too large', { status: 413 });
    }

    // Rate limiting (using D1 with daily-rotating salt for privacy)
    if (env.DB) {
      const isRateLimited = await checkRateLimit(env, clientIP, userAgent);
      if (isRateLimited) {
        return new Response('Rate limit exceeded', { status: 429 });
      }
    }

    const payload = await request.json();

    if (!payload.v || !payload.events || !Array.isArray(payload.events)) {
      return new Response('Invalid payload', { status: 400 });
    }

    // Limit events per request
    const events = payload.events.slice(0, RATE_LIMIT.MAX_EVENTS_PER_REQUEST);

    const country = request.cf?.country || 'unknown';
    const now = Date.now();

    // Process events in background
    ctx.waitUntil(processEvents(env, events, country, now));

    // Periodically clean old events (1% chance per request)
    if (Math.random() < 0.01) {
      ctx.waitUntil(cleanupOldEvents(env));
    }

    return new Response(JSON.stringify({ ok: true, received: events.length }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders(origin)
      }
    });

  } catch (err) {
    console.error('Events error:', err);
    return new Response('Server error', { status: 500 });
  }
}

async function processEvents(env, events, country, receivedAt) {
  // Check if D1 is available
  if (!env.DB) {
    // Fall back to KV if D1 not configured
    if (env.ANALYTICS_EVENTS) {
      const key = `events:${receivedAt}:${crypto.randomUUID()}`;
      await env.ANALYTICS_EVENTS.put(key, JSON.stringify(events.map(e => ({
        ...e,
        _received: receivedAt,
        _country: country
      }))), { expirationTtl: 86400 * 30 });
    }
    return;
  }

  // Insert events into D1
  const insertStmt = env.DB.prepare(`
    INSERT INTO events (type, session_id, path, timestamp, country, data)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  const batch = [];
  const aggregates = {
    pageviews: {},      // date -> count
    clicks: {},         // name:section -> {name, section, category}
    searches: {},       // query -> count
    pages: {},          // path -> count
    hourly: {},         // hour_bucket -> {pageviews, clicks}
    sessions: new Set(),
    engageTimes: []
  };

  for (const event of events) {
    const timestamp = event.ts || receivedAt;
    const date = new Date(timestamp).toISOString().split('T')[0];
    const hourBucket = new Date(timestamp).toISOString().slice(0, 13).replace('T', '-');

    // Insert raw event
    batch.push(insertStmt.bind(
      event.t,
      event.sid || null,
      event.p || event.d?.path || null,
      timestamp,
      country,
      JSON.stringify(event.d || {})
    ));

    // Track session
    if (event.sid) {
      aggregates.sessions.add(event.sid);
    }

    // Aggregate by type
    switch (event.t) {
      case 'pageview':
        aggregates.pageviews[date] = (aggregates.pageviews[date] || 0) + 1;
        aggregates.hourly[hourBucket] = aggregates.hourly[hourBucket] || { pageviews: 0, clicks: 0 };
        aggregates.hourly[hourBucket].pageviews++;
        if (event.d?.path) {
          aggregates.pages[event.d.path] = (aggregates.pages[event.d.path] || 0) + 1;
        }
        break;

      case 'click':
        if (event.d?.type === 'card' && event.d?.name) {
          const key = `${event.d.name}|||${event.d.section || 'other'}`;
          if (!aggregates.clicks[key]) {
            aggregates.clicks[key] = {
              name: event.d.name,
              section: event.d.section || 'other',
              category: event.d.category || null,
              count: 0
            };
          }
          aggregates.clicks[key].count++;
        }
        aggregates.hourly[hourBucket] = aggregates.hourly[hourBucket] || { pageviews: 0, clicks: 0 };
        aggregates.hourly[hourBucket].clicks++;
        break;

      case 'impression':
        if (event.d?.name) {
          const key = `${event.d.name}|||${event.d.section || 'other'}`;
          if (!aggregates.impressions) aggregates.impressions = {};
          if (!aggregates.impressions[key]) {
            aggregates.impressions[key] = {
              name: event.d.name,
              section: event.d.section || 'other',
              count: 0
            };
          }
          aggregates.impressions[key].count++;
        }
        break;

      case 'search':
        if (event.d?.q) {
          const query = event.d.q.toLowerCase().trim();
          aggregates.searches[query] = (aggregates.searches[query] || 0) + 1;
        }
        break;

      case 'engage':
        if (event.d?.timeOnPage) {
          aggregates.engageTimes.push(event.d.timeOnPage);
        }
        break;

      // ML Events
      case 'sequence':
        if (!aggregates.sequences) aggregates.sequences = [];
        aggregates.sequences.push({
          sid: event.sid,
          pages: event.d?.pages || [],
          items: event.d?.items || [],
          clicks: event.d?.clicks || [],
          searches: event.d?.searches || [],
          duration: event.d?.duration || 0
        });
        break;

      case 'dwell':
        if (!aggregates.dwells) aggregates.dwells = [];
        if (event.d?.name) {
          aggregates.dwells.push({
            sid: event.sid,
            name: event.d.name,
            section: event.d.section || 'other',
            dwellMs: event.d.dwellMs || 0,
            viewableSec: event.d.viewableSec || 0,
            readingRatio: event.d.readingRatio || null,
            ts: timestamp
          });
        }
        break;

      case 'scroll_milestone':
        if (!aggregates.milestones) aggregates.milestones = [];
        if (event.d?.milestone) {
          aggregates.milestones.push({
            sid: event.sid,
            path: event.p,
            milestone: event.d.milestone,
            ts: timestamp
          });
        }
        break;

      case 'search_click':
        if (!aggregates.searchClicks) aggregates.searchClicks = [];
        aggregates.searchClicks.push({
          sid: event.sid,
          qid: event.d?.qid,
          position: event.d?.position,
          resultId: event.d?.resultId,
          ts: timestamp
        });
        break;

      case 'search_abandon':
        if (!aggregates.searchAbandons) aggregates.searchAbandons = [];
        aggregates.searchAbandons.push({
          sid: event.sid,
          qid: event.d?.qid,
          type: event.d?.type,
          dwellMs: event.d?.dwellMs,
          scrollDepth: event.d?.scrollDepth,
          ts: timestamp
        });
        break;

      case 'frustration':
        if (!aggregates.frustrations) aggregates.frustrations = [];
        aggregates.frustrations.push({
          sid: event.sid,
          path: event.p,
          type: event.d?.type,
          element: event.d?.element || null,
          ts: timestamp
        });
        break;
    }
  }

  try {
    // Execute batch insert
    if (batch.length > 0) {
      await env.DB.batch(batch);
    }

    // Update aggregates
    await updateAggregates(env, aggregates, country);
  } catch (err) {
    console.error('D1 batch error:', err);
  }
}

async function updateAggregates(env, aggregates, country) {
  const updates = [];

  // Update daily stats
  for (const [date, count] of Object.entries(aggregates.pageviews)) {
    updates.push(env.DB.prepare(`
      INSERT INTO daily_stats (date, pageviews, unique_sessions, updated_at)
      VALUES (?, ?, ?, datetime('now'))
      ON CONFLICT(date) DO UPDATE SET
        pageviews = pageviews + excluded.pageviews,
        unique_sessions = unique_sessions + excluded.unique_sessions,
        updated_at = datetime('now')
    `).bind(date, count, aggregates.sessions.size));
  }

  // Update content clicks (with correct count)
  for (const click of Object.values(aggregates.clicks)) {
    updates.push(env.DB.prepare(`
      INSERT INTO content_clicks (name, section, category, click_count, last_clicked)
      VALUES (?, ?, ?, ?, datetime('now'))
      ON CONFLICT(name, section) DO UPDATE SET
        click_count = click_count + ?,
        last_clicked = datetime('now')
    `).bind(click.name, click.section, click.category, click.count, click.count));
  }

  // Update impressions
  if (aggregates.impressions) {
    for (const imp of Object.values(aggregates.impressions)) {
      updates.push(env.DB.prepare(`
        INSERT INTO content_impressions (name, section, impression_count, last_seen)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(name, section) DO UPDATE SET
          impression_count = impression_count + ?,
          last_seen = datetime('now')
      `).bind(imp.name, imp.section, imp.count, imp.count));
    }
  }

  // Update search queries
  for (const [query, count] of Object.entries(aggregates.searches)) {
    updates.push(env.DB.prepare(`
      INSERT INTO search_queries (query, search_count, last_searched)
      VALUES (?, ?, datetime('now'))
      ON CONFLICT(query) DO UPDATE SET
        search_count = search_count + excluded.search_count,
        last_searched = datetime('now')
    `).bind(query, count));
  }

  // Update page views
  for (const [path, count] of Object.entries(aggregates.pages)) {
    updates.push(env.DB.prepare(`
      INSERT INTO page_views (path, view_count, last_viewed)
      VALUES (?, ?, datetime('now'))
      ON CONFLICT(path) DO UPDATE SET
        view_count = view_count + excluded.view_count,
        last_viewed = datetime('now')
    `).bind(path, count));
  }

  // Update hourly stats
  for (const [bucket, stats] of Object.entries(aggregates.hourly)) {
    updates.push(env.DB.prepare(`
      INSERT INTO hourly_stats (hour_bucket, pageviews, clicks, updated_at)
      VALUES (?, ?, ?, datetime('now'))
      ON CONFLICT(hour_bucket) DO UPDATE SET
        pageviews = pageviews + excluded.pageviews,
        clicks = clicks + excluded.clicks,
        updated_at = datetime('now')
    `).bind(bucket, stats.pageviews, stats.clicks));
  }

  // Update country stats
  if (country && country !== 'unknown') {
    updates.push(env.DB.prepare(`
      INSERT INTO country_stats (country, session_count, last_seen)
      VALUES (?, ?, datetime('now'))
      ON CONFLICT(country) DO UPDATE SET
        session_count = session_count + excluded.session_count,
        last_seen = datetime('now')
    `).bind(country, aggregates.sessions.size));
  }

  // ============================================
  // ML Aggregates
  // ============================================

  // Store session sequences
  if (aggregates.sequences) {
    for (const seq of aggregates.sequences) {
      updates.push(env.DB.prepare(`
        INSERT INTO session_sequences (session_id, page_sequence, click_sequence, item_sequence, search_sequence, duration_ms, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(session_id) DO UPDATE SET
          page_sequence = excluded.page_sequence,
          click_sequence = excluded.click_sequence,
          item_sequence = excluded.item_sequence,
          search_sequence = excluded.search_sequence,
          duration_ms = excluded.duration_ms,
          updated_at = datetime('now')
      `).bind(
        seq.sid,
        JSON.stringify(seq.pages),
        JSON.stringify(seq.clicks),
        JSON.stringify(seq.items),
        JSON.stringify(seq.searches),
        seq.duration
      ));

      // Update session features
      const itemSeq = seq.items.map(i => i.name);
      const engagementTier = seq.duration < 10000 ? 'bounce' :
                             seq.duration < 30000 ? 'skim' :
                             seq.duration < 120000 ? 'read' : 'deep';
      updates.push(env.DB.prepare(`
        INSERT INTO session_features (session_id, pageviews, unique_items, unique_pages, duration_ms, engagement_tier, content_sequence, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(session_id) DO UPDATE SET
          pageviews = excluded.pageviews,
          unique_items = excluded.unique_items,
          unique_pages = excluded.unique_pages,
          duration_ms = excluded.duration_ms,
          engagement_tier = excluded.engagement_tier,
          content_sequence = excluded.content_sequence,
          last_seen = datetime('now')
      `).bind(
        seq.sid,
        seq.pages.length,
        seq.items.length,
        new Set(seq.pages.map(p => p.pid)).size,
        seq.duration,
        engagementTier,
        JSON.stringify(itemSeq)
      ));
    }
  }

  // Store dwell times
  if (aggregates.dwells) {
    for (const dwell of aggregates.dwells) {
      updates.push(env.DB.prepare(`
        INSERT INTO content_dwell (session_id, name, section, dwell_ms, viewable_seconds, reading_ratio, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, name, section) DO UPDATE SET
          dwell_ms = dwell_ms + excluded.dwell_ms,
          viewable_seconds = viewable_seconds + excluded.viewable_seconds,
          reading_ratio = excluded.reading_ratio
      `).bind(dwell.sid, dwell.name, dwell.section, dwell.dwellMs, dwell.viewableSec, dwell.readingRatio, dwell.ts));
    }
  }

  // Store scroll milestones
  if (aggregates.milestones) {
    for (const m of aggregates.milestones) {
      updates.push(env.DB.prepare(`
        INSERT OR IGNORE INTO scroll_milestones (session_id, path, milestone, timestamp)
        VALUES (?, ?, ?, ?)
      `).bind(m.sid, m.path, m.milestone, m.ts));
    }
  }

  // Store search abandonment
  if (aggregates.searchAbandons) {
    for (const sa of aggregates.searchAbandons) {
      updates.push(env.DB.prepare(`
        INSERT INTO search_sessions (session_id, query_id, abandonment_type, dwell_ms, scroll_depth, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(query_id) DO UPDATE SET
          abandonment_type = excluded.abandonment_type,
          dwell_ms = excluded.dwell_ms,
          scroll_depth = excluded.scroll_depth
      `).bind(sa.sid, sa.qid, sa.type, sa.dwellMs, sa.scrollDepth, sa.ts));
    }
  }

  // Store frustration events
  if (aggregates.frustrations) {
    for (const f of aggregates.frustrations) {
      updates.push(env.DB.prepare(`
        INSERT INTO frustration_events (session_id, path, event_type, element, timestamp)
        VALUES (?, ?, ?, ?, ?)
      `).bind(f.sid, f.path, f.type, f.element, f.ts));
    }
  }

  if (updates.length > 0) {
    try {
      await env.DB.batch(updates);
    } catch (err) {
      console.error('Aggregate update error:', err);
    }
  }
}

// ============================================
// GET /stats - Dashboard summary
// ============================================

async function handleStats(request, env, origin) {
  if (origin && !isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  try {
    // Check cache
    const cached = await getCache(env, 'stats');
    if (cached) {
      return jsonResponse({ ...cached, _cached: true }, origin);
    }

    let stats;

    if (env.DB) {
      stats = await getStatsFromD1(env);
    } else if (env.ANALYTICS_EVENTS) {
      stats = await getStatsFromKV(env);
    } else {
      stats = { error: 'No storage configured' };
    }

    // Cache for 1 hour
    await setCache(env, 'stats', stats, CACHE_TTL);

    return jsonResponse(stats, origin);
  } catch (err) {
    console.error('Stats error:', err);
    return jsonResponse({ error: err.message }, origin, 500);
  }
}

async function getStatsFromD1(env) {
  const now = Date.now();
  const sevenDaysAgo = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  // Get summary stats
  const summary = await env.DB.prepare(`
    SELECT
      COALESCE(SUM(pageviews), 0) as pageviews,
      COALESCE(SUM(unique_sessions), 0) as sessions,
      COALESCE(SUM(clicks), 0) as clicks,
      COALESCE(SUM(searches), 0) as searches
    FROM daily_stats
    WHERE date >= ?
  `).bind(sevenDaysAgo).first();

  // Get daily breakdown
  const daily = await env.DB.prepare(`
    SELECT date, pageviews, unique_sessions, clicks
    FROM daily_stats
    WHERE date >= ?
    ORDER BY date ASC
  `).bind(sevenDaysAgo).all();

  // Get top pages
  const topPages = await env.DB.prepare(`
    SELECT path as name, view_count as count
    FROM page_views
    ORDER BY view_count DESC
    LIMIT 10
  `).all();

  // Get top clicks
  const topClicks = await env.DB.prepare(`
    SELECT name, section, category, click_count as count
    FROM content_clicks
    ORDER BY click_count DESC
    LIMIT 20
  `).all();

  // Get top searches
  const topSearches = await env.DB.prepare(`
    SELECT query as name, search_count as count
    FROM search_queries
    ORDER BY search_count DESC
    LIMIT 20
  `).all();

  // Get countries
  const countries = await env.DB.prepare(`
    SELECT country as name, session_count as count
    FROM country_stats
    ORDER BY session_count DESC
    LIMIT 10
  `).all();

  // Get hourly activity (last 24 hours)
  const hourlyActivity = {};
  const hourlyData = await env.DB.prepare(`
    SELECT hour_bucket, pageviews
    FROM hourly_stats
    WHERE hour_bucket >= ?
    ORDER BY hour_bucket ASC
  `).bind(new Date(now - 24 * 60 * 60 * 1000).toISOString().slice(0, 13).replace('T', '-')).all();

  for (const row of hourlyData.results || []) {
    const hour = parseInt(row.hour_bucket.split('-')[3], 10);
    hourlyActivity[hour] = (hourlyActivity[hour] || 0) + row.pageviews;
  }

  // Organize clicks by section
  const clicksBySection = { packages: [], datasets: [], learning: [], other: [] };
  for (const click of (topClicks.results || [])) {
    const section = click.section || 'other';
    const bucket = clicksBySection[section] || clicksBySection.other;
    bucket.push({ name: click.name, count: click.count, category: click.category });
  }

  return {
    updated: now,
    summary: {
      pageviews: summary?.pageviews || 0,
      sessions: summary?.sessions || 0,
      clicks: summary?.clicks || 0,
      searches: summary?.searches || 0,
      avgTimeOnPage: 0 // TODO: calculate from events
    },
    dailyPageviews: Object.fromEntries(
      (daily.results || []).map(r => [r.date, r.pageviews])
    ),
    topPages: topPages.results || [],
    topClicks: clicksBySection,
    topSearches: topSearches.results || [],
    countries: countries.results || [],
    hourlyActivity,
    _source: 'd1'
  };
}

async function getStatsFromKV(env) {
  // Fallback to KV-based stats (existing logic)
  const now = Date.now();
  const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;
  const allEvents = [];
  let cursor = null;
  const MAX_KEYS = 500;
  let totalKeysFetched = 0;

  do {
    const list = await env.ANALYTICS_EVENTS.list({ prefix: 'events:', cursor, limit: 100 });

    for (const key of list.keys) {
      if (totalKeysFetched >= MAX_KEYS) break;
      try {
        const data = await env.ANALYTICS_EVENTS.get(key.name);
        if (data) {
          const events = JSON.parse(data);
          allEvents.push(...events);
        }
        totalKeysFetched++;
      } catch (e) {}
    }

    cursor = list.list_complete ? null : list.cursor;
  } while (cursor && totalKeysFetched < MAX_KEYS);

  const recentEvents = allEvents.filter(e => e.ts >= sevenDaysAgo);
  return aggregateKVEvents(recentEvents, now);
}

function aggregateKVEvents(events, now) {
  const stats = {
    updated: now,
    summary: { pageviews: 0, sessions: new Set(), clicks: 0, searches: 0, avgTimeOnPage: 0 },
    dailyPageviews: {},
    topPages: {},
    topClicks: { packages: {}, datasets: {}, learning: {}, other: {} },
    topSearches: {},
    countries: {},
    hourlyActivity: {},
    _source: 'kv'
  };

  let totalTime = 0, timeCount = 0;

  for (const event of events) {
    if (event.sid) stats.summary.sessions.add(event.sid);

    switch (event.t) {
      case 'pageview':
        stats.summary.pageviews++;
        const day = new Date(event.ts).toISOString().split('T')[0];
        stats.dailyPageviews[day] = (stats.dailyPageviews[day] || 0) + 1;
        if (event.d?.path) {
          stats.topPages[event.d.path] = (stats.topPages[event.d.path] || 0) + 1;
        }
        const hour = new Date(event.ts).getUTCHours();
        stats.hourlyActivity[hour] = (stats.hourlyActivity[hour] || 0) + 1;
        break;

      case 'click':
        stats.summary.clicks++;
        if (event.d?.type === 'card' && event.d?.name) {
          const section = event.d.section || 'other';
          const bucket = stats.topClicks[section] || stats.topClicks.other;
          bucket[event.d.name] = (bucket[event.d.name] || 0) + 1;
        }
        break;

      case 'search':
        stats.summary.searches++;
        if (event.d?.q) {
          stats.topSearches[event.d.q.toLowerCase()] = (stats.topSearches[event.d.q.toLowerCase()] || 0) + 1;
        }
        break;

      case 'engage':
        if (event.d?.timeOnPage) {
          totalTime += event.d.timeOnPage;
          timeCount++;
        }
        break;
    }

    if (event._country && event._country !== 'unknown') {
      stats.countries[event._country] = (stats.countries[event._country] || 0) + 1;
    }
  }

  stats.summary.sessions = stats.summary.sessions.size;
  stats.summary.avgTimeOnPage = timeCount > 0 ? Math.round(totalTime / timeCount) : 0;

  // Convert to arrays
  stats.topPages = sortAndLimit(stats.topPages, 10);
  stats.topSearches = sortAndLimit(stats.topSearches, 20);
  stats.countries = sortAndLimit(stats.countries, 10);
  for (const section of ['packages', 'datasets', 'learning', 'other']) {
    stats.topClicks[section] = sortAndLimit(stats.topClicks[section], 10);
  }

  return stats;
}

// ============================================
// GET /timeseries - Time-series data
// ============================================

async function handleTimeseries(request, env, origin, url) {
  if (origin && !isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  const days = Math.min(parseInt(url.searchParams.get('days') || '7', 10), 90);
  const granularity = url.searchParams.get('granularity') || 'daily'; // daily or hourly

  if (!env.DB) {
    return jsonResponse({ error: 'D1 not configured' }, origin, 500);
  }

  try {
    const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    if (granularity === 'hourly') {
      const hourly = await env.DB.prepare(`
        SELECT hour_bucket, pageviews, clicks
        FROM hourly_stats
        WHERE hour_bucket >= ?
        ORDER BY hour_bucket ASC
      `).bind(startDate.replace(/-/g, '-') + '-00').all();

      return jsonResponse({
        granularity: 'hourly',
        days,
        data: hourly.results || []
      }, origin);
    }

    const daily = await env.DB.prepare(`
      SELECT date, pageviews, unique_sessions as sessions, clicks, searches
      FROM daily_stats
      WHERE date >= ?
      ORDER BY date ASC
    `).bind(startDate).all();

    return jsonResponse({
      granularity: 'daily',
      days,
      data: daily.results || []
    }, origin);

  } catch (err) {
    console.error('Timeseries error:', err);
    return jsonResponse({ error: err.message }, origin, 500);
  }
}

// ============================================
// GET /clicks - Top clicked content
// ============================================

async function handleClicks(request, env, origin, url) {
  if (origin && !isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50', 10), 200);
  const section = url.searchParams.get('section'); // optional filter

  if (!env.DB) {
    return jsonResponse({ error: 'D1 not configured' }, origin, 500);
  }

  try {
    let query = `
      SELECT name, section, category, click_count as count, last_clicked
      FROM content_clicks
    `;
    const params = [];

    if (section) {
      query += ' WHERE section = ?';
      params.push(section);
    }

    query += ' ORDER BY click_count DESC LIMIT ?';
    params.push(limit);

    const clicks = await env.DB.prepare(query).bind(...params).all();

    return jsonResponse({
      total: clicks.results?.length || 0,
      data: clicks.results || []
    }, origin);

  } catch (err) {
    console.error('Clicks error:', err);
    return jsonResponse({ error: err.message }, origin, 500);
  }
}

// ============================================
// GET /searches - Top search queries
// ============================================

async function handleSearches(request, env, origin, url) {
  if (origin && !isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50', 10), 200);

  if (!env.DB) {
    return jsonResponse({ error: 'D1 not configured' }, origin, 500);
  }

  try {
    const searches = await env.DB.prepare(`
      SELECT query, search_count as count, last_searched
      FROM search_queries
      ORDER BY search_count DESC
      LIMIT ?
    `).bind(limit).all();

    return jsonResponse({
      total: searches.results?.length || 0,
      data: searches.results || []
    }, origin);

  } catch (err) {
    console.error('Searches error:', err);
    return jsonResponse({ error: err.message }, origin, 500);
  }
}

// ============================================
// GET /export - CSV export
// ============================================

async function handleExport(request, env, origin, url) {
  if (origin && !isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  const format = url.searchParams.get('format') || 'csv';
  const type = url.searchParams.get('type') || 'events'; // events, clicks, searches, daily
  const days = Math.min(parseInt(url.searchParams.get('days') || '30', 10), 90);

  if (!env.DB) {
    return jsonResponse({ error: 'D1 not configured' }, origin, 500);
  }

  try {
    const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    let data, headers;

    switch (type) {
      case 'clicks':
        const clicks = await env.DB.prepare(`
          SELECT name, section, category, click_count, first_clicked, last_clicked
          FROM content_clicks
          ORDER BY click_count DESC
        `).all();
        data = clicks.results || [];
        headers = ['name', 'section', 'category', 'click_count', 'first_clicked', 'last_clicked'];
        break;

      case 'searches':
        const searches = await env.DB.prepare(`
          SELECT query, search_count, first_searched, last_searched
          FROM search_queries
          ORDER BY search_count DESC
        `).all();
        data = searches.results || [];
        headers = ['query', 'search_count', 'first_searched', 'last_searched'];
        break;

      case 'daily':
        const daily = await env.DB.prepare(`
          SELECT date, pageviews, unique_sessions, clicks, searches
          FROM daily_stats
          WHERE date >= ?
          ORDER BY date ASC
        `).bind(startDate.toISOString().split('T')[0]).all();
        data = daily.results || [];
        headers = ['date', 'pageviews', 'unique_sessions', 'clicks', 'searches'];
        break;

      case 'events':
      default:
        const events = await env.DB.prepare(`
          SELECT type, session_id, path, timestamp, country, data
          FROM events
          WHERE timestamp >= ?
          ORDER BY timestamp DESC
          LIMIT 10000
        `).bind(startDate.getTime()).all();
        data = events.results || [];
        headers = ['type', 'session_id', 'path', 'timestamp', 'country', 'data'];
        break;
    }

    if (format === 'json') {
      return jsonResponse({ type, days, count: data.length, data }, origin);
    }

    // CSV format
    const csv = [
      headers.join(','),
      ...data.map(row => headers.map(h => {
        let val = row[h];
        if (val === null || val === undefined) return '';
        if (typeof val === 'object') val = JSON.stringify(val);
        val = String(val).replace(/"/g, '""');
        return val.includes(',') || val.includes('"') || val.includes('\n') ? `"${val}"` : val;
      }).join(','))
    ].join('\n');

    return new Response(csv, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': `attachment; filename="analytics-${type}-${new Date().toISOString().split('T')[0]}.csv"`,
        ...corsHeaders(origin || '*')
      }
    });

  } catch (err) {
    console.error('Export error:', err);
    return jsonResponse({ error: err.message }, origin, 500);
  }
}

// ============================================
// GET /cf-stats - Cloudflare Analytics
// ============================================

async function handleCfStats(request, env, origin) {
  if (origin && !isAllowedOrigin(origin)) {
    return new Response('Forbidden', { status: 403 });
  }

  // Check cache
  const cached = await getCache(env, 'cf-stats');
  if (cached) {
    return jsonResponse({ ...cached, _cached: true }, origin);
  }

  if (!env.CF_API_TOKEN || !env.CF_ZONE_ID) {
    return jsonResponse({
      error: 'Cloudflare API not configured',
      minVisitors: 11,
      maxVisitors: 37,
      _fallback: true
    }, origin);
  }

  try {
    const now = Date.now();
    const yesterday = new Date(now - 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const today = new Date(now).toISOString().split('T')[0];

    const query = `
      query {
        viewer {
          zones(filter: { zoneTag: "${env.CF_ZONE_ID}" }) {
            httpRequests1hGroups(
              limit: 24
              filter: { date_geq: "${yesterday}", date_leq: "${today}" }
            ) {
              dimensions { datetime }
              uniq { uniques }
            }
          }
        }
      }
    `;

    const response = await fetch('https://api.cloudflare.com/client/v4/graphql', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.CF_API_TOKEN}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query })
    });

    if (!response.ok) {
      throw new Error(`Cloudflare API error: ${response.status}`);
    }

    const result = await response.json();
    const hourlyData = result?.data?.viewer?.zones?.[0]?.httpRequests1hGroups || [];
    const uniqueCounts = hourlyData.map(h => h.uniq?.uniques || 0).filter(n => n > 0);

    const stats = {
      minVisitors: uniqueCounts.length > 0 ? Math.min(...uniqueCounts) : 11,
      maxVisitors: uniqueCounts.length > 0 ? Math.max(...uniqueCounts) : 37,
      avgVisitors: uniqueCounts.length > 0 ? Math.round(uniqueCounts.reduce((a, b) => a + b, 0) / uniqueCounts.length) : 20,
      hoursAnalyzed: uniqueCounts.length,
      updated: now
    };

    await setCache(env, 'cf-stats', stats, CACHE_TTL);
    return jsonResponse(stats, origin);

  } catch (err) {
    console.error('CF Stats error:', err);
    return jsonResponse({
      error: err.message,
      minVisitors: 11,
      maxVisitors: 37,
      _fallback: true
    }, origin);
  }
}

// ============================================
// GET /migrate - One-time KV to D1 migration
// ============================================

async function handleMigrate(request, env) {
  if (!env.ANALYTICS_EVENTS || !env.DB) {
    return jsonResponse({ error: 'Both KV and D1 must be configured' }, null, 500);
  }

  const url = new URL(request.url);
  const limit = parseInt(url.searchParams.get('limit') || '50', 10);
  const cursor = url.searchParams.get('cursor') || null;

  const stats = {
    keysProcessed: 0,
    totalEvents: 0,
    clicksUpserted: 0,
    searchesUpserted: 0,
    pagesUpserted: 0,
    dailyUpserted: 0,
    nextCursor: null,
    errors: []
  };

  try {
    // Fetch a batch of event keys from KV
    const allEvents = [];
    const list = await env.ANALYTICS_EVENTS.list({ prefix: 'events:', cursor, limit });

    for (const key of list.keys) {
      try {
        const data = await env.ANALYTICS_EVENTS.get(key.name);
        if (data) {
          const events = JSON.parse(data);
          allEvents.push(...events);
          stats.keysProcessed++;
        }
      } catch (e) {
        stats.errors.push(`Key ${key.name}: ${e.message}`);
      }
    }

    stats.nextCursor = list.list_complete ? null : list.cursor;

    // Aggregation maps
    const clicks = {};
    const searches = {};
    const pages = {};
    const daily = {};
    const hourly = {};
    const countries = {};
    const sessions = new Set();

    // Process events
    for (const event of allEvents) {
      const timestamp = event.ts || event._received || Date.now();
      const date = new Date(timestamp).toISOString().split('T')[0];
      const hourBucket = new Date(timestamp).toISOString().slice(0, 13).replace('T', '-');
      const country = event._country || 'unknown';

      if (event.sid) sessions.add(event.sid);

      if (!daily[date]) {
        daily[date] = { pageviews: 0, sessions: new Set(), clicks: 0, searches: 0 };
      }
      if (event.sid) daily[date].sessions.add(event.sid);

      if (!hourly[hourBucket]) {
        hourly[hourBucket] = { pageviews: 0, clicks: 0 };
      }

      if (country !== 'unknown' && event.sid) {
        countries[country] = countries[country] || new Set();
        countries[country].add(event.sid);
      }

      switch (event.t) {
        case 'pageview':
          daily[date].pageviews++;
          hourly[hourBucket].pageviews++;
          if (event.d?.path || event.p) {
            const path = event.d?.path || event.p;
            pages[path] = (pages[path] || 0) + 1;
          }
          break;

        case 'click':
          daily[date].clicks++;
          hourly[hourBucket].clicks++;
          if (event.d?.type === 'card' && event.d?.name) {
            const key = `${event.d.name}|||${event.d.section || 'other'}`;
            if (!clicks[key]) {
              clicks[key] = {
                name: event.d.name,
                section: event.d.section || 'other',
                category: event.d.category || null,
                count: 0
              };
            }
            clicks[key].count++;
          }
          break;

        case 'search':
          daily[date].searches++;
          if (event.d?.q) {
            const query = event.d.q.toLowerCase().trim();
            searches[query] = (searches[query] || 0) + 1;
          }
          break;
      }
    }

    // Build batch inserts
    const batch = [];

    for (const [date, data] of Object.entries(daily)) {
      batch.push(env.DB.prepare(`
        INSERT INTO daily_stats (date, pageviews, unique_sessions, clicks, searches, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(date) DO UPDATE SET
          pageviews = pageviews + excluded.pageviews,
          unique_sessions = excluded.unique_sessions,
          clicks = clicks + excluded.clicks,
          searches = searches + excluded.searches
      `).bind(date, data.pageviews, data.sessions.size, data.clicks, data.searches));
      stats.dailyUpserted++;
    }

    for (const click of Object.values(clicks)) {
      batch.push(env.DB.prepare(`
        INSERT INTO content_clicks (name, section, category, click_count, last_clicked)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(name, section) DO UPDATE SET
          click_count = click_count + excluded.click_count,
          last_clicked = datetime('now')
      `).bind(click.name, click.section, click.category, click.count));
      stats.clicksUpserted++;
    }

    for (const [query, count] of Object.entries(searches)) {
      batch.push(env.DB.prepare(`
        INSERT INTO search_queries (query, search_count, last_searched)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(query) DO UPDATE SET
          search_count = search_count + excluded.search_count
      `).bind(query, count));
      stats.searchesUpserted++;
    }

    for (const [path, count] of Object.entries(pages)) {
      batch.push(env.DB.prepare(`
        INSERT INTO page_views (path, view_count, last_viewed)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(path) DO UPDATE SET
          view_count = view_count + excluded.view_count
      `).bind(path, count));
      stats.pagesUpserted++;
    }

    for (const [bucket, data] of Object.entries(hourly)) {
      batch.push(env.DB.prepare(`
        INSERT INTO hourly_stats (hour_bucket, pageviews, clicks, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(hour_bucket) DO UPDATE SET
          pageviews = pageviews + excluded.pageviews,
          clicks = clicks + excluded.clicks
      `).bind(bucket, data.pageviews, data.clicks));
    }

    for (const [country, sessionSet] of Object.entries(countries)) {
      batch.push(env.DB.prepare(`
        INSERT INTO country_stats (country, session_count, last_seen)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(country) DO UPDATE SET
          session_count = session_count + excluded.session_count
      `).bind(country, sessionSet.size));
    }

    // Execute in batches
    const BATCH_SIZE = 50;
    for (let i = 0; i < batch.length; i += BATCH_SIZE) {
      await env.DB.batch(batch.slice(i, i + BATCH_SIZE));
    }

    // Clear cache
    await env.DB.prepare("DELETE FROM cache_meta WHERE key = 'stats'").run();

    stats.totalEvents = allEvents.length;
    stats.totalSessions = sessions.size;
    stats.success = true;

    return jsonResponse(stats, null);

  } catch (err) {
    stats.error = err.message;
    stats.success = false;
    return jsonResponse(stats, null, 500);
  }
}

// ============================================
// Rate Limiting & Cleanup
// ============================================

async function checkRateLimit(env, clientIP, userAgent) {
  if (!env.DB) return false;

  const now = Date.now();
  // Use daily-rotating salt for privacy-preserving IP hash
  const ipHash = await hashIPWithSalt(env, clientIP, userAgent);

  try {
    // Store and increment request count
    await env.DB.prepare(`
      INSERT INTO cache_meta (key, value, expires_at)
      VALUES (?, ?, ?)
      ON CONFLICT(key) DO UPDATE SET
        value = CAST(CAST(value AS INTEGER) + 1 AS TEXT),
        expires_at = CASE WHEN expires_at < ? THEN ? ELSE expires_at END
    `).bind(`ratelimit:${ipHash}`, '1', now + 60000, now, now + 60000).run();

    // Check rate limit from cache
    const cached = await env.DB.prepare(
      'SELECT value FROM cache_meta WHERE key = ? AND expires_at > ?'
    ).bind(`ratelimit:${ipHash}`, now).first();

    const requestCount = parseInt(cached?.value || '0', 10);
    return requestCount > RATE_LIMIT.MAX_REQUESTS_PER_MINUTE;

  } catch (err) {
    console.error('Rate limit check error:', err);
    return false; // Fail open
  }
}

// Daily rotating salt for privacy-preserving IP hashing
let dailySaltCache = { date: null, salt: null };

async function getDailySalt(env) {
  const today = new Date().toISOString().split('T')[0];

  // Use cached salt if still today
  if (dailySaltCache.date === today && dailySaltCache.salt) {
    return dailySaltCache.salt;
  }

  try {
    // Try to get existing salt for today
    const existing = await env.DB.prepare(
      'SELECT salt FROM daily_salts WHERE date = ?'
    ).bind(today).first();

    if (existing?.salt) {
      dailySaltCache = { date: today, salt: existing.salt };
      return existing.salt;
    }

    // Generate new salt for today
    const salt = crypto.randomUUID() + crypto.randomUUID();
    await env.DB.prepare(
      'INSERT OR IGNORE INTO daily_salts (date, salt) VALUES (?, ?)'
    ).bind(today, salt).run();

    // Delete old salts (privacy requirement: don't keep historical salts)
    await env.DB.prepare(
      'DELETE FROM daily_salts WHERE date < ?'
    ).bind(today).run();

    dailySaltCache = { date: today, salt };
    return salt;

  } catch (err) {
    console.error('Daily salt error:', err);
    // Fallback to in-memory salt (still rotates daily via cache)
    if (!dailySaltCache.salt || dailySaltCache.date !== today) {
      dailySaltCache = { date: today, salt: crypto.randomUUID() };
    }
    return dailySaltCache.salt;
  }
}

async function hashIPWithSalt(env, ip, userAgent) {
  const salt = await getDailySalt(env);
  const domain = 'tech-econ.com';
  const data = `${salt}|${domain}|${ip}|${userAgent || ''}`;

  // Use Web Crypto API for secure hashing
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);
  const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.slice(0, 8).map(b => b.toString(16).padStart(2, '0')).join('');
}

function hashIP(ip) {
  // Fallback simple hash (used when async not available)
  let hash = 0;
  for (let i = 0; i < ip.length; i++) {
    hash = ((hash << 5) - hash) + ip.charCodeAt(i);
    hash = hash & hash;
  }
  return hash.toString(36);
}

async function cleanupOldEvents(env) {
  if (!env.DB) return;

  try {
    // Only delete old events if retention is configured
    if (RATE_LIMIT.RETENTION_DAYS > 0) {
      const cutoff = Date.now() - (RATE_LIMIT.RETENTION_DAYS * 24 * 60 * 60 * 1000);
      const result = await env.DB.prepare(`
        DELETE FROM events WHERE timestamp < ?
      `).bind(cutoff).run();
      console.log(`Cleanup: deleted ${result.meta?.changes || 0} old events`);
    }

    // Always clean expired cache/rate-limit entries
    await env.DB.prepare(`
      DELETE FROM cache_meta WHERE expires_at < ?
    `).bind(Date.now()).run();

  } catch (err) {
    console.error('Cleanup error:', err);
  }
}

// ============================================
// Cache Helpers
// ============================================

async function getCache(env, key) {
  if (env.DB) {
    try {
      const row = await env.DB.prepare(
        'SELECT value, expires_at FROM cache_meta WHERE key = ?'
      ).bind(key).first();

      if (row && row.expires_at > Date.now()) {
        return JSON.parse(row.value);
      }
    } catch (e) {}
  }

  if (env.ANALYTICS_EVENTS) {
    try {
      const cached = await env.ANALYTICS_EVENTS.get(`cache:${key}`);
      if (cached) {
        const { data, ts } = JSON.parse(cached);
        if (Date.now() - ts < CACHE_TTL * 1000) {
          return data;
        }
      }
    } catch (e) {}
  }

  return null;
}

async function setCache(env, key, data, ttl) {
  const expiresAt = Date.now() + ttl * 1000;

  if (env.DB) {
    try {
      await env.DB.prepare(`
        INSERT INTO cache_meta (key, value, expires_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, expires_at = excluded.expires_at
      `).bind(key, JSON.stringify(data), expiresAt).run();
    } catch (e) {}
  }

  if (env.ANALYTICS_EVENTS) {
    try {
      await env.ANALYTICS_EVENTS.put(`cache:${key}`, JSON.stringify({ data, ts: Date.now() }), { expirationTtl: ttl });
    } catch (e) {}
  }
}

// ============================================
// Utility Functions
// ============================================

function sortAndLimit(obj, limit) {
  return Object.entries(obj)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

function jsonResponse(data, origin, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300',
      ...corsHeaders(origin || '*')
    }
  });
}

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
