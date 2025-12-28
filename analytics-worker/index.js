/**
 * Tech-Econ Analytics Endpoint
 * Cloudflare Worker for receiving and storing analytics events
 */

const ALLOWED_ORIGINS = [
  'https://tech-econ.com',
  'https://www.tech-econ.com',
  'https://rawatpranjal.github.io',
  'http://localhost:1313'
];

export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return handleCORS(request);
    }

    // Only accept POST
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    // Verify origin
    const origin = request.headers.get('Origin');
    if (!isAllowedOrigin(origin)) {
      return new Response('Forbidden', { status: 403 });
    }

    try {
      const payload = await request.json();

      // Validate payload
      if (!payload.v || !payload.events || !Array.isArray(payload.events)) {
        return new Response('Invalid payload', { status: 400 });
      }

      // Enrich events with server-side metadata
      const enrichedEvents = payload.events.map(event => ({
        ...event,
        _received: Date.now(),
        _country: request.cf?.country || 'unknown'
      }));

      // Store in KV (non-blocking)
      const key = `events:${Date.now()}:${crypto.randomUUID()}`;
      ctx.waitUntil(
        env.ANALYTICS_EVENTS.put(key, JSON.stringify(enrichedEvents), {
          expirationTtl: 86400 * 30  // 30 days
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
};

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
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400'
    }
  });
}

function corsHeaders(origin) {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Credentials': 'false'
  };
}
