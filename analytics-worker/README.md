# Tech-Econ Analytics System

Privacy-respecting analytics for tracking user interactions on tech-econ.com.

## Architecture

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────┐
│  User Browser   │────▶│  Cloudflare Worker       │────▶│  D1 (SQLite)│
│  tracker.js     │     │  tech-econ-analytics     │     │  + KV backup│
└─────────────────┘     └──────────────────────────┘     └─────────────┘
```

## What's Tracked

| Event | Description | Data Captured |
|-------|-------------|---------------|
| `pageview` | Page visits | path, hashed referrer |
| `click` | Link/card clicks | item name, section, category |
| `impression` | Content visibility (50%+ visible) | item name, section |
| `search` | Search queries | query text, source input |
| `engage` | Session engagement | time on page, scroll depth, interaction count |
| `vitals` | Core Web Vitals | LCP, FID, CLS with ratings |
| `error` | JavaScript errors | message, file hash, line number |

## Privacy Measures

- Respects `Do Not Track` header
- No cookies - uses sessionStorage (cleared on tab close)
- Referrers are hashed, not stored raw
- IP addresses are hashed for rate limiting, not stored
- No PII collected

## Files

| File | Purpose |
|------|---------|
| `/static/js/tracker.js` | Client-side tracking script |
| `/analytics-worker/index.js` | Cloudflare Worker (API + storage) |
| `/analytics-worker/schema.sql` | D1 database schema |
| `/analytics-worker/wrangler.toml` | Worker configuration |

## Database Schema (D1)

```sql
events              -- Raw events (kept forever)
daily_stats         -- Aggregated daily metrics
hourly_stats        -- Hourly breakdown
content_clicks      -- Click counts per item
content_impressions -- View counts per item
search_queries      -- Search query frequency
page_views          -- Page view counts
country_stats       -- Visitor countries
cache_meta          -- Response cache + rate limits
```

## API Endpoints

Base URL: `https://tech-econ-analytics.rawat-pranjal010.workers.dev`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/events` | POST | Receive tracking events |
| `/stats` | GET | Dashboard summary (1hr cache) |
| `/timeseries?days=7&granularity=daily` | GET | Time-series data |
| `/clicks?limit=50&section=packages` | GET | Top clicked content |
| `/searches?limit=20` | GET | Top search queries |
| `/export?type=clicks&format=csv` | GET | CSV/JSON export |
| `/health` | GET | Health check |
| `/migrate?key=SECRET` | GET | KV→D1 migration (protected) |

### Export Types
- `events` - Raw events (last N days)
- `clicks` - Content click leaderboard
- `searches` - Search query frequency
- `daily` - Daily aggregated stats

## Safety Limits

| Limit | Value |
|-------|-------|
| Requests per minute (per IP) | 60 |
| Events per request | 50 |
| Payload size | 50KB |
| Event retention | Forever |
| Cache TTL | 1 hour |

## Secrets (Cloudflare)

Set via `wrangler secret put <NAME>`:

| Secret | Purpose |
|--------|---------|
| `ADMIN_KEY` | Protects `/migrate` endpoint |
| `CF_API_TOKEN` | Cloudflare Analytics API (optional) |

## Deployment

### Automatic (GitHub Actions)
- **Site**: Deploys on push to `main` (includes tracker.js)
- **Worker**: Deploys on changes to `analytics-worker/**`

### Manual
```bash
cd analytics-worker
wrangler deploy
```

### First-time Setup
```bash
# 1. Create D1 database
wrangler d1 create tech-econ-analytics-db

# 2. Update wrangler.toml with database_id

# 3. Run schema
wrangler d1 execute tech-econ-analytics-db --remote --file=./schema.sql

# 4. Set secrets
wrangler secret put ADMIN_KEY
wrangler secret put CF_API_TOKEN  # optional

# 5. Deploy
wrangler deploy
```

## Querying Data

### Via API
```bash
# Dashboard stats
curl https://tech-econ-analytics.rawat-pranjal010.workers.dev/stats

# Top clicks
curl https://tech-econ-analytics.rawat-pranjal010.workers.dev/clicks?limit=20

# Export to CSV
curl -o clicks.csv "https://tech-econ-analytics.rawat-pranjal010.workers.dev/export?type=clicks&format=csv"
```

### Via D1 Console
```bash
# Interactive SQL
wrangler d1 execute tech-econ-analytics-db --remote --command "SELECT * FROM content_clicks ORDER BY click_count DESC LIMIT 10"

# Count events
wrangler d1 execute tech-econ-analytics-db --remote --command "SELECT COUNT(*) FROM events"
```

## Monitoring

### Health Check
```bash
curl https://tech-econ-analytics.rawat-pranjal010.workers.dev/health
# {"status":"ok","d1":true,"kv":true,"timestamp":...}
```

### Database Size
```bash
wrangler d1 execute tech-econ-analytics-db --remote --command "SELECT page_count * page_size as size_bytes FROM pragma_page_count(), pragma_page_size()"
```

### Cloudflare Dashboard
- Workers: https://dash.cloudflare.com → Workers & Pages → tech-econ-analytics
- D1: https://dash.cloudflare.com → Workers & Pages → D1 → tech-econ-analytics-db

## How Tracking Works

### Client Side (tracker.js)

1. On page load:
   - Check Do Not Track
   - Generate/retrieve session ID from sessionStorage
   - Initialize all tracking modules
   - Send `pageview` event

2. Event batching:
   - Events queue locally
   - Flush when: 10 events accumulated, 30 seconds pass, or page hidden
   - Uses `sendBeacon` for reliable delivery on page exit

3. Impression tracking:
   - Uses IntersectionObserver (50% visibility threshold)
   - Debounced 2-second flush
   - Each item tracked once per session

### Server Side (Worker)

1. Receive events at `/events`:
   - Validate origin (CORS)
   - Check rate limit
   - Validate payload size/structure

2. Process in background:
   - Insert raw events into D1
   - Update aggregation tables (clicks, impressions, daily stats, etc.)

3. Serve stats:
   - Check cache first
   - Query D1 aggregations
   - Cache for 1 hour

## Content Attribution

For an item to be tracked, add `data-name` attribute:

```html
<div class="card" data-name="pandas" data-category="Python" data-section="packages">
  ...
</div>
```

The tracker automatically picks up:
- `data-name` - Required, item identifier
- `data-section` - Optional, category (packages/datasets/learning)
- `data-category` - Optional, subcategory
