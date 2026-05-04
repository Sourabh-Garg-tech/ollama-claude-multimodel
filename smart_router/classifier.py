import re


def classify(messages: list[dict]) -> str:
    """Classify a conversation based on the latest user message and history."""
    text = _extract_text(messages)
    length = len(text)

    if _is_lookup(text, length):
        return "lookup"
    if _is_planning(text):
        return "planning"
    if _is_code(text):
        return "code"
    if _is_complex(text, length):
        return "complex"
    return "default"


def classify_description(description: str) -> str:
    """Classify a plain-text task description (for the launcher GUI)."""
    messages = [{"role": "user", "content": description}]
    return classify(messages)


def _extract_text(messages: list[dict]) -> str:
    parts = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    parts.append(block.get("content", ""))
        else:
            parts.append(content)
    return "\n".join(parts)


def _is_lookup(text: str, length: int) -> bool:
    if length > 300:
        return False
    patterns = [
        r"^(what is|how (do|can|to)|explain|define|lookup|find|search)",
        r"\?$",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _is_planning(text: str) -> bool:
    keywords = [
        "architecture", "design", "strategy", "plan", "roadmap",
        "structure", "organize", "approach", "blueprint", "system design",
    ]
    return any(kw in text.lower() for kw in keywords)


def _is_code(text: str) -> bool:
    code_indicators = [
        r"```[a-z]*\n",
        r"\.(py|js|ts|tsx|go|rs|java|cpp|c|h)\b",
        r"\b(fix|debug|implement|refactor|build|compile|test|deploy|commit)\b",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in code_indicators)


def _is_complex(text: str, length: int) -> bool:
    if length < 1500:
        return False
    keywords = ["analyze", "compare", "evaluate", "assess", "review", "deep dive"]
    return any(kw in text.lower() for kw in keywords)
