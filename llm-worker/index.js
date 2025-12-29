/**
 * LLM Search Enhancement Worker
 *
 * Provides AI-powered search enhancements:
 * - POST /expand - Query expansion with domain terminology
 * - POST /explain - Streaming result explanations
 *
 * Uses Groq API with Llama 3.3 70B model
 */

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const MODEL = 'llama-3.3-70b-versatile';

const ALLOWED_ORIGINS = [
  'https://tech-econ.com',
  'https://www.tech-econ.com',
  'https://rawatpranjal.github.io',
  'http://localhost:1313'
];

// Domain-specific terminology for econometrics/ML
const DOMAIN_CONTEXT = `You are a search assistant for tech-econ.org, a resource directory for applied researchers in economics, data science, and machine learning.

Common domain abbreviations:
- IV = instrumental variables
- DID / DiD = difference-in-differences
- RCT = randomized controlled trial
- FE = fixed effects
- RE = random effects
- OLS = ordinary least squares
- 2SLS = two-stage least squares
- RDD = regression discontinuity design
- CATE = conditional average treatment effect
- ATE = average treatment effect
- ATT = average treatment effect on the treated
- ML = machine learning
- DML = double machine learning
- LASSO = least absolute shrinkage and selection operator`;

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get('Origin');

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return handleCORS(origin);
    }

    // Validate origin
    if (!isAllowedOrigin(origin)) {
      return new Response('Forbidden', { status: 403 });
    }

    const url = new URL(request.url);

    // Route requests
    if (request.method === 'POST' && url.pathname === '/expand') {
      return handleExpand(request, env, origin);
    }

    if (request.method === 'POST' && url.pathname === '/explain') {
      return handleExplain(request, env, origin);
    }

    // Health check
    if (request.method === 'GET' && url.pathname === '/health') {
      return jsonResponse({ status: 'ok', model: MODEL }, origin);
    }

    return new Response('Not found', { status: 404 });
  }
};

/**
 * Handle query expansion
 * Expands abbreviations and adds related terms
 */
async function handleExpand(request, env, origin) {
  try {
    const { query } = await request.json();

    if (!query || query.length < 2) {
      return jsonResponse({ expandedTerms: [] }, origin);
    }

    // Check for API key
    if (!env.GROQ_API_KEY) {
      console.error('GROQ_API_KEY not configured');
      return jsonResponse({ expandedTerms: [], error: 'API not configured' }, origin);
    }

    const response = await fetch(GROQ_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.GROQ_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [{
          role: 'system',
          content: `${DOMAIN_CONTEXT}

Your task is to expand search queries. Given a search query:
1. Expand any abbreviations (e.g., "IV" -> "instrumental variables")
2. Add 1-2 closely related terms that might help find relevant results
3. Return ONLY a JSON array of strings with the expanded/related terms
4. Do NOT include the original query terms
5. Keep it focused - max 3 terms

Example:
Query: "IV estimation"
Response: ["instrumental variables", "2SLS", "endogeneity"]

Query: "causal ML"
Response: ["causal machine learning", "double machine learning", "CATE estimation"]`
        }, {
          role: 'user',
          content: `Expand this search query: "${query}"`
        }],
        max_tokens: 100,
        temperature: 0.3
      })
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Groq API error:', error);
      return jsonResponse({ expandedTerms: [], error: 'LLM request failed' }, origin);
    }

    const data = await response.json();
    const content = data.choices[0]?.message?.content || '[]';

    // Parse the JSON array from response
    let expandedTerms = [];
    try {
      // Try to parse as JSON first
      expandedTerms = JSON.parse(content);
      if (!Array.isArray(expandedTerms)) {
        expandedTerms = [];
      }
    } catch (e) {
      // Fallback: extract quoted strings
      const matches = content.match(/["']([^"']+)["']/g);
      if (matches) {
        expandedTerms = matches.map(s => s.replace(/["']/g, ''));
      }
    }

    // Filter and limit
    expandedTerms = expandedTerms
      .filter(term => typeof term === 'string' && term.length > 0)
      .slice(0, 3);

    return jsonResponse({ expandedTerms }, origin);

  } catch (error) {
    console.error('Expand error:', error);
    return jsonResponse({ expandedTerms: [], error: 'Internal error' }, origin);
  }
}

/**
 * Handle result explanation with streaming
 * Explains why a result is relevant to the query
 */
async function handleExplain(request, env, origin) {
  try {
    const { query, result } = await request.json();

    if (!query || !result) {
      return new Response('Missing query or result', {
        status: 400,
        headers: corsHeaders(origin)
      });
    }

    // Check for API key
    if (!env.GROQ_API_KEY) {
      return sseError('API not configured', origin);
    }

    const response = await fetch(GROQ_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.GROQ_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [{
          role: 'system',
          content: `${DOMAIN_CONTEXT}

You are explaining search result relevance. Be concise (2-3 sentences max).
Focus on:
1. Why this result matches the user's search intent
2. What specific features/capabilities are relevant
3. Any domain-specific connections (e.g., implements a method from a paper)

Do not repeat the result description verbatim. Add value by connecting concepts.`
        }, {
          role: 'user',
          content: `Explain why this result is relevant to the search "${query}":

Title: ${result.name}
Type: ${result.type}
Category: ${result.category || 'N/A'}
Description: ${(result.description || '').slice(0, 400)}`
        }],
        max_tokens: 150,
        temperature: 0.5,
        stream: true
      })
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Groq API error:', error);
      return sseError('LLM request failed', origin);
    }

    // Transform Groq's SSE format to our simplified format
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();

    // Process the stream
    (async () => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') {
                await writer.write(encoder.encode('data: [DONE]\n\n'));
                continue;
              }

              try {
                const parsed = JSON.parse(data);
                const content = parsed.choices?.[0]?.delta?.content;
                if (content) {
                  // Send simplified SSE with just the content
                  await writer.write(
                    encoder.encode(`data: ${JSON.stringify({ content })}\n\n`)
                  );
                }
              } catch (e) {
                // Skip malformed JSON
              }
            }
          }
        }
      } catch (error) {
        console.error('Stream processing error:', error);
      } finally {
        await writer.close();
      }
    })();

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        ...corsHeaders(origin)
      }
    });

  } catch (error) {
    console.error('Explain error:', error);
    return sseError('Internal error', origin);
  }
}

// Helper functions

function isAllowedOrigin(origin) {
  if (!origin) return false;
  return ALLOWED_ORIGINS.some(allowed =>
    origin === allowed || origin.startsWith(allowed)
  );
}

function handleCORS(origin) {
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
    'Access-Control-Allow-Origin': isAllowedOrigin(origin) ? origin : ALLOWED_ORIGINS[0],
    'Access-Control-Allow-Credentials': 'false'
  };
}

function jsonResponse(data, origin) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      ...corsHeaders(origin)
    }
  });
}

function sseError(message, origin) {
  return new Response(`data: ${JSON.stringify({ error: message })}\n\n`, {
    headers: {
      'Content-Type': 'text/event-stream',
      ...corsHeaders(origin)
    }
  });
}
