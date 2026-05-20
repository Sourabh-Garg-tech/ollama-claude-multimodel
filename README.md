# Ollama Claude Launcher

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4.svg)
![Requires: Ollama](https://img.shields.io/badge/requires-Ollama-6E40C9.svg)
![Requires: Claude Code CLI](https://img.shields.io/badge/requires-Claude_Code_CLI-D97706.svg)

> Redirect [Claude Code](https://claude.ai/code) to [Ollama Cloud](https://ollama.com) models with a Windows GUI — no proxies, no routing rules, no Python dependencies.

This launcher lets you run Claude Code against open-weight models on Ollama Cloud instead of Anthropic's API. Pick a project folder, check prerequisites, and click Launch.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Claude Launcher.vbs                │
│            (double-click entry point)            │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│                launcher.ps1                      │
│  ┌─────────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Folder Picker │  │ Prereq   │  │ Env Vars  │ │
│  │  + History   │  │  Checks  │  │  (model   │ │
│  │              │  │ Ollama ✓  │  │  mapping) │ │
│  │  Last 10     │  │ Claude ✓  │  │           │ │
│  └─────────────┘  └──────────┘  └─────┬─────┘ │
└─────────────────────────────────────────┼───────┘
                                          │
                                          ▼
                               ┌────────────────────┐
                               │    Claude Code CLI  │
                               │  (inherits env vars) │
                               └─────────┬──────────┘
                                         │
                                         ▼
                               ┌────────────────────┐
                               │  Ollama Cloud      │
                               │  localhost:11434    │
                               │                    │
                               │  Opus  → kimi-k2.6 │
                               │  Sonnet → glm-5.1  │
                               │  Haiku  → ds-v4    │
                               └────────────────────┘
```

---

## What You Get

| Feature | What It Means |
|---|---|
| 3-tier model mapping | Opus/Sonnet/Haiku mapped to budget-friendly Ollama Cloud models |
| GUI folder picker | Browse or select from last 10 recent folders |
| Prerequisite checks | Ollama and `claude` CLI status shown before launch |
| Custom system prompt | `system_prompt.txt` auto-loaded on every session |
| Capability flags | Effort, thinking, adaptive thinking enabled per tier |
| No black popup | VBS entry point hides the PowerShell console window |

---

## Prerequisites

- **Windows 10/11**
- [Ollama](https://ollama.com/download) running on `localhost:11434`
- Three Ollama Cloud models pulled (see Setup below)
- [Claude Code CLI](https://claude.ai/code) installed and on `PATH`

## Setup

```powershell
ollama pull kimi-k2.6:cloud
ollama pull glm-5.1:cloud
ollama pull deepseek-v4-flash:cloud
```

---

## Quick Start

1. Place a shortcut to `Claude Launcher.vbs` on your Desktop
2. Double-click it
3. Pick or browse to a project folder
4. Check that both Ollama and `claude` CLI show green (ready)
5. Click **Launch Claude**

The launcher remembers your last 10 project folders. Your custom system prompt (`system_prompt.txt`) is automatically loaded on every session.

---

## Model Mapping

Claude Code uses three internal tiers. The launcher maps each to a different Ollama Cloud model:

| Claude Tier | Ollama Model | Best For |
|---|---|---|
| `opus` (planning) | `kimi-k2.6:cloud` | Deep reasoning, complex analysis — use sparingly |
| `sonnet` (execution) | `glm-5.1:cloud` | Fast coding, implementation, refactors — your default |
| `haiku` (quick tasks) | `deepseek-v4-flash:cloud` | Background tasks, one-liners, summaries — cheap and fast |

**How tiers work in Claude Code:**
- **Sonnet** is the default on Pro plans — it handles all main conversation turns.
- **Haiku** runs automatically for background tasks (conversation summarization, compaction). You don't trigger it manually.
- **Opus** fires only when you switch with `/model opus`, or via the `opusplan` alias (Opus for planning, Sonnet for execution).

---

## How It Works

The launcher sets environment variables before starting Claude Code:

```powershell
# Routing
$env:ANTHROPIC_BASE_URL              = "http://localhost:11434"
$env:ANTHROPIC_AUTH_TOKEN             = "ollama"

# Models
$env:ANTHROPIC_DEFAULT_OPUS_MODEL   = "kimi-k2.6:cloud"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "glm-5.1:cloud"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL  = "deepseek-v4-flash:cloud"

# Display names (shown in /model picker)
$env:ANTHROPIC_DEFAULT_OPUS_MODEL_NAME          = "Kimi K2.6 (Opus)"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION    = "Tier A - architecture, deep debugging, hard problems"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL_NAME        = "GLM-5.1 (Sonnet)"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION  = "Mid-tier - sustained coding, refactors, daily driver"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME          = "DeepSeek V4 Flash (Haiku)"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION   = "Fast and cheap - quick edits, scaffolding, summaries"

# Capabilities (tells Claude Code what features each model supports)
$env:ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES   = "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES = "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES  = "effort,thinking"

# Context
$env:OLLAMA_NUM_CTX = "65536"
```

- `ANTHROPIC_BASE_URL` routes requests to Ollama instead of Anthropic.
- `ANTHROPIC_DEFAULT_*_MODEL` remaps Claude's tier aliases to Ollama models.
- `*_NAME` / `*_DESCRIPTION` customize the `/model` picker display.
- `*_SUPPORTED_CAPABILITIES` tells Claude Code which features each model supports. Without these, Claude Code can't detect features for unknown model IDs.

---

## Files

| File | Purpose |
|---|---|
| `launcher.ps1` | PowerShell GUI — folder picker, history, prereq checks, env vars, launch |
| `Claude Launcher.vbs` | Double-click entry point (no cmd.exe flash) |
| `system_prompt.txt` | Auto-loaded via `--append-system-prompt-file` on every launch |
| `CLAUDE.md` | Contributor guide and architecture details |

---

## Related Projects

- [Obsidian Skill for Claude Code](https://github.com/Sourabh-Garg-tech/obsidian) — If you use Obsidian, the [Obsidian Skill plugin](https://github.com/Sourabh-Garg-tech/obsidian) pairs with this launcher. Add the Obsidian vault rules from its docs to your `system_prompt.txt` to give Claude full vault awareness (CLI commands, wikilink preservation, bulk operations, and more).

---

## Customizing

### Change the system prompt

Edit `system_prompt.txt` and relaunch — no code changes needed.

If you use Obsidian, add the vault rules from [Obsidian Skill for Claude Code](https://github.com/Sourabh-Garg-tech/obsidian) to your `system_prompt.txt` for full vault awareness (CLI commands, wikilink preservation, bulk operations).

### Change model mappings

Edit the model env vars in `launcher.ps1`:

```powershell
$env:ANTHROPIC_DEFAULT_OPUS_MODEL   = "your-model:cloud"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "your-model:cloud"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL  = "your-model:cloud"
```

### Change context window size

Edit `OLLAMA_NUM_CTX` in `launcher.ps1`. Default is `65536` (64K tokens). Increase to `131072` for large codebases — larger context costs more GPU time on Ollama Cloud.

### Change capabilities

Edit the `*_SUPPORTED_CAPABILITIES` env vars in `launcher.ps1`. Valid values (test before enabling):

| Capability | Enables |
|---|---|
| `effort` | `/effort` command (low/medium/high) |
| `xhigh_effort` | Stronger reasoning level |
| `max_effort` | Maximum reasoning level |
| `thinking` | Extended thinking mode |
| `adaptive_thinking` | Model decides how much to think per step |
| `interleaved_thinking` | Thinking between tool calls |

**Do not set** `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1` — it bypasses capability checks and crashes Haiku subagents ([issue #47175](https://github.com/anthropics/claude-code/issues/47175)).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Ollama: not running" | Start Ollama first |
| "claude: not found" | Install Claude Code CLI and add it to PATH |
| Models not available | Run `ollama pull` for each model |
| Black popup window | Use `Claude Launcher.vbs` instead of running `launcher.ps1` directly |
| Haiku subagent crashes | Remove `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT` from env vars |
| No `/effort` command | Check `*_SUPPORTED_CAPABILITIES` env vars include `effort` |
| No thinking output | Check `*_SUPPORTED_CAPABILITIES` env vars include `thinking` |

---

## Privacy

All inference happens through Ollama Cloud. No data is sent to Anthropic's API when using this launcher.

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License

[MIT](LICENSE)