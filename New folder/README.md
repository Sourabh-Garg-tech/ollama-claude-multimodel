# LLM Router

Production-grade LangGraph + LiteLLM routing stack for four models:
DeepSeek V4 Flash, DeepSeek V4 Pro, Kimi K2.6, GLM-5.1.

## Architecture

```
App
 └─ LangGraph (control plane)
     ├─ hard_router        deterministic rules (token count, code signals, loop signals)
     ├─ classifier         Flash-based intent classification (only when rules abstain)
     ├─ execute            model call through LiteLLM proxy
     ├─ det_validator      schema / syntax / tool / length / refusal checks
     ├─ llm_judge          Pro-based quality judge (opt-in per task)
     ├─ escalate           re-route on failure (Flash/Kimi/GLM → Pro)
     └─ finalize           telemetry flush
 └─ LiteLLM (transport layer)
     ├─ provider abstraction   one OpenAI-compatible surface for all 4 models
     ├─ infra fallbacks        rate-limit / outage / context-window overflow
     └─ auth management        per-provider API keys via env vars
```

**Key distinction:**
- LangGraph decides *which model should do the task* and *whether the answer is good enough*.
- LiteLLM decides *what to do if the chosen model cannot be reached*.

## Routing rules

| Condition | Route |
|---|---|
| Input > 50K tokens | v4_pro |
| Code blocks / refactor / debug intent | kimi |
| Loop / monitor / autonomous / pipeline intent | glm |
| Classifier: simple extraction / formatting | v4_flash |
| Classifier: complex reasoning | v4_pro |
| Classifier confidence < 0.6 or risk = high | v4_pro (conservative) |

Default flow: `v4_flash` → escalate to `v4_pro` on failure.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export DEEPSEEK_API_KEY=...
export KIMI_API_KEY=...
export GLM_API_KEY=...
export LITELLM_MASTER_KEY=sk-my-proxy-key

# 3. Start LiteLLM proxy
litellm --config config/litellm_config.yaml --port 4000

# 4. Run
python main.py
```

## Telemetry

Every step emits a JSON line to stdout:

```json
{"ts": 1714500000.0, "event": "route_decision", "route": "kimi", "source": "hard_rule", ...}
{"ts": 1714500001.2, "event": "execution", "route": "kimi", "attempt": 1, "latency_ms": 820, ...}
{"ts": 1714500002.1, "event": "validation", "passed": true, ...}
{"ts": 1714500002.1, "event": "final", "success": true, "initial_route": "kimi", ...}
```

Pipe to your log aggregator. Track `first_route_accuracy()` — if any route drops below ~0.80, retune its classifier thresholds.

## Calling from your code

```python
from main import run_task

result = run_task(
    task="Refactor auth.py to use JWT tokens",
    max_attempts=3,
    context={
        "check_python": True,           # enable Python syntax validation
        "use_llm_judge": True,          # enable Pro quality judge
        "expected_schema": None,        # JSON schema dict if output should be JSON
        "expected_tool_keys": None,     # list of strings that must appear in output
    },
)

print(result["output"])
print(result["initial_route"], "→", result["final_route"])
```

## File layout

```
llm_router/
├─ main.py                   entrypoint + demo
├─ requirements.txt
├─ config/
│   └─ litellm_config.yaml   LiteLLM proxy config
├─ graph/
│   ├─ state.py              State TypedDict + constants
│   ├─ nodes.py              all LangGraph node functions
│   └─ builder.py            graph assembly + make_initial_state()
├─ validators/
│   └─ deterministic.py      schema / syntax / tool / length / refusal checks
└─ telemetry/
    └─ logger.py             structured JSON-line logging + accuracy tracker
```
