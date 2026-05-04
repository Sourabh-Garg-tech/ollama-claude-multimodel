# Multi-Model LLM Router

Use Claude Code with Ollama Cloud models, auto-switching to the best model for each request.

## How It Works

Claude Code sends requests to a LiteLLM proxy on `localhost:4000`. The proxy inspects each message and routes to the best model:

```
Claude Code -> LiteLLM Proxy (:4000) -> Ollama Cloud
                    |
                    +-- Short questions -> GLM-5.1
                    +-- Planning/architecture -> V4 Pro
                    +-- Code/debug -> Kimi K2.6
                    +-- Tool results, default -> V4 Flash
```

This means every request automatically gets the right model — no manual switching, no wasted tokens on overkill models.

### Programmatic Pipeline (Secondary)

```
Task --> Plan (V4 Pro) --> Execute (V4 Flash) --> Validate (GLM-5.1)
                                                      |
                                            +---------+----------+
                                            | pass                | fail
                                            v                    v
                                        Done          Escalate (Kimi K2.6)
                                                            |
                                                    Re-validate (GLM-5.1)
                                                            |
                                                    +-------+-------+
                                                    | pass          | fail
                                                    v              v
                                                  Done          Fail + log
```

## Model Roles

| Role | Model | Ollama Tag | Cost (1M tokens) | Why |
|------|-------|-----------|-------------------|-----|
| Planner | DeepSeek V4 Pro | `deepseek-v4-pro:cloud` | $1.42 in / $0.87 out* | Best reasoning (99.4% AIME 2026), 1M context |
| Executor | DeepSeek V4 Flash | `deepseek-v4-flash:cloud` | $0.18 in / $0.18 out* | Cheapest high-quality option, 1M context |
| Coder | Kimi K2.6 | `kimi-k2.6:cloud` | $1.15 in / $4.00 out | Best coding (99% HumanEval), best overall QI (53.9) |
| Validator | GLM-5.1 | `glm-5.1:cloud` | $1.66 in / $4.40 out | Best agentic eval (58.4 SWE-Bench Pro), fast |

*\*DeepSeek pricing at 75% discount through May 2026. Full price: $1.74/$3.48.*

## Project Structure

```
ollama-claude-multimodel/
├── launcher.ps1              # GUI launcher (dark theme, pre-flight checks, routing preview)
├── launch-claude.ps1         # Start proxy + launch Claude CLI
├── Claude Launcher.bat       # Double-click shortcut to launcher.ps1
├── proxy_callbacks.py        # LiteLLM auto-routing callback (optional budget enforcement)
├── proxy_config.yaml         # LiteLLM proxy configuration
├── models.json               # Model metadata for GUI
├── setup.ps1                 # Environment setup
├── requirements.txt          # Python dependencies
├── router/                   # Programmatic pipeline (secondary)
│   ├── __init__.py
│   ├── __main__.py           # CLI entry: python -m router "task"
│   ├── models.py             # Model registry + pricing
│   ├── budget.py             # Daily token budget tracker
│   └── pipeline.py           # Plan->Execute->Validate->Escalate->Revalidate
└── tests/
    └── test_router.py         # Pipeline + budget + model tests
```

## Quick Start

### Prerequisites

- [Ollama](https://ollama.com) running with cloud models pulled
- [Claude Code CLI](https://claude.ai/code) installed
- Python 3.10+
- PowerShell 5.1+ (Windows)

### Setup

```powershell
.\setup.ps1

# Or manually:
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### Launch

```powershell
# GUI launcher (Windows) — pick model or Auto
.\Claude Launcher.bat

# Or directly:
.\launch-claude.ps1 -Model deepseek-v4-flash:cloud -ModelLabel "Auto"
```

The GUI launcher remembers your last 10 project folders and shows:
- Ollama and proxy status (green/red indicators)
- Routing preview (type a message, see which model handles it)

### Programmatic Usage

```python
from router.pipeline import run_pipeline

result = run_pipeline("Refactor auth.py to use JWT tokens")
print(result["output"])   # Final output
print(result["route"])    # "happy" or "escalated"
print(result["cost"])     # Total token cost
```

## Configuration

### Auto-Routing Rules

Routing logic lives in `proxy_callbacks.py`. The `_classify()` function checks messages in order:

1. **Tool results** -> Executor (V4 Flash)
2. **Short questions** (<200 chars, ends with `?`) -> Validator (GLM-5.1)
3. **Planning keywords** (architecture, design, strategy, etc.) -> Planner (V4 Pro)
4. **Code signals** (file extensions, code keywords, code blocks) -> Coder (Kimi K2.6)
5. **Long + analytical** (>=2000 chars + analytical keywords) -> Planner (V4 Pro)
6. **Everything else** -> Executor (V4 Flash)

### Budget (Optional, Off by Default)

Set `BUDGET_ENABLED = True` in `proxy_callbacks.py` to enforce daily token limits. When enabled: low budget (80%+) downgrades executor to validator, critical budget (95%+) pauses requests.

### LiteLLM Proxy

The proxy runs on `localhost:4000` and translates Anthropic Messages API format to Ollama's format. See `proxy_config.yaml` for timeout, retry, and fallback settings.

## Privacy

Ollama Cloud has the strongest privacy commitment among the available providers:

| Provider | Stores Prompts | Used for Training | Data Location |
|----------|---------------|-------------------|---------------|
| Ollama Cloud | No | No | US |
| DeepSeek API | May collect | Possible (opt-out) | China |
| Kimi/Moonshot API | Explicitly collects | Explicitly | China |
| z.ai/Zhipu API | Explicitly collects | Extremely broad license | China |

## Sources

- [WhatLLM - Best Open Source LLMs](https://whatllm.org/best-open-source-llm)
- [Ollama Cloud vs API vs Subscriptions](https://yage.ai/share/ollama-cloud-vs-api-vs-subscriptions-en-20260428.html)
- [GLM-5.1 on Ollama](https://ollama.com/library/glm-5.1:cloud)