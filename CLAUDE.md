# Multi-Model LLM Router

## Architecture

Two routing systems share the same model registry:

1. **Proxy-based auto-routing** (primary) — `proxy_callbacks.py` + `proxy_config.yaml`
   - LiteLLM proxy intercepts Claude Code requests on `localhost:4000`
   - `AutoRouter.async_pre_call_hook` classifies messages and rewrites `data["model"]`
   - `async_post_call_success_hook` logs to `logs/proxy-usage.csv` and optionally tracks budget

2. **Programmatic pipeline** (secondary) — `router/pipeline.py`
   - Plan->Execute->Validate->Escalate->Revalidate workflow
   - Uses Ollama SDK directly (bypasses proxy)
   - Has its own `BudgetTracker` in `router/budget.py`

## Key Files

- `proxy_callbacks.py` — Primary routing: `_classify()` function, `AutoRouter` class, budget check
- `launcher.ps1` — GUI launcher with `Get-Route` (PowerShell mirror of `_classify`)
- `launch-claude.ps1` — Starts proxy, launches Claude CLI with env vars
- `router/pipeline.py` — 5-step pipeline using Ollama SDK
- `router/budget.py` — Budget tracker used by pipeline
- `router/models.py` — Model registry (`MODELS`, `PRICING`, `estimate_cost`)

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

## Important Notes

- Routing heuristics exist in **two places**: `proxy_callbacks.py:_classify()` (Python) and `launcher.ps1:Get-Route` (PowerShell). Keep them in sync.
- Budget status returns `"healthy"/"low"/"critical"` (not `"ok"`)
- `BUDGET_ENABLED = False` by default — set to `True` in `proxy_callbacks.py` to enforce limits
- Models use `:cloud` suffix for Ollama Cloud (e.g., `deepseek-v4-flash:cloud`)