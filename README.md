# Multi-Model LLM Router

Token-efficient LLM routing via Ollama Cloud. Routes every task through a **Plan -> Execute -> Validate -> Escalate -> Re-validate** pipeline, using the cheapest model that gets the job done.

## Architecture

Every request follows the same 5-step pipeline. No classification heuristics, no guesswork.

```
Task ──> Plan (V4 Pro) ──> Execute (V4 Flash) ──> Validate (GLM-5.1)
                                                      │
                                            ┌─────────┴──────────┐
                                            │ pass                │ fail
                                            v                    v
                                        Done          Escalate (Kimi K2.6)
                                                            │
                                                    Re-validate (GLM-5.1)
                                                            │
                                                    ┌───────┴───────┐
                                                    │ pass          │ fail
                                                    v              v
                                                  Done          Fail + log
```

### Why This Pipeline

Traditional routers classify the task first, then pick one model. That wastes tokens: you guess wrong sometimes, and you never validate the output. This pipeline is different:

1. **Plan once** with the strongest reasoner, then execute cheaply.
2. **Validate every output** - catch mistakes before they propagate.
3. **Escalate smartly** - only pay for the expensive coder when validation fails.
4. **Re-validate** - confirm the fix actually fixed it.

Result: most tasks cost ~$0.18/M (Flash pricing) with Pro-level quality, because the plan guides the cheap executor and the validator catches errors.

## Model Roles

| Role | Model | Ollama Tag | Cost (1M tokens) | Why |
|------|-------|-----------|-------------------|-----|
| Planner | DeepSeek V4 Pro | `deepseek-v4-pro:cloud` | $1.42 in / $0.87 out* | Best reasoning (99.4% AIME 2026), 1M context |
| Executor | DeepSeek V4 Flash | `deepseek-v4-flash:cloud` | $0.18 in / $0.18 out* | Cheapest high-quality option, 1M context |
| Coder | Kimi K2.6 | `kimi-k2.6:cloud` | $1.15 in / $4.00 out | Best coding (99% HumanEval), best overall QI (53.9) |
| Validator | GLM-5.1 | `glm-5.1:cloud` | $1.66 in / $4.40 out | Best agentic eval (58.4 SWE-Bench Pro), fast |

*\*DeepSeek pricing at 75% discount through May 2026. Full price: $1.74/$3.48.*

### Model Selection Rationale

**DeepSeek V4 Pro as Planner** - Only called once per task. Best reasoning scores (99.4% AIME, top math/science) and 1M context window mean it can understand complex tasks fully. Worth the cost because a good plan saves tokens downstream.

**DeepSeek V4 Flash as Executor** - Does the bulk of the work. At $0.18/M tokens, it's 8x cheaper than V4 Pro. The plan from step 1 constrains it, so you get Pro-quality results at Flash prices. 1M context means it can handle the full plan + codebase.

**Kimi K2.6 as Coder (escalation)** - Only called when validation fails. Highest overall quality index (53.9) and best coding benchmarks (99% HumanEval). If Flash couldn't do it, Kimi probably can.

**GLM-5.1 as Validator** - Called twice per task (validate + re-validate). Best at agentic evaluation tasks (58.4 SWE-Bench Pro, 68.7 CyberGym). Fast output speed (150 tok/s) keeps validation cheap. Its long-horizon effectiveness means it catches subtle bugs other models miss.

### Benchmarks Summary

| Benchmark | V4 Pro | V4 Flash | Kimi K2.6 | GLM-5.1 |
|-----------|--------|----------|-----------|---------|
| Quality Index | 51.51 | 46.52 | **53.9** | 51.41 |
| AIME 2026 | **99.4%** | ~95% | 96.1% | 95.3% |
| SWE-Bench Pro | ~55% | ~40% | ~54% | **58.4%** |
| HumanEval | ~90% | ~85% | **99%** | ~88% |
| Cost (1M in) | $1.42 | **$0.18** | $1.15 | $1.66 |
| Speed (tok/s) | **175** | 107 | 139 | 150 |
| Context | **1M** | **1M** | 262K | 205K |

## Token Cost Analysis

Typical task: 2K input tokens for planning, 5K input for execution, 1K for each validation.

| Step | Model | Input | Output | Cost |
|------|-------|-------|--------|------|
| Plan | V4 Pro | 2K | 500 | $0.003 |
| Execute | V4 Flash | 5K | 2K | $0.001 |
| Validate | GLM-5.1 | 1K | 200 | $0.002 |
| **Total (happy path)** | | | | **$0.006** |

With escalation (adds Kimi + re-validate):

| Step | Model | Input | Output | Cost |
|------|-------|-------|--------|------|
| Escalate | Kimi K2.6 | 5K | 2K | $0.009 |
| Re-validate | GLM-5.1 | 1K | 200 | $0.002 |
| **Total (escalation)** | | | | **$0.017** |

Compare: routing everything through V4 Pro would cost ~$0.014 per task. The pipeline saves ~60% on the happy path and only costs 20% more when escalation is needed.

## Project Structure

```
ollama-claude-multimodel/
├── router/                  # Routing pipeline
│   ├── pipeline.py          # Plan->Execute->Validate->Escalate->Revalidate
│   ├── models.py            # Model registry, pricing, capabilities
│   ├── budget.py            # Daily token budget tracker
│   └── callback.py          # LiteLLM pre/post-call hooks
├── config/
│   └── models.yaml          # Model catalog + routing config
├── scripts/
│   ├── launch.ps1           # Start LiteLLM proxy + Claude CLI
│   └── gui.ps1              # Windows Forms model selector
├── tests/
│   └── test_router.py       # Pipeline + budget + model tests
├── proxy_config.yaml        # LiteLLM proxy configuration
├── models.json              # Model metadata for GUI
├── requirements.txt         # Python dependencies
└── setup.ps1                # Environment setup
```

## Quick Start

### Prerequisites

- [Ollama](https://ollama.com) running with cloud models pulled
- [Claude Code CLI](https://claude.ai/code) installed
- Python 3.10+
- PowerShell 5.1+ (Windows)

### Setup

```powershell
# Install dependencies
.\setup.ps1

# Or manually:
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### Launch

```powershell
# GUI launcher (Windows)
.\Claude Launcher.bat

# Or directly:
.\launch-claude.ps1 -Model deepseek-v4-pro:cloud -ModelLabel "Planner"
```

### Programmatic Usage

```python
from router.pipeline import run_pipeline

result = run_pipeline("Refactor auth.py to use JWT tokens")
print(result["output"])        # Final output
print(result["route"])         # "happy" or "escalated"
print(result["cost"])          # Total token cost
print(result["validations"])   # List of validation results
```

## Configuration

### Daily Token Budget

Edit `config/models.yaml`:

```yaml
budget:
  daily_input_tokens: 100000
  daily_output_tokens: 200000
  hard_stop_on_critical: true
```

When budget is low (80%+), the executor downgrades to GLM-5.1 for even cheaper execution. When critical (95%+), requests are paused.

### LiteLLM Proxy

The proxy runs on `localhost:4000` and provides an OpenAI-compatible API. Claude Code talks to the proxy, the proxy talks to Ollama.

See `proxy_config.yaml` for timeout, retry, and fallback settings.

## Privacy

Ollama Cloud has the strongest privacy commitment among the available providers:

| Provider | Stores Prompts | Used for Training | Data Location |
|----------|---------------|-------------------|---------------|
| Ollama Cloud | No | No | US |
| DeepSeek API | May collect | Possible (opt-out) | China |
| Kimi/Moonshot API | Explicitly collects | Explicitly | China |
| z.ai/Zhipu API | Explicitly collects | Extremely broad license | China |

If you use the Ollama Cloud models (the `:cloud` tags), your data stays private. Direct API access to Chinese providers may involve data collection.

## Sources

- [WhatLLM - Best Open Source LLMs](https://whatllm.org/best-open-source-llm)
- [Ollama Cloud vs API vs Subscriptions](https://yage.ai/share/ollama-cloud-vs-api-vs-subscriptions-en-20260428.html)
- [GLM-5.1 on Ollama](https://ollama.com/library/glm-5.1:cloud)
- [Qwen 3.6 vs Gemma 4 vs Llama 4 vs GLM-5.1 vs DeepSeek V4](https://lushbinary.com/blog/qwen-3-6-vs-gemma-4-llama-4-glm-5-1-deepseek-v4-open-source-comparison/)