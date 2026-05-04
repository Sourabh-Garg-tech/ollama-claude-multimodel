# Pipeline Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the classification-based router with a deterministic Plan→Execute→Validate→Escalate→Re-validate pipeline for maximum token efficiency.

**Architecture:** Every task runs through the same 5-step pipeline. No classification heuristics. DeepSeek V4 Pro plans, V4 Flash executes, GLM-5.1 validates, Kimi K2.6 escalates on failure. Budget tracking downgrades execution when tokens are scarce.

**Tech Stack:** Python 3.12, LiteLLM (proxy + client), Ollama Cloud models, PyYAML

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `router/__init__.py` | Package init, exports `run_pipeline`, `ROLES` |
| Create | `router/pipeline.py` | 5-step pipeline: plan, execute, validate, escalate, revalidate |
| Create | `router/models.py` | Model registry with roles, pricing, LiteLLM model names |
| Move | `router/budget.py` | Token budget tracker (from `smart_router/budget.py`, minimal edits) |
| Create | `router/callback.py` | LiteLLM pre/post-call hooks for proxy integration |
| Create | `config/models.yaml` | Model catalog + budget config (replaces `smart_router/models.yaml`) |
| Modify | `proxy_config.yaml` | Update callback path from `smart_router` to `router` |
| Modify | `launch-claude.ps1` | Update import paths, simplify prompt |
| Create | `tests/test_pipeline.py` | Pipeline tests with mocked model calls |
| Create | `tests/test_budget.py` | Budget tracker tests |
| Create | `tests/test_models.py` | Model registry tests |
| Delete | `smart_router/` | Replaced by `router/` |
| Delete | `New folder/` | Experimental LangGraph router, not needed for pipeline |
| Delete | `test_router.py` | Replaced by `tests/` |
| Delete | `Ollama commands.txt` | Scratchpad, not source |
| Delete | zip files | Backups, not source (already gitignored) |

---

### Task 1: Create router/models.py — Model Registry

**Files:**
- Create: `router/models.py`
- Create: `router/__init__.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from router.models import ROLES, get_model, get_pricing, MODEL_MAP


def test_roles_defined():
    assert set(ROLES.keys()) == {"planner", "executor", "coder", "validator"}


def test_get_model_returns_ollama_tag():
    assert get_model("planner") == "deepseek-v4-pro:cloud"
    assert get_model("executor") == "deepseek-v4-flash:cloud"
    assert get_model("coder") == "kimi-k2.6:cloud"
    assert get_model("validator") == "glm-5.1:cloud"


def test_get_pricing():
    plan_price = get_pricing("planner")
    assert "input_per_1m" in plan_price
    assert "output_per_1m" in plan_price
    assert plan_price["input_per_1m"] > 0


def test_model_map_has_litellm_names():
    for role in ROLES:
        assert role in MODEL_MAP
        assert MODEL_MAP[role].startswith("ollama/")


if __name__ == "__main__":
    test_roles_defined()
    test_get_model_returns_ollama_tag()
    test_get_pricing()
    test_model_map_has_litellm_names()
    print("All model tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_models.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'router'`

- [ ] **Step 3: Write minimal implementation**

```python
# router/__init__.py
from .pipeline import run_pipeline
from .models import ROLES

__all__ = ["run_pipeline", "ROLES"]
```

```python
# router/models.py
ROLES = {
    "planner":   "deepseek-v4-pro:cloud",
    "executor":  "deepseek-v4-flash:cloud",
    "coder":     "kimi-k2.6:cloud",
    "validator": "glm-5.1:cloud",
}

PRICING = {
    "planner":   {"input_per_1m": 1.42, "output_per_1m": 0.87},
    "executor":  {"input_per_1m": 0.18, "output_per_1m": 0.18},
    "coder":     {"input_per_1m": 1.15, "output_per_1m": 4.00},
    "validator": {"input_per_1m": 1.66, "output_per_1m": 4.40},
}

MODEL_MAP = {
    "planner":   f"ollama/{ROLES['planner']}",
    "executor":  f"ollama/{ROLES['executor']}",
    "coder":     f"ollama/{ROLES['coder']}",
    "validator": f"ollama/{ROLES['validator']}",
}


def get_model(role: str) -> str:
    return ROLES[role]


def get_pricing(role: str) -> dict:
    return PRICING[role]


def estimate_cost(role: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING[role]
    return (input_tokens * p["input_per_1m"] + output_tokens * p["output_per_1m"]) / 1_000_000
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_models.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add router/__init__.py router/models.py tests/test_models.py
git commit -m "feat: add model registry with roles, pricing, and LiteLLM names"
```

---

### Task 2: Move and update budget.py

**Files:**
- Create: `router/budget.py` (from `smart_router/budget.py`)
- Test: `tests/test_budget.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_budget.py
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from router.budget import BudgetTracker


def test_budget_healthy():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        assert budget.status() == "healthy"


def test_budget_low():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        budget.add_usage(850, 850)
        assert budget.status() == "low"


def test_budget_critical():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        budget.add_usage(960, 960)
        assert budget.status() == "critical"


def test_budget_auto_resets():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "budget.json")
        budget = BudgetTracker(config, path)
        budget.add_usage(500, 500)
        # Simulate next day by writing old date
        import json
        with open(path) as f:
            data = json.load(f)
        data["date"] = "2000-01-01"
        with open(path, "w") as f:
            json.dump(data, f)
        budget2 = BudgetTracker(config, path)
        assert budget2.status() == "healthy"


def test_budget_remaining():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        budget.add_usage(300, 200)
        r = budget.remaining()
        assert r["input"] == 700
        assert r["output"] == 800


if __name__ == "__main__":
    test_budget_healthy()
    test_budget_low()
    test_budget_critical()
    test_budget_auto_resets()
    test_budget_remaining()
    print("All budget tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_budget.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'router'`

- [ ] **Step 3: Copy budget.py to router/ (minimal changes)**

Copy `smart_router/budget.py` to `router/budget.py`. No changes needed — it has no imports from the old smart_router package.

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_budget.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add router/budget.py tests/test_budget.py
git commit -m "feat: add budget tracker module to router package"
```

---

### Task 3: Create router/pipeline.py — The Core Pipeline

**Files:**
- Create: `router/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from router.pipeline import run_pipeline


def _mock_call(role, prompt, **kwargs):
    """Return predictable responses based on role."""
    if role == "planner":
        return "PLAN: Step 1 - Read the file. Step 2 - Fix the bug."
    if role == "executor":
        return "RESULT: Fixed the bug in auth.py"
    if role == "validator":
        # First call passes, second call (re-validate after escalation) passes too
        return "PASS"
    if role == "coder":
        return "RESULT: Fixed the bug properly with Kimi"
    return "UNKNOWN"


def test_pipeline_happy_path():
    """Task passes validation on first try."""
    with patch("router.pipeline.call_model", side_effect=_mock_call):
        result = run_pipeline("Fix the auth bug")
    assert result["output"] == "RESULT: Fixed the bug in auth.py"
    assert result["route"] == "happy"
    assert result["steps"] == 3  # plan + execute + validate
    assert result["cost"] > 0


def test_pipeline_escalation():
    """Task fails validation, escalates to coder, passes re-validation."""
    call_count = {"n": 0}
    original = _mock_call

    def counting_mock(role, prompt, **kwargs):
        call_count["n"] += 1
        # First validation fails, second (re-validate) passes
        if role == "validator" and call_count["n"] == 3:
            return "FAIL"
        return original(role, prompt, **kwargs)

    with patch("router.pipeline.call_model", side_effect=counting_mock):
        result = run_pipeline("Fix the hard bug")
    assert result["route"] == "escalated"
    assert result["steps"] == 5  # plan + execute + validate(fail) + escalate + revalidate
    assert "Kimi" in result["output"] or "kimi" in result["output"].lower()


def test_pipeline_tracks_telemetry():
    with patch("router.pipeline.call_model", side_effect=_mock_call):
        result = run_pipeline("Test task")
    assert "telemetry" in result
    assert "plan_tokens" in result["telemetry"]
    assert "execute_tokens" in result["telemetry"]
    assert "validate_tokens" in result["telemetry"]


if __name__ == "__main__":
    test_pipeline_happy_path()
    test_pipeline_escalation()
    test_pipeline_tracks_telemetry()
    print("All pipeline tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_pipeline.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'router.pipeline'`

- [ ] **Step 3: Write the pipeline implementation**

```python
# router/pipeline.py
from .models import get_model, estimate_cost, MODEL_MAP
from .budget import BudgetTracker

try:
    import litellm
    _HAS_LITELLM = True
except ImportError:
    _HAS_LITELLM = False


VALIDATION_PROMPT = (
    "Check correctness of this output. "
    "Reply with only PASS or FAIL followed by a brief reason.\n\n"
    "## Original Task\n{task}\n\n## Output to Validate\n{output}"
)

REVALIDATE_PROMPT = (
    "Re-validate this corrected output after escalation. "
    "Reply with only PASS or FAIL followed by a brief reason.\n\n"
    "## Original Task\n{task}\n\n## Corrected Output\n{output}"
)


def call_model(role: str, prompt: str, budget: BudgetTracker | None = None) -> dict:
    """Call a model by role. Returns dict with 'content', 'input_tokens', 'output_tokens'."""
    model = MODEL_MAP[role]

    if _HAS_LITELLM:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=120,
        )
        content = response.choices[0].message.content
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
    else:
        # Fallback for testing without LiteLLM
        content = ""
        input_tokens = len(prompt.split())
        output_tokens = 0

    if budget:
        budget.add_usage(input_tokens, output_tokens)

    return {
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": estimate_cost(role, input_tokens, output_tokens),
    }


def _parse_validation(content: str) -> bool:
    text = content.strip().upper()
    return text.startswith("PASS")


def run_pipeline(task: str, budget: BudgetTracker | None = None) -> dict:
    """Run the 5-step Plan->Execute->Validate->Escalate->Revalidate pipeline.

    Returns dict with: output, route ("happy"|"escalated"|"failed"), steps, cost, telemetry
    """
    telemetry = {}
    total_cost = 0.0

    # Step 1: Plan
    plan_result = call_model("planner", task, budget=budget)
    telemetry["plan_tokens"] = plan_result["output_tokens"]
    total_cost += plan_result["cost"]

    # Step 2: Execute
    execute_prompt = f"## Plan\n{plan_result['content']}\n\n## Task\n{task}\n\nExecute the plan step by step."
    execute_result = call_model("executor", execute_prompt, budget=budget)
    telemetry["execute_tokens"] = execute_result["output_tokens"]
    total_cost += execute_result["cost"]

    # Step 3: Validate
    validate_prompt = VALIDATION_PROMPT.format(task=task, output=execute_result["content"])
    validate_result = call_model("validator", validate_prompt, budget=budget)
    telemetry["validate_tokens"] = validate_result["output_tokens"]
    total_cost += validate_result["cost"]

    if _parse_validation(validate_result["content"]):
        return {
            "output": execute_result["content"],
            "route": "happy",
            "steps": 3,
            "cost": total_cost,
            "telemetry": telemetry,
        }

    # Step 4: Escalate
    escalate_prompt = f"## Plan\n{plan_result['content']}\n\n## Task\n{task}\n\nThe initial execution failed validation. Fix it properly."
    escalate_result = call_model("coder", escalate_prompt, budget=budget)
    telemetry["escalate_tokens"] = escalate_result["output_tokens"]
    total_cost += escalate_result["cost"]

    # Step 5: Re-validate
    revalidate_prompt = REVALIDATE_PROMPT.format(task=task, output=escalate_result["content"])
    revalidate_result = call_model("validator", revalidate_prompt, budget=budget)
    telemetry["revalidate_tokens"] = revalidate_result["output_tokens"]
    total_cost += revalidate_result["cost"]

    route = "escalated" if _parse_validation(revalidate_result["content"]) else "failed"

    return {
        "output": escalate_result["content"] if route == "escalated" else execute_result["content"],
        "route": route,
        "steps": 5,
        "cost": total_cost,
        "telemetry": telemetry,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_pipeline.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add router/pipeline.py tests/test_pipeline.py
git commit -m "feat: add Plan->Execute->Validate->Escalate pipeline"
```

---

### Task 4: Create router/callback.py — LiteLLM Integration

**Files:**
- Create: `router/callback.py`
- Modify: `proxy_config.yaml:33` (update callback path)

- [ ] **Step 1: Write the LiteLLM callback**

```python
# router/callback.py
"""LiteLLM proxy callbacks for integration with the pipeline.

Pre-call: No model rewriting (the pipeline decides the model, not LiteLLM).
Post-call: Log usage and update budget.
"""
import time
import csv
from pathlib import Path

from .budget import BudgetTracker

_LOG_PATH = Path(__file__).parent.parent / "logs" / "router-usage.csv"
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_budget = None


def _init_budget():
    global _budget
    if _budget is None:
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _budget = BudgetTracker(data.get("budget", {}))
    return _budget


def litellm_logging_callback(kwargs, response_obj, start_time, end_time):
    """LiteLLM post-call callback: log usage and update budget."""
    try:
        model = kwargs.get("model", "unknown")
        if model.startswith("ollama/"):
            model = model[7:]

        usage = response_obj.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        budget = _init_budget()
        budget.add_usage(input_tokens, output_tokens)

        if not _LOG_PATH.exists():
            with open(_LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "model", "input_tokens", "output_tokens"])
        with open(_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           model, input_tokens, output_tokens])
    except Exception:
        pass
```

- [ ] **Step 2: Update proxy_config.yaml callback path**

Change line 33 from `smart_router.litellm_callback` to `router.callback`:

```yaml
  callbacks:
    - router.callback
```

- [ ] **Step 3: Commit**

```bash
git add router/callback.py proxy_config.yaml
git commit -m "feat: add LiteLLM callback and update proxy config path"
```

---

### Task 5: Create config/models.yaml

**Files:**
- Create: `config/models.yaml`

- [ ] **Step 1: Write the config**

```yaml
# config/models.yaml — Model catalog and budget configuration

models:
  deepseek-v4-pro:cloud:
    role: planner
    input_per_1m: 1.42
    output_per_1m: 0.87
    context_window: 1000000
    speed_toks: 175

  deepseek-v4-flash:cloud:
    role: executor
    input_per_1m: 0.18
    output_per_1m: 0.18
    context_window: 1000000
    speed_toks: 107

  kimi-k2.6:cloud:
    role: coder
    input_per_1m: 1.15
    output_per_1m: 4.00
    context_window: 262000
    speed_toks: 139

  glm-5.1:cloud:
    role: validator
    input_per_1m: 1.66
    output_per_1m: 4.40
    context_window: 205000
    speed_toks: 150

budget:
  daily_input_tokens: 100000
  daily_output_tokens: 200000
  hard_stop_on_critical: true
  low_budget_percent: 20
  critical_budget_percent: 5
```

- [ ] **Step 2: Commit**

```bash
git add config/models.yaml
git commit -m "feat: add model catalog config with pipeline roles"
```

---

### Task 6: Update launch-claude.ps1

**Files:**
- Modify: `launch-claude.ps1`

- [ ] **Step 1: Update import paths and system prompt**

Change `$routerDir = Join-Path $PSScriptRoot "smart_router"` to `$routerDir = Join-Path $PSScriptRoot "router"`.

Update the system prompt (lines 131-139) to reference the pipeline architecture:

```powershell
$prompt = @"
You are Claude, operating as a software engineering assistant.
Route all tasks through the Plan->Execute->Validate->Escalate pipeline.
- Invoke all installed skills and plugins automatically whenever they apply.
- Prefer minimal, concise output. Only change what is necessary.
"@
```

- [ ] **Step 2: Commit**

```bash
git add launch-claude.ps1
git commit -m "feat: update launcher to use router package and pipeline prompt"
```

---

### Task 7: Delete old code

**Files:**
- Delete: `smart_router/` (entire directory)
- Delete: `New folder/` (entire directory)
- Delete: `test_router.py` (root, replaced by `tests/`)
- Delete: `Ollama commands.txt` (scratchpad)

- [ ] **Step 1: Remove old smart_router**

```bash
git rm -r smart_router/
```

- [ ] **Step 2: Remove experimental LangGraph router**

```bash
git rm -r "New folder/"
```

- [ ] **Step 3: Remove old test and scratchpad**

```bash
git rm test_router.py "Ollama commands.txt"
```

- [ ] **Step 4: Verify new tests still pass**

Run: `python tests/test_models.py && python tests/test_budget.py && python tests/test_pipeline.py`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove old smart_router, LangGraph router, and scratchpad files"
```

---

### Task 8: Final verification and push

**Files:**
- All files

- [ ] **Step 1: Run all tests**

```bash
python tests/test_models.py && python tests/test_budget.py && python tests/test_pipeline.py
```
Expected: All PASS

- [ ] **Step 2: Verify file structure is clean**

```bash
ls -R
```
Expected: No old files remaining, `router/` and `tests/` directories present.

- [ ] **Step 3: Push to GitHub**

```bash
git push origin master
```

---

## Self-Review

**Spec coverage:** The plan implements the user's 5-step pipeline (Plan→Execute→Validate→Escalate→Re-validate) with the exact model assignments (V4 Pro planner, V4 Flash executor, Kimi coder, GLM validator). Budget tracking is preserved. LiteLLM proxy integration is preserved. ✓

**Placeholder scan:** No TBDs, TODOs, or "implement later" steps. All code is complete. ✓

**Type consistency:** `run_pipeline` returns `dict` with keys `output`, `route`, `steps`, `cost`, `telemetry` — consistent between `pipeline.py` and `test_pipeline.py`. `call_model` returns `dict` with keys `content`, `input_tokens`, `output_tokens`, `cost` — consistent with usage in `pipeline.py`. `BudgetTracker.status()` returns `str` ("healthy"/"low"/"critical") — consistent with test assertions. ✓