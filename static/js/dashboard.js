/**
 * dashboard.js — Live Dashboard for tech-econ.com
 *
 * One fetch per tab, lazy-loaded on tab switch.
 * Results cached in memory so re-switching is instant.
 * Falls back to an error + retry button on any network failure.
 */

const WORKER = 'https://tech-econ-analytics-v2.pp712.workers.dev';

// In-memory cache: endpoint string -> parsed JSON data
const _cache = {};

/**
 * fetchAndRender
 * Fetches endpoint, calls renderFn(data) -> HTML string, mounts into mountSel.
 * Caches by endpoint so re-switching tabs does not re-fetch.
 */
async function fetchAndRender(endpoint, renderFn, mountSel) {
  const mount = document.querySelector(mountSel);
  if (!mount) return;

  if (_cache[endpoint] !== undefined) {
    mount.innerHTML = renderFn(_cache[endpoint]);
    return;
  }

  mount.innerHTML = skeletonHTML(3);

  try {
    const res = await fetch(`${WORKER}${endpoint}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _cache[endpoint] = data;
    mount.innerHTML = renderFn(data);
  } catch (err) {
    mount.innerHTML = `<div class="dashboard-error">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      Could not load live data.
      <button type="button" class="dashboard-retry-btn">Retry</button>
    </div>`;
    const btn = mount.querySelector('.dashboard-retry-btn');
    if (btn) btn.addEventListener('click', () => fetchAndRender(endpoint, renderFn, mountSel));
  }
}

/* ============================================================
   Helpers
   ============================================================ */

/**
 * Returns a CSS-only animated skeleton placeholder with n rows.
 * Replaces "Loading..." text with a visually clear loading state.
 */
function skeletonHTML(n) {
  const rows = Array.from({ length: n }, function () {
    return '<div class="skel-row"></div>';
  }).join('');
  return '<div class="dashboard-skeleton">' + rows + '</div>';
}

function fmtNum(n) {
  if (n === null || n === undefined) return '--';
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

function pct(a, b) {
  if (!b) return '0%';
  return Math.round((a / b) * 100) + '%';
}

/* ============================================================
   TAB 1: Traffic
   Endpoints: /stats, /timeseries?days=30, /health
   ============================================================ */

async function loadTraffic() {
  const mount = document.querySelector('#dash-traffic-content');
  if (!mount) return;

  // Show skeleton immediately
  mount.innerHTML = skeletonHTML(3);

  // Fetch all three endpoints in parallel, fail gracefully per-call
  const [statsResult, timeseriesResult, healthResult] = await Promise.allSettled([
    fetchJSON('/stats'),
    fetchJSON('/timeseries?days=30'),
    fetchJSON('/health'),
  ]);

  const stats     = statsResult.status     === 'fulfilled' ? statsResult.value     : null;
  const timeseries = timeseriesResult.status === 'fulfilled' ? timeseriesResult.value : null;
  const health    = healthResult.status    === 'fulfilled' ? healthResult.value    : null;

  mount.innerHTML = renderTraffic(stats, timeseries, health);
}

async function fetchJSON(endpoint) {
  if (_cache[endpoint] !== undefined) return _cache[endpoint];
  const res = await fetch(`${WORKER}${endpoint}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  _cache[endpoint] = data;
  return data;
}

function renderTraffic(stats, timeseries, health) {
  // Health pill
  let healthPill = '<span class="dashboard-health-pill stat-unknown">Unknown</span>';
  if (health) {
    const isHealthy = health.status === 'ok'
      && (health.last_write_age_seconds === null || health.last_write_age_seconds < 86400);
    if (isHealthy) {
      healthPill = '<span class="dashboard-health-pill stat-positive">Healthy</span>';
    } else {
      healthPill = '<span class="dashboard-health-pill stat-warning">Degraded</span>';
    }
  }

  // Today's metrics come from the latest entry in /timeseries (the worker
  // doesn't expose dedicated today_* fields on /stats).
  const tsArr = timeseries && Array.isArray(timeseries.data) ? timeseries.data : [];
  const today = tsArr.length ? tsArr[tsArr.length - 1] : null;
  const pageviewsToday = today ? fmtNum(today.pageviews ?? 0) : '--';
  const sessionsToday  = today ? fmtNum(today.sessions  ?? 0) : '--';
  const clicksToday    = today ? fmtNum(today.clicks    ?? 0) : '--';
  const events24h      = health ? fmtNum(health.events_24h) : '--';

  let cards = `
    <div class="dashboard-stat-grid">
      <div class="dashboard-stat-card stat-positive">
        <div class="dashboard-stat-num">${pageviewsToday}</div>
        <div class="dashboard-stat-label">Pageviews today</div>
      </div>
      <div class="dashboard-stat-card">
        <div class="dashboard-stat-num">${sessionsToday}</div>
        <div class="dashboard-stat-label">Sessions today</div>
      </div>
      <div class="dashboard-stat-card">
        <div class="dashboard-stat-num">${clicksToday}</div>
        <div class="dashboard-stat-label">Clicks today</div>
      </div>
      <div class="dashboard-stat-card">
        <div class="dashboard-stat-num">${events24h}</div>
        <div class="dashboard-stat-label">Events (24h) ${healthPill}</div>
      </div>
    </div>`;

  // 30-day bar chart
  let chart = '';
  if (timeseries && timeseries.data && timeseries.data.length > 0) {
    const days = timeseries.data;
    const eventCount = d => (d.pageviews ?? 0) + (d.clicks ?? 0) + (d.searches ?? 0);
    const maxVal = Math.max(...days.map(eventCount), 1);
    const bars = days.map(d => {
      const count = eventCount(d);
      const heightPct = Math.max(2, Math.round((count / maxVal) * 100));
      const dateLabel = d.date || d.day || '';
      return `<div class="dashboard-bar" style="height:${heightPct}%" title="${dateLabel}: ${count} events" data-count="${count}" data-date="${dateLabel}"></div>`;
    }).join('');

    chart = `
      <div class="dashboard-chart-section">
        <h3 class="dashboard-section-title">30-day event volume</h3>
        <div class="dashboard-bar-chart" role="img" aria-label="30-day daily event bar chart">
          <div class="dashboard-bars">${bars}</div>
          <div class="dashboard-bar-baseline"></div>
        </div>
        <p class="dashboard-chart-note">Each bar = one day. Hover for date and count.</p>
      </div>`;
  } else {
    chart = `<div class="dashboard-empty">30-day timeseries not available.</div>`;
  }

  // What this means
  const prose = `
    <div class="dashboard-prose">
      <p>Events include page views, card clicks, search queries, and engagement signals (scroll depth, dwell time). Sessions group events from the same browser tab in a short window. Healthy write-side means the analytics pipeline accepted events in the last 24 hours without errors.</p>
    </div>`;

  return cards + chart + prose;
}

/* ============================================================
   TAB 2: Top Content
   Endpoint: /clicks?limit=50
   ============================================================ */

function loadTopContent() {
  fetchAndRender('/clicks?limit=50', renderTopContent, '#dash-content-content');
}

function renderTopContent(data) {
  const items = Array.isArray(data) ? data : (data.data || data.clicks || data.items || []);

  if (!Array.isArray(items) || items.length === 0) {
    return '<div class="dashboard-empty">No click data available yet.</div>';
  }

  // Content-type filter values from the data
  const types = [...new Set(items.map(i => i.section || i.type || 'other').filter(Boolean))].sort();
  const totalClicks = items.reduce((s, i) => s + (i.click_count || i.clicks || 0), 0);
  const top20Clicks = items.slice(0, 20).reduce((s, i) => s + (i.click_count || i.clicks || 0), 0);
  const top20Pct = pct(top20Clicks, totalClicks);

  const typeOptions = types.map(t => `<option value="${t}">${t}</option>`).join('');

  const rows = items.slice(0, 50).map((item, idx) => {
    const name    = item.name || item.item || 'Unknown';
    const section = item.section || item.type || 'other';
    const clicks  = item.click_count || item.clicks || 0;
    return `<tr class="dashboard-content-row" data-section="${section}">
      <td class="dashboard-rank">${idx + 1}</td>
      <td class="dashboard-item-name">${escHtml(name)}</td>
      <td><span class="dashboard-type-pill">${escHtml(section)}</span></td>
      <td class="dashboard-click-count">${fmtNum(clicks)}</td>
    </tr>`;
  }).join('');

  const longtail = `
    <div class="dashboard-callout">
      Top 20 items account for <strong>${top20Pct}</strong> of all ${fmtNum(totalClicks)} tracked clicks. The rest is long tail.
    </div>`;

  const filters = types.length > 1 ? `
    <div class="dashboard-filter-bar">
      <label for="content-type-filter">Filter by type:</label>
      <select id="content-type-filter" onchange="filterContentRows(this.value)">
        <option value="">All</option>
        ${typeOptions}
      </select>
    </div>` : '';

  const table = `
    <table class="dashboard-ranked-list">
      <thead><tr><th>#</th><th>Item</th><th>Type</th><th>Clicks</th></tr></thead>
      <tbody id="content-rows">${rows}</tbody>
    </table>`;

  const prose = `
    <div class="dashboard-prose">
      <p>Click count is cumulative since the analytics pipeline started. High click counts reflect genuine reader interest: every click is an outbound navigation to the linked resource, not a page-internal action.</p>
    </div>`;

  return longtail + filters + table + prose;
}

function filterContentRows(sectionVal) {
  document.querySelectorAll('.dashboard-content-row').forEach(row => {
    if (!sectionVal || row.dataset.section === sectionVal) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

// expose globally so inline onchange handler works
window.filterContentRows = filterContentRows;

/* ============================================================
   TAB 3: Search
   Endpoint: /searches?limit=50
   ============================================================ */

function loadSearch() {
  fetchAndRender('/searches?limit=50', renderSearch, '#dash-search-content');
}

function renderSearch(data) {
  const queries = Array.isArray(data) ? data : (data.data || data.searches || data.queries || []);

  if (!Array.isArray(queries) || queries.length === 0) {
    return '<div class="dashboard-empty">No search data available yet.</div>';
  }

  const totalSearches = queries.reduce((s, q) => s + (q.count || q.search_count || 0), 0);

  // Zero-result queries (field may be present or absent)
  const zeroResults = queries.filter(q => q.result_count === 0 || q.results === 0);

  const rows = queries.slice(0, 20).map((q, idx) => {
    const query = q.query || q.search_query || '';
    const count = q.count || q.search_count || 0;
    const hasResults = q.result_count === undefined ? null : q.result_count > 0;
    const pill = hasResults === false ? '<span class="dashboard-zero-pill">0 results</span>' : '';
    return `<tr>
      <td class="dashboard-rank">${idx + 1}</td>
      <td class="dashboard-query-text">${escHtml(query)}</td>
      <td class="dashboard-click-count">${fmtNum(count)}</td>
      <td>${pill}</td>
    </tr>`;
  }).join('');

  let zeroCallout = '';
  if (zeroResults.length > 0) {
    const zeroList = zeroResults.slice(0, 10).map(q =>
      `<li>${escHtml(q.query || q.search_query || '')}</li>`
    ).join('');
    zeroCallout = `
      <div class="dashboard-callout dashboard-callout-warn">
        <strong>Searches with no results (${zeroResults.length}):</strong>
        <ul class="dashboard-zero-list">${zeroList}</ul>
        These are topics readers wanted that the site did not have. Worth considering as content gaps.
      </div>`;
  }

  const prose = `
    <div class="dashboard-prose">
      <p>Search queries are stored without any user identifier. The count reflects how many times a given string was submitted to the search bar. High-frequency zero-result queries are the clearest signal of content gaps: readers are asking for something and finding nothing.</p>
    </div>`;

  return `
    <div class="dashboard-stat-grid" style="margin-bottom:1.5rem">
      <div class="dashboard-stat-card">
        <div class="dashboard-stat-num">${fmtNum(totalSearches)}</div>
        <div class="dashboard-stat-label">Total searches recorded</div>
      </div>
      <div class="dashboard-stat-card${zeroResults.length > 0 ? ' stat-warning' : ''}">
        <div class="dashboard-stat-num">${zeroResults.length}</div>
        <div class="dashboard-stat-label">Queries returning no results</div>
      </div>
    </div>
    <table class="dashboard-ranked-list">
      <thead><tr><th>#</th><th>Query</th><th>Count</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${zeroCallout}
    ${prose}`;
}

/* ============================================================
   TAB 4: ML Models
   Reads from page-embedded scoreboard JSON
   ============================================================ */

function loadModels() {
  const mount = document.querySelector('#dash-models-content');
  if (!mount) return;

  const raw = document.getElementById('site-scoreboard-data');
  if (!raw) {
    mount.innerHTML = '<div class="dashboard-empty">Scoreboard data not available in this build.</div>';
    return;
  }

  let scoreboard;
  try {
    scoreboard = JSON.parse(raw.textContent);
  } catch (e) {
    mount.innerHTML = '<div class="dashboard-error">Could not parse scoreboard data.</div>';
    return;
  }

  mount.innerHTML = renderModels(scoreboard);
}

function renderModels(scoreboard) {
  const latest   = scoreboard.metrics && scoreboard.metrics.latest;
  const history  = scoreboard.metrics && scoreboard.metrics.history || [];
  const replays  = scoreboard.replays;
  const genAt    = scoreboard.generated_at ? scoreboard.generated_at.slice(0, 10) : 'unknown';

  if (!latest) {
    return '<div class="dashboard-empty">No eval runs recorded yet.</div>';
  }

  const ndcg10   = latest.ndcg_at_10 !== undefined ? (latest.ndcg_at_10 * 100).toFixed(1) + '%' : '--';
  const hr10     = latest.hit_rate_at_10 !== undefined ? (latest.hit_rate_at_10 * 100).toFixed(1) + '%' : '--';
  const map_val  = latest.map_at_10 !== undefined ? (latest.map_at_10 * 100).toFixed(1) + '%' : '--';

  const statCards = `
    <div class="dashboard-stat-grid">
      <div class="dashboard-stat-card stat-positive">
        <div class="dashboard-stat-num">${ndcg10}</div>
        <div class="dashboard-stat-label">NDCG@10 (latest eval)</div>
      </div>
      <div class="dashboard-stat-card">
        <div class="dashboard-stat-num">${hr10}</div>
        <div class="dashboard-stat-label">Hit-Rate@10</div>
      </div>
      <div class="dashboard-stat-card">
        <div class="dashboard-stat-num">${map_val}</div>
        <div class="dashboard-stat-label">MAP@10</div>
      </div>
    </div>`;

  // Sparkline (single dot today, line as rows accumulate)
  let sparkline = '';
  if (history.length >= 1) {
    const vals = history.map(r => r.ndcg_at_10 || 0);
    const maxV = Math.max(...vals, 0.001);
    const W = 300, H = 60, PAD = 10;
    if (vals.length === 1) {
      const cx = W / 2;
      const cy = H - PAD - ((vals[0] / maxV) * (H - PAD * 2));
      sparkline = `<svg viewBox="0 0 ${W} ${H}" class="dashboard-sparkline" aria-label="NDCG@10 over time">
        <circle cx="${cx}" cy="${cy}" r="4" fill="var(--accent)"/>
        <text x="${cx}" y="${cy - 8}" text-anchor="middle" font-size="11" fill="var(--text-muted)">${(vals[0]*100).toFixed(1)}%</text>
      </svg>`;
    } else {
      const step = (W - PAD * 2) / (vals.length - 1);
      const points = vals.map((v, i) => {
        const x = PAD + i * step;
        const y = H - PAD - ((v / maxV) * (H - PAD * 2));
        return `${x},${y}`;
      }).join(' ');
      sparkline = `<svg viewBox="0 0 ${W} ${H}" class="dashboard-sparkline" aria-label="NDCG@10 over time">
        <polyline points="${points}" fill="none" stroke="var(--accent)" stroke-width="2"/>
        ${vals.map((v, i) => {
          const x = PAD + i * step;
          const y = H - PAD - ((v / maxV) * (H - PAD * 2));
          return `<circle cx="${x}" cy="${y}" r="3" fill="var(--accent)"/>`;
        }).join('')}
      </svg>`;
    }
  }

  // History table
  const histRows = history.slice().reverse().map(r => `
    <tr>
      <td>${r.date || ''}</td>
      <td>${r.ndcg_at_10 !== undefined ? (r.ndcg_at_10 * 100).toFixed(1) + '%' : '--'}</td>
      <td>${r.hit_rate_at_10 !== undefined ? (r.hit_rate_at_10 * 100).toFixed(1) + '%' : '--'}</td>
      <td>${r.map_at_10 !== undefined ? (r.map_at_10 * 100).toFixed(1) + '%' : '--'}</td>
      <td>${r.n_evaluable_sessions || '--'}</td>
    </tr>`).join('');

  const histTable = `
    <div class="dashboard-chart-section">
      <h3 class="dashboard-section-title">Eval history</h3>
      ${sparkline ? `<div class="dashboard-sparkline-wrap">${sparkline}</div>` : ''}
      <table class="dashboard-ranked-list">
        <thead><tr><th>Date</th><th>NDCG@10</th><th>HR@10</th><th>MAP@10</th><th>Sessions</th></tr></thead>
        <tbody>${histRows || '<tr><td colspan="5">No rows</td></tr>'}</tbody>
      </table>
    </div>`;

  // Replay section
  let replaySection = '';
  if (replays && replays.latest) {
    const rl = replays.latest;
    const deltaSign = rl.delta_ndcg_at_10 >= 0 ? '+' : '';
    replaySection = `
      <div class="dashboard-chart-section">
        <h3 class="dashboard-section-title">Latest replay</h3>
        <div class="dashboard-stat-grid">
          <div class="dashboard-stat-card">
            <div class="dashboard-stat-num">${(rl.baseline_ndcg_at_10 * 100).toFixed(1)}%</div>
            <div class="dashboard-stat-label">Baseline NDCG@10</div>
          </div>
          <div class="dashboard-stat-card${rl.delta_ndcg_at_10 > 0 ? ' stat-positive' : rl.delta_ndcg_at_10 < 0 ? ' stat-warning' : ''}">
            <div class="dashboard-stat-num">${deltaSign}${(rl.delta_ndcg_at_10 * 100).toFixed(2)}%</div>
            <div class="dashboard-stat-label">Delta vs baseline</div>
          </div>
          <div class="dashboard-stat-card">
            <div class="dashboard-stat-num">${rl.n_evaluable}</div>
            <div class="dashboard-stat-label">Evaluable sessions</div>
          </div>
        </div>
      </div>`;
  }

  const prose = `
    <div class="dashboard-prose">
      <p>NDCG@10 (Normalized Discounted Cumulative Gain) measures how well the ranker places the items a user actually clicked near the top of the list. 1.0 is a perfect ranker. Hit-Rate@10 is the fraction of sessions where at least one clicked item appeared in the top 10. MAP is Mean Average Precision, which rewards both rank quality and completeness. Higher is better on all three. The eval runs a temporal holdout: it trains on older sessions and checks against the most recent window.</p>
    </div>`;

  return `<p class="dashboard-refresh-note">Last refreshed: ${genAt}</p>${statCards}${histTable}${replaySection}${prose}`;
}

/* ============================================================
   TAB 5: A/B Tests
   Reads from page-embedded scoreboard JSON
   ============================================================ */

function loadExperiments() {
  const mount = document.querySelector('#dash-experiments-content');
  if (!mount) return;

  const raw = document.getElementById('site-scoreboard-data');
  if (!raw) {
    mount.innerHTML = '<div class="dashboard-empty">Scoreboard data not available in this build.</div>';
    return;
  }

  let scoreboard;
  try {
    scoreboard = JSON.parse(raw.textContent);
  } catch (e) {
    mount.innerHTML = '<div class="dashboard-error">Could not parse scoreboard data.</div>';
    return;
  }

  mount.innerHTML = renderExperiments(scoreboard);
}

function renderExperiments(scoreboard) {
  const experiments = scoreboard.experiments || [];

  if (experiments.length === 0) {
    return '<div class="dashboard-empty">No experiments recorded yet.</div>';
  }

  const active = experiments.filter(e => e.status === 'active');
  const past   = experiments.filter(e => e.status !== 'active');

  // Active experiment callouts
  const activeCallouts = active.map(exp => {
    const started   = exp.started_at || '--';
    const daysRunning = started !== '--' ? Math.floor((Date.now() - new Date(started)) / 86400000) : '--';
    return `
      <div class="dashboard-experiment-card dashboard-experiment-active">
        <div class="dashboard-experiment-header">
          <span class="dashboard-exp-pill pill-active">Active</span>
          <span class="dashboard-exp-id">${escHtml(exp.id)}</span>
          <span class="dashboard-exp-kind">${escHtml(exp.kind || '')}</span>
        </div>
        <div class="dashboard-experiment-meta">
          Started ${started} &bull; ${daysRunning} days running
        </div>
        <p class="dashboard-exp-summary">${escHtml(exp.summary || 'No summary.')}</p>
        ${renderVariantStats(exp)}
      </div>`;
  }).join('');

  // Past experiments table + detail rows
  const pastRows = past.map(exp => {
    const verdictClass = exp.verdict && exp.verdict.toLowerCase().startsWith('broken') ? 'exp-verdict-broken'
      : exp.verdict && exp.verdict.toLowerCase().includes('pass') ? 'exp-verdict-pass'
      : 'exp-verdict-other';
    return `
      <tr class="dashboard-past-exp" onclick="toggleExpDetail('${escHtml(exp.id)}')" style="cursor:pointer">
        <td><span class="dashboard-exp-pill pill-${exp.status}">${exp.status}</span></td>
        <td class="dashboard-exp-id">${escHtml(exp.id)}</td>
        <td>${escHtml(exp.kind || '')}</td>
        <td>${exp.started_at || '--'}</td>
        <td>${exp.ended_at || '--'}</td>
        <td class="${verdictClass}">${escHtml((exp.verdict || '').substring(0, 60))}${(exp.verdict || '').length > 60 ? '...' : ''}</td>
      </tr>
      <tr id="exp-detail-${escHtml(exp.id)}" class="dashboard-exp-detail-row" style="display:none">
        <td colspan="6">
          <div class="dashboard-exp-detail-body">
            <p>${escHtml(exp.summary || exp.verdict || '')}</p>
            ${renderVariantStats(exp)}
          </div>
        </td>
      </tr>`;
  }).join('');

  const pastTable = past.length > 0 ? `
    <div class="dashboard-chart-section">
      <h3 class="dashboard-section-title">Past experiments</h3>
      <p class="dashboard-chart-note">Click a row to expand per-variant stats.</p>
      <table class="dashboard-ranked-list dashboard-exp-table">
        <thead><tr><th>Status</th><th>ID</th><th>Kind</th><th>Started</th><th>Ended</th><th>Verdict</th></tr></thead>
        <tbody>${pastRows}</tbody>
      </table>
    </div>` : '';

  const prose = `
    <div class="dashboard-prose">
      <p>CTR (click-through rate) is clicks divided by impressions for items shown in that experiment variant. The 95% confidence interval (CI) gives the range where the true CTR probably falls. If the CI ranges overlap substantially between variants, the difference is not reliable. An A/A test should show overlapping CIs: two variants that see identical experiences should not have statistically different CTRs.</p>
    </div>`;

  return (activeCallouts || '<div class="dashboard-empty">No active experiments.</div>') + pastTable + prose;
}

function renderVariantStats(exp) {
  const results = exp.results;
  if (!results) return '<p class="dashboard-exp-collecting">Collecting data...</p>';

  const variantBlocks = Object.entries(results).map(([varId, v]) => {
    const ctr    = v.ctr !== undefined ? (v.ctr * 100).toFixed(2) + '%' : '--';
    const ciLow  = v.ci_low !== undefined ? (v.ci_low * 100).toFixed(2) + '%' : '--';
    const ciHigh = v.ci_high !== undefined ? (v.ci_high * 100).toFixed(2) + '%' : '--';
    const imps   = fmtNum(v.impressions);
    const clicks = fmtNum(v.clicks);
    return `
      <div class="dashboard-variant-block">
        <div class="dashboard-variant-label">${escHtml(varId)}</div>
        <div class="dashboard-variant-ctr">${ctr}</div>
        <div class="dashboard-variant-ci">95% CI: ${ciLow} to ${ciHigh}</div>
        <div class="dashboard-variant-counts">${imps} impressions / ${clicks} clicks</div>
      </div>`;
  }).join('');

  return `<div class="dashboard-variants-grid">${variantBlocks}</div>`;
}

function toggleExpDetail(id) {
  const row = document.getElementById('exp-detail-' + id);
  if (!row) return;
  row.style.display = row.style.display === 'none' ? '' : 'none';
}

window.toggleExpDetail = toggleExpDetail;

/* ============================================================
   Utility
   ============================================================ */

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ============================================================
   Test surface (pure helpers only — no DOM, no network)
   ============================================================ */

if (typeof window !== 'undefined') {
  window.Dashboard = {
    fmtNum,
    pct,
    escHtml,
    skeletonHTML,
    renderTraffic,
    renderTopContent,
    renderSearch,
    renderModels,
    renderExperiments,
    renderVariantStats,
  };
}

/* ============================================================
   Tab switching + init
   ============================================================ */

const TAB_LOADERS = {
  'traffic':     loadTraffic,
  'content':     loadTopContent,
  'search':      loadSearch,
  'models':      loadModels,
  'experiments': loadExperiments,
};

// Track which tabs have been fetched so we lazy-load once per tab
const _loaded = {};

function activateTab(tabId) {
  const tabs        = document.querySelectorAll('.dashboard-tab');
  const tabContents = document.querySelectorAll('.dashboard-tab-content');

  tabs.forEach(t => {
    const isActive = t.dataset.tab === tabId;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
    t.tabIndex = isActive ? 0 : -1;
  });

  tabContents.forEach(c => {
    c.classList.toggle('active', c.id === 'dash-tab-' + tabId);
  });

  if (!_loaded[tabId] && TAB_LOADERS[tabId]) {
    TAB_LOADERS[tabId]();
    _loaded[tabId] = true;
  }
}

document.addEventListener('DOMContentLoaded', function () {
  const dashTabs = Array.from(document.querySelectorAll('.dashboard-tab'));

  // Wire tab buttons
  dashTabs.forEach(function (btn) {
    btn.addEventListener('click', function () {
      activateTab(this.dataset.tab);
    });

    // Arrow-key navigation between tabs (ARIA pattern)
    btn.addEventListener('keydown', function (e) {
      const idx  = dashTabs.indexOf(this);
      let   next = -1;
      if (e.key === 'ArrowRight') {
        next = (idx + 1) % dashTabs.length;
      } else if (e.key === 'ArrowLeft') {
        next = (idx - 1 + dashTabs.length) % dashTabs.length;
      } else if (e.key === 'Home') {
        next = 0;
      } else if (e.key === 'End') {
        next = dashTabs.length - 1;
      }
      if (next >= 0) {
        e.preventDefault();
        dashTabs[next].focus();
        activateTab(dashTabs[next].dataset.tab);
      }
    });
  });

  // Set roving tabIndex: first tab reachable, rest skipped until activated
  dashTabs.forEach(function (btn, i) {
    btn.tabIndex = (i === 0) ? 0 : -1;
  });

  // Load first tab (traffic) immediately
  activateTab('traffic');
});
