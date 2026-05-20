# Ollama Claude Launcher — Developer Guide

## Architecture

```
Claude Launcher.vbs          ← double-click entry point
        │
        ▼
    launcher.ps1              ← PowerShell GUI (WinForms)
        │
        ├── Folder picker + history (last 10)
        ├── Prereq checks (Ollama, claude CLI)
        ├── Env vars (routing, models, capabilities)
        └── Start-Process powershell.exe → claude --append-system-prompt-file
                │
                ▼
          Claude Code CLI     ← inherits env vars from parent
                │
                ▼
          Ollama Cloud         ← localhost:11434
```

## Key Principles

1. **PowerShell-only execution.** No `cmd.exe`, no batch files. The VBS wrapper launches `powershell.exe` directly.
2. **Env vars on parent process.** Environment variables are set on the parent PowerShell process before `Start-Process`. The child process inherits them — no fragile quoting of env vars in command-line arguments.
3. **Capability flags are required.** Ollama Cloud model IDs like `kimi-k2.6:cloud` are unknown to Claude Code. The `*_SUPPORTED_CAPABILITIES` env vars tell Claude Code what features each model supports. Without them, `/effort`, thinking, and adaptive thinking are unavailable.
4. **No `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT`.** This env var bypasses model capability checks and crashes Haiku subagents ([issue #47175](https://github.com/anthropics/claude-code/issues/47175)).

## Model Mapping

| Claude Tier | Ollama Model | Role |
|---|---|---|
| `opus` (planning) | `kimi-k2.6:cloud` | Expensive — use only for architecture and hard problems. Switch with `/model opus`. |
| `sonnet` (execution) | `glm-5.1:cloud` | **Default.** All coding, refactors, reviews. Fires on 80%+ of turns. |
| `haiku` (background) | `deepseek-v4-flash:cloud` | Auto-fires for summarization, compaction, sub-agents. Cheap and fast. |

## Environment Variables

### Routing

| Variable | Value | Purpose |
|---|---|---|
| `ANTHROPIC_BASE_URL` | `http://localhost:11434` | Route requests to Ollama instead of Anthropic |
| `ANTHROPIC_AUTH_TOKEN` | `ollama` | Auth token for Ollama |

### Model mapping

| Variable | Value | Tier |
|---|---|---|
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | `kimi-k2.6:cloud` | Opus — planning, architecture |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | `glm-5.1:cloud` | Sonnet — coding, execution (default) |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `deepseek-v4-flash:cloud` | Haiku — background tasks, quick work |

### Display names (shown in `/model` picker)

| Variable | Value |
|---|---|
| `*_OPUS_MODEL_NAME` | `Kimi K2.6 (Opus)` |
| `*_OPUS_MODEL_DESCRIPTION` | `Tier A - architecture, deep debugging, hard problems` |
| `*_SONNET_MODEL_NAME` | `GLM-5.1 (Sonnet)` |
| `*_SONNET_MODEL_DESCRIPTION` | `Mid-tier - sustained coding, refactors, daily driver` |
| `*_HAIKU_MODEL_NAME` | `DeepSeek V4 Flash (Haiku)` |
| `*_HAIKU_MODEL_DESCRIPTION` | `Fast and cheap - quick edits, scaffolding, summaries` |

### Capabilities

| Variable | Value |
|---|---|
| `*_OPUS_MODEL_SUPPORTED_CAPABILITIES` | `effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking` |
| `*_SONNET_MODEL_SUPPORTED_CAPABILITIES` | `effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking` |
| `*_HAIKU_MODEL_SUPPORTED_CAPABILITIES` | `effort,thinking` |

What each capability enables:
- `effort` — `/effort` command (low/medium/high effort levels)
- `xhigh_effort` / `max_effort` — strongest reasoning levels
- `thinking` — extended thinking mode (visible reasoning before responses)
- `adaptive_thinking` — model decides how much to think per step based on complexity
- `interleaved_thinking` — thinking between tool calls (critical for agentic workflows)

**Not set:** `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT` — this variable bypasses model capability checks and crashes Haiku subagents ([issue #47175](https://github.com/anthropics/claude-code/issues/47175)).

### Context

| Variable | Value | Notes |
|---|---|---|
| `OLLAMA_NUM_CTX` | `65536` | 64K tokens. Increase to `131072` for large codebases, but larger context costs more GPU time. |

## File Conventions

| File | Purpose |
|---|---|
| `launcher.ps1` | PowerShell GUI — folder picker, history, prereq checks, env vars, launch |
| `Claude Launcher.vbs` | Double-click entry point (launches PowerShell directly, no cmd.exe) |
| `system_prompt.txt` | Ingested via `--append-system-prompt-file` on every launch |
| `CLAUDE.md` | This file — contributor guide |

## Git Workflow

- Branch naming: `feature/description` or `fix/description`
- Commit prefixes: `feat:`, `fix:`, `docs:`, `chore:`
- All changes are PowerShell, VBS, or Markdown only — no build step needed