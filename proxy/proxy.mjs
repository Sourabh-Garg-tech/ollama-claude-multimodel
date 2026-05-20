import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROXY_PORT = 11435;
const OLLAMA_PORT = 11434;
const OLLAMA_HOST = 'localhost';
const LOG_DIR = path.join(__dirname, '..', 'logs');

// Ensure log directory exists
if (!fs.existsSync(LOG_DIR)) {
  fs.mkdirSync(LOG_DIR, { recursive: true });
}

const server = http.createServer((req, res) => {
  // Health check endpoint
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', port: PROXY_PORT, target: `http://${OLLAMA_HOST}:${OLLAMA_PORT}` }));
    return;
  }

  const startTime = Date.now();
  let requestBody = [];
  let model = null;
  let isStream = false;

  // Buffer request body to extract model name
  req.on('data', (chunk) => {
    requestBody.push(chunk);
  });

  req.on('end', () => {
    const body = Buffer.concat(requestBody).toString();

    // Parse request body to extract model and stream flag
    if (body && req.headers['content-type']?.includes('application/json')) {
      try {
        const parsed = JSON.parse(body);
        model = parsed.model || null;
        isStream = !!parsed.stream;
      } catch {
        // Not valid JSON — forward anyway, just don't log
      }
    }

    // Forward request to Ollama
    const options = {
      hostname: OLLAMA_HOST,
      port: OLLAMA_PORT,
      path: req.url,
      method: req.method,
      headers: { ...req.headers },
    };

    // Remove proxy-specific headers before forwarding
    delete options.headers['host'];
    options.headers['host'] = `${OLLAMA_HOST}:${OLLAMA_PORT}`;

    const proxyReq = http.request(options, (proxyRes) => {
      const contentType = proxyRes.headers['content-type'] || '';
      const isSSE = contentType.includes('text/event-stream');

      if (isSSE && model) {
        // Streaming response: pipe to client while parsing SSE for usage data
        handleStreamingResponse(proxyRes, res, model, isStream, startTime, req.url, req.method);
      } else if (model) {
        // Non-streaming response: buffer, parse usage, forward
        handleNonStreamingResponse(proxyRes, res, model, isStream, startTime, req.url, req.method);
      } else {
        // Non-messages request or unparseable: forward as-is
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      }
    });

    proxyReq.on('error', (err) => {
      console.error(`[proxy] Error connecting to Ollama: ${err.message}`);
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'upstream_error', message: `Cannot reach Ollama at ${OLLAMA_HOST}:${OLLAMA_PORT}` }));
    });

    // Forward request body
    if (body) {
      proxyReq.write(body);
    }
    proxyReq.end();
  });
});

function handleStreamingResponse(proxyRes, clientRes, model, isStream, startTime, endpoint, method) {
  let inputTokens = 0;
  let outputTokens = 0;
  let sseBuffer = '';

  clientRes.writeHead(proxyRes.statusCode, {
    'Content-Type': proxyRes.headers['content-type'] || 'text/event-stream',
    'Cache-Control': proxyRes.headers['cache-control'] || 'no-cache',
    'Connection': proxyRes.headers['connection'] || 'keep-alive',
  });

  proxyRes.on('data', (chunk) => {
    // Forward to client immediately
    clientRes.write(chunk);

    // Parse SSE events for usage data
    sseBuffer += chunk.toString();
    const lines = sseBuffer.split('\n');
    sseBuffer = lines.pop(); // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const jsonStr = line.slice(6).trim();
        if (jsonStr === '[DONE]') continue;
        try {
          const event = JSON.parse(jsonStr);
          if (event.type === 'message_start' && event.message?.usage) {
            inputTokens = event.message.usage.input_tokens || 0;
          } else if (event.type === 'message_delta' && event.usage) {
            outputTokens = event.usage.output_tokens || 0;
          }
        } catch {
          // Ignore non-JSON SSE lines
        }
      }
    }
  });

  proxyRes.on('end', () => {
    // Process any remaining buffer
    if (sseBuffer.startsWith('data: ')) {
      const jsonStr = sseBuffer.slice(6).trim();
      if (jsonStr !== '[DONE]') {
        try {
          const event = JSON.parse(jsonStr);
          if (event.type === 'message_delta' && event.usage) {
            outputTokens = event.usage.output_tokens || 0;
          }
        } catch { /* ignore */ }
      }
    }

    clientRes.end();
    logRequest({
      timestamp: new Date(startTime).toISOString(),
      model,
      duration_ms: Date.now() - startTime,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      status: proxyRes.statusCode,
      stream: true,
      endpoint,
      method,
    });
  });

  proxyRes.on('error', (err) => {
    console.error(`[proxy] Stream error: ${err.message}`);
    clientRes.end();
  });
}

function handleNonStreamingResponse(proxyRes, clientRes, model, isStream, startTime, endpoint, method) {
  let responseBody = [];

  proxyRes.on('data', (chunk) => {
    responseBody.push(chunk);
  });

  proxyRes.on('end', () => {
    const body = Buffer.concat(responseBody).toString();
    let inputTokens = 0;
    let outputTokens = 0;

    try {
      const parsed = JSON.parse(body);
      if (parsed.usage) {
        inputTokens = parsed.usage.input_tokens || 0;
        outputTokens = parsed.usage.output_tokens || 0;
      }
    } catch { /* ignore parse errors */ }

    // Forward response headers and body to client
    clientRes.writeHead(proxyRes.statusCode, proxyRes.headers);
    clientRes.end(body);

    logRequest({
      timestamp: new Date(startTime).toISOString(),
      model,
      duration_ms: Date.now() - startTime,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      status: proxyRes.statusCode,
      stream: false,
      endpoint,
      method,
    });
  });

  proxyRes.on('error', (err) => {
    console.error(`[proxy] Response error: ${err.message}`);
    clientRes.writeHead(502, { 'Content-Type': 'application/json' });
    clientRes.end(JSON.stringify({ error: 'upstream_error', message: err.message }));
  });
}

function logRequest(entry) {
  const dateStr = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  const logFile = path.join(LOG_DIR, `${dateStr}.jsonl`);
  const line = JSON.stringify(entry) + '\n';

  try {
    fs.appendFileSync(logFile, line);
  } catch (err) {
    console.error(`[proxy] Failed to write log: ${err.message}`);
  }
}

server.listen(PROXY_PORT, () => {
  console.log(`[proxy] Ollama analytics proxy listening on http://localhost:${PROXY_PORT}`);
  console.log(`[proxy] Forwarding to http://${OLLAMA_HOST}:${OLLAMA_PORT}`);
  console.log(`[proxy] Logging to ${LOG_DIR}/YYYY-MM-DD.jsonl`);
  console.log(`[proxy] Health check: http://localhost:${PROXY_PORT}/health`);
});