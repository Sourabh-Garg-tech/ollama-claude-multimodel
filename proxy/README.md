# Ollama Analytics Proxy

A lightweight local proxy that sits between Claude Code and Ollama Cloud, logging per-request usage data for analytics.

## How It Works

```
Claude Code CLI --> localhost:11435 (proxy) --> localhost:11434 (Ollama)
                          |
                          v
                   logs/2026-05-20.jsonl
```

The proxy is **fully opt-in**. When it's not running, the launcher connects directly to Ollama on port 11434. When it's running, the launcher detects it and routes through port 11435 instead.

## Prerequisites

- [Node.js](https://nodejs.org) installed and on PATH (required by Claude Code anyway)
- No `npm install` needed — the proxy uses only Node.js built-in modules

## Quick Start

**Start the proxy in the background:**

```powershell
.\proxy\start-proxy-bg.ps1
```

**Or start in the foreground (for debugging):**

```powershell
node .\proxy\proxy.mjs
```

**Check if it's running:**

```powershell
Invoke-WebRequest -Uri "http://localhost:11435/health"
```

**Stop the proxy:**

```powershell
.\proxy\stop-proxy.ps1
```

## Usage Analytics

**Today's summary:**

```powershell
node .\proxy\analytics.mjs
```

**Per-model breakdown:**

```powershell
node .\proxy\analytics.mjs models
```

**Daily totals over a date range:**

```powershell
node .\proxy\analytics.mjs daily --from 2026-05-01 --to 2026-05-20
```

**Raw JSONL output:**

```powershell
node .\proxy\analytics.mjs raw
```

## Log Format

Logs are written to `logs/YYYY-MM-DD.jsonl` (one file per day):

```json
{"timestamp":"2026-05-20T14:30:00.123Z","model":"glm-5.1:cloud","duration_ms":3420,"input_tokens":1523,"output_tokens":487,"status":200,"stream":true,"endpoint":"/v1/messages","method":"POST"}
```

| Field | Description |
|---|---|
| `timestamp` | ISO 8601 timestamp when the request was received |
| `model` | Ollama model name from the request body |
| `duration_ms` | Total request duration in milliseconds |
| `input_tokens` | Prompt tokens from Ollama's usage response |
| `output_tokens` | Completion tokens from Ollama's usage response |
| `status` | HTTP status code from Ollama |
| `stream` | Whether the response was streamed (SSE) |
| `endpoint` | Request path (always `/v1/messages`) |
| `method` | HTTP method (always `POST`) |

## Files

| File | Purpose |
|---|---|
| `proxy/proxy.mjs` | HTTP proxy server — forwards requests, parses SSE, logs JSONL |
| `proxy/analytics.mjs` | CLI tool — reads JSONL logs, shows usage summaries |
| `proxy/start-proxy.ps1` | Start proxy in foreground (debugging) |
| `proxy/start-proxy-bg.ps1` | Start proxy in background (daily use) |
| `proxy/stop-proxy.ps1` | Stop a background proxy process |

## Launcher Integration

The launcher automatically detects if the proxy is running:

- **Proxy running** — status line shows `Proxy: active`, `ANTHROPIC_BASE_URL` is set to `http://localhost:11435`
- **Proxy off** — status line shows `Proxy: off`, `ANTHROPIC_BASE_URL` is set to `http://localhost:11434`

No configuration needed. Just start the proxy before launching Claude Code.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Proxy: off" in launcher | Start the proxy first with `start-proxy-bg.ps1` |
| "Failed to start analytics proxy" | Install Node.js and ensure it's on PATH |
| No logs appearing | Check that the `logs/` directory exists and is writable |
| Streaming responses feel slow | The proxy adds minimal overhead (~1ms per request). If slow, check Ollama |
| 502 errors from proxy | Ollama is not running — start it first |