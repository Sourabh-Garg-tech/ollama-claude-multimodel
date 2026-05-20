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

The launcher automatically starts the proxy if Node.js is available and the proxy isn't already running:

- **Proxy auto-started** — status line shows `Proxy: started`, `ANTHROPIC_BASE_URL` is set to `http://localhost:11435`
- **Proxy already running** — status line shows `Proxy: active`, `ANTHROPIC_BASE_URL` is set to `http://localhost:11435`
- **Proxy off** (no Node.js or start failed) — status line shows `Proxy: off`, `ANTHROPIC_BASE_URL` is set to `http://localhost:11434`

No configuration needed. The proxy starts automatically when you launch Claude Code.

## Proof of Concept: Multi-Instance Usage Analysis

The proxy was tested with **two Claude Code instances** running simultaneously against Ollama Cloud (3 concurrent model slots). Each instance analyzed a different project — one with many Markdown files, one with many Python files.

### Session Summary (~10 minutes, 28 requests)

| Tier | Model | Requests | Input Tokens | Output Tokens | Efficiency (out/1K in) | Normal Latency | Under Contention |
|---|---|---|---|---|---|---|---|
| Haiku | deepseek-v4-flash | 15 (54%) | 799K | 13,612 | 17.0 | 2-3s | 55-106s |
| Sonnet | glm-5.1 | 9 (32%) | 273K | 3,035 | 11.1 | 4-5s | 12-19s |
| Opus | kimi-k2.6 | 4 (14%) | 155K | 1,741 | 11.2 | 7-10s | N/A |
| **Total** | | **28** | **1.23M** | **18,388** | **15.0** | | |

### Key Findings

1. **Haiku is the contention bottleneck.** Under normal load, Haiku responds in 2-3s. With two instances competing for the same Haiku model slot, latency spiked to 55-106s (25-50x slower). Haiku handles compaction, summarization, and subagents — when it stalls, everything stalls.

2. **Sonnet handles concurrency well.** Sonnet latency increased modestly (4-5s to 12-19s) under contention but remained usable. Sonnet is the right tier for parallel instances.

3. **Context windows grow beyond `OLLAMA_NUM_CTX`.** Despite setting `OLLAMA_NUM_CTX=65536`, Ollama served requests with up to 155K input tokens — 2.4x the configured limit. Each large context request costs more GPU time than expected.

4. **Input tokens dominate cost.** 1.23M input tokens vs 18K output tokens — a 67:1 ratio. Large context windows (35-65K per request) are the primary cost driver, not output generation.

5. **Ollama doesn't support all Claude Code API endpoints.** Requests to `/v1/messages/count_tokens` return 404. The proxy correctly logs these, which helps identify API compatibility gaps.

6. **Token efficiency varies by tier.** Haiku produces 17 output tokens per 1K input (most efficient), Sonnet 11.1, Opus 11.2. But Opus delivers higher reasoning quality per token — the right metric depends on the task.

### Recommendations

- **Single instance**: All tiers perform normally. No issues.
- **Two instances**: Viable for Sonnet-heavy work. Expect Haiku-tier slowdown (background compaction, subagents).
- **Context management**: Start fresh sessions periodically to prevent context bloat beyond `OLLAMA_NUM_CTX`.
- **Budget monitoring**: Use `node proxy/analytics.mjs models` to track per-model token spend across sessions.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Proxy: off" in launcher | Start the proxy first with `start-proxy-bg.ps1` |
| "Failed to start analytics proxy" | Install Node.js and ensure it's on PATH |
| No logs appearing | Check that the `logs/` directory exists and is writable |
| Streaming responses feel slow | The proxy adds minimal overhead (~1ms per request). If slow, check Ollama |
| 502 errors from proxy | Ollama is not running — start it first |