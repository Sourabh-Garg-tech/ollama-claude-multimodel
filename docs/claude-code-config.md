# Claude Code Configuration Guide

Complete reference for configuring Claude Code when using this launcher with Ollama Cloud.

---

## Settings Files

Claude Code uses a layered configuration system. Settings from higher-priority scopes override lower ones:

| Priority | Scope | File | Shared? |
|---|---|---|---|
| 1 (highest) | Managed | OS-level (IT-deployed) | Yes (org-wide) |
| 2 | CLI args | `--model`, `--permission-mode`, etc. | Session-only |
| 3 | Local | `.claude/settings.local.json` | No (gitignored) |
| 4 | Project | `.claude/settings.json` | Yes (committed) |
| 5 (lowest) | User (global) | `~/.claude/settings.json` | No |

Permission rules (allow/deny/ask) **merge** across scopes. Deny rules always win.

Run `/config` in a session to see all active settings and their sources.

---

## Environment Variables

The launcher sets these in `launcher.ps1` before starting Claude Code. You can also set them in `settings.json` under the `"env"` key, or in your shell profile.

### Routing (required)

| Variable | Value | Purpose |
|---|---|---|
| `ANTHROPIC_BASE_URL` | `http://localhost:11434` | Route requests to Ollama instead of Anthropic |
| `ANTHROPIC_AUTH_TOKEN` | `ollama` | Auth token for Ollama (`Authorization: Bearer ollama`) |

### Model mapping (required)

| Variable | Value | Purpose |
|---|---|---|
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | `kimi-k2.6:cloud` | Override Opus-class model |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | `glm-5.1:cloud` | Override Sonnet-class model (default tier) |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `deepseek-v4-flash:cloud` | Override Haiku-class model (background tier) |

### Display names (recommended)

| Variable | Example |
|---|---|
| `ANTHROPIC_DEFAULT_OPUS_MODEL_NAME` | `Kimi K2.6 (Opus)` |
| `ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION` | `Tier A - architecture, deep debugging, hard problems` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL_NAME` | `GLM-5.1 (Sonnet)` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION` | `Mid-tier - sustained coding, refactors, daily driver` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME` | `DeepSeek V4 Flash (Haiku)` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION` | `Fast and cheap - quick edits, scaffolding, summaries` |

### Capabilities (required for unknown models)

Without these flags, Claude Code cannot detect features for unrecognized model IDs like `kimi-k2.6:cloud`.

| Variable | Value |
|---|---|
| `ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES` | `effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES` | `effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES` | `effort,thinking` |

| Capability | Enables |
|---|---|
| `effort` | `/effort` command (low/medium/high) |
| `xhigh_effort` | Stronger reasoning level |
| `max_effort` | Maximum reasoning level |
| `thinking` | Extended thinking mode |
| `adaptive_thinking` | Model decides how much to think per step |
| `interleaved_thinking` | Thinking between tool calls (critical for agentic workflows) |

### Custom model entry (optional)

Add a fourth model to the `/model` picker (in addition to the three tiers):

```powershell
$env:ANTHROPIC_CUSTOM_MODEL_OPTION = "qwen3-coder:cloud"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = "Qwen 3 Coder (Local)"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "Local model via Ollama"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES = "effort,thinking"
```

### Gateway tuning (recommended for local models)

| Variable | Default | Recommended | Purpose |
|---|---|---|---|
| `API_TIMEOUT_MS` | 600000 | 1200000 | API request timeout (local models can be slower) |
| `CLAUDE_CODE_MAX_RETRIES` | 10 | 5 | Retry count for failed requests |
| `OLLAMA_NUM_CTX` | 2048 | 65536 | Ollama context window size |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | auto | 65536 | Claude Code context window (should match OLLAMA_NUM_CTX) |

### Privacy (optional)

| Variable | Purpose |
|---|---|
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` | Prevents telemetry, auto-updater, error reporting to Anthropic |
| `CLAUDE_CODE_ATTRIBUTION_HEADER=0` | Omits attribution block from system prompt (improves Ollama cache hit rate) |

### Important warnings

- **Do NOT set** `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1` — it bypasses capability checks and crashes Haiku subagents ([issue #47175](https://github.com/anthropics/claude-code/issues/47175)).
- Ollama's Anthropic compatibility does not support prompt caching, tool choice, or the batches API.
- MCP tool search is disabled for non-first-party hosts by default. Re-enable with `ENABLE_TOOL_SEARCH=true` if needed.

---

## Settings.json Reference

### Project-level (`.claude/settings.json`)

Commit this with your project for team-shared settings:

```jsonc
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",

  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(gh *)",
      "Bash(ollama *)",
      "WebSearch",
      "WebFetch(domain:docs.anthropic.com)",
      "WebFetch(domain:ollama.com)"
    ],
    "deny": [
      "Bash(rm -rf *)"
    ]
  },

  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:11434",
    "ANTHROPIC_AUTH_TOKEN": "ollama",
    "OLLAMA_NUM_CTX": "65536"
  }
}
```

### User-level (`~/.claude/settings.json`)

Personal preferences that apply to all projects:

```jsonc
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",

  "model": "sonnet",

  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(git *)",
      "Bash(gh *)",
      "Bash(ollama *)"
    ]
  },

  "autoUpdatesChannel": "latest",
  "editorMode": "normal",
  "includeGitInstructions": true,
  "showTurnDuration": true
}
```

### Permission modes

| Mode | Behavior |
|---|---|
| `default` | Prompts on first use of each tool |
| `acceptEdits` | Auto-accepts file edits and common filesystem commands |
| `plan` | Read-only — Claude explores but does not edit |
| `auto` | Auto-approves with background safety checks |
| `dontAsk` | Auto-denies unless pre-approved via allow rules |
| `bypassPermissions` | Skips all prompts (only for isolated containers) |

### Permission rule syntax

Rules use the format `Tool(specifier)` where specifier supports wildcards:

| Rule | Effect |
|---|---|
| `Bash(git *)` | Allow all git commands |
| `Bash(ollama *)` | Allow all ollama commands |
| `Bash(rm -rf *)` | Block recursive force deletes |
| `Read(./.env)` | Block reading .env files |
| `WebFetch(domain:ollama.com)` | Allow fetching from ollama.com |
| `mcp__puppeteer__*` | Allow all tools from puppeteer MCP server |

**Evaluation order:** deny first, then ask, then allow. First match wins. Deny rules from any scope take precedence.

---

## Hooks

Hooks run shell commands at specific lifecycle events. Define them in `settings.json` under the `"hooks"` key.

### Available events

| Cadence | Events |
|---|---|
| Per session | `SessionStart`, `SessionEnd`, `Setup` |
| Per turn | `UserPromptSubmit`, `Stop`, `StopFailure` |
| Per tool | `PreToolUse`, `PostToolUse`, `PostToolUseFailure` |
| Permission | `PermissionRequest`, `PermissionDenied` |
| Compaction | `PreCompact`, `PostCompact` |

### Example: Auto-verify Ollama on session start

```jsonc
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "curl -sf http://localhost:11434/api/tags > /dev/null && echo 'Ollama: running' || echo 'Ollama: NOT RUNNING'"
          }
        ]
      }
    ]
  }
}
```

### Example: Block commits to main

```jsonc
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(git push *main*)",
            "command": "echo 'Direct pushes to main are blocked' >&2; exit 2"
          }
        ]
      }
    ]
  }
}
```

### Hook types

| Type | Description |
|---|---|
| `command` | Shell command (exit 0 = success, exit 2 = block, other = non-blocking error) |
| `http` | POST JSON to a URL |
| `mcp_tool` | Call an MCP server tool |
| `prompt` | Single-turn LLM evaluation |
| `agent` | Multi-turn subagent with tool access (experimental) |

---

## MCP Servers

Model Context Protocol servers extend Claude Code with external tools. Configure in `.mcp.json` (project) or `~/.claude.json` (user).

### Example: Filesystem MCP server

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    }
  }
}
```

### Controlling MCP in settings.json

| Setting | Purpose |
|---|---|
| `enableAllProjectMcpServers` | Auto-approve all MCP servers in `.mcp.json` |
| `enabledMcpjsonServers` | Specific servers from `.mcp.json` to approve |
| `disabledMcpjsonServers` | Specific servers to reject |

---

## Sandbox

Claude Code supports sandboxing for isolated file and network access:

```jsonc
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "autoAllowBashIfSandboxed": true,
    "filesystem": {
      "allowWrite": ["."],
      "denyRead": ["./.env", "./secrets/**"]
    },
    "network": {
      "allowedDomains": ["github.com", "localhost"]
    }
  }
}
```

---

## Putting It All Together

### Recommended project `.claude/settings.json` for this launcher

```jsonc
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",

  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(git *)",
      "Bash(gh *)",
      "Bash(ollama *)",
      "WebSearch"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)",
      "Read(./.env)"
    ]
  },

  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:11434",
    "ANTHROPIC_AUTH_TOKEN": "ollama",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "kimi-k2.6:cloud",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1:cloud",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash:cloud",
    "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "Kimi K2.6 (Opus)",
    "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "GLM-5.1 (Sonnet)",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "DeepSeek V4 Flash (Haiku)",
    "ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION": "Tier A - architecture, deep debugging, hard problems",
    "ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION": "Mid-tier - sustained coding, refactors, daily driver",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION": "Fast and cheap - quick edits, scaffolding, summaries",
    "ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES": "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking",
    "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES": "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES": "effort,thinking",
    "OLLAMA_NUM_CTX": "65536"
  },

  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "curl -sf http://localhost:11434/api/tags > /dev/null && echo 'Ollama: running' || echo 'Ollama: NOT RUNNING'"
          }
        ]
      }
    ]
  }
}
```

This settings file:
- Sets `acceptEdits` mode for smoother workflow
- Pre-approves git, gh, and ollama commands
- Blocks dangerous deletes and `.env` reads
- Configures all Ollama environment variables
- Verifies Ollama is running at session start

### Using settings.json instead of launcher.ps1

The `"env"` block in `settings.json` is an alternative to setting environment variables in `launcher.ps1`. You can use either approach:

| Approach | Pros | Cons |
|---|---|---|
| `launcher.ps1` env vars | Set per-launch, GUI workflow, only active when launched via VBS | Must edit PowerShell to change |
| `settings.json` env block | Always active (even `claude` CLI), survives updates, team-shareable | Always active (even without Ollama running) |

For most users, the launcher is simpler. For teams or power users who run `claude` directly, `settings.json` is more portable.

---

## Further Reading

- [Claude Code Settings Reference](https://code.claude.com/docs/en/settings)
- [Permissions Documentation](https://code.claude.com/docs/en/permissions)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Environment Variables](https://code.claude.com/docs/en/env-vars)
- [LLM Gateway Configuration](https://docs.anthropic.com/en/docs/claude-code/llm-gateway)
- [JSON Schema](https://json.schemastore.org/claude-code-settings.json)
- [Example Settings](https://github.com/anthropics/claude-code/tree/main/examples/settings)