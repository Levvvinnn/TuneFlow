"""
Compatibility shim — re-exports everything from fireworks_client.

Stale __pycache__ bytecode in some agent files may still contain
`from qwen_client import ...` compiled before the Fireworks AI migration.
This file satisfies those imports transparently so old .pyc files don't
need to be manually hunted down.

Do not add new code here. Use fireworks_client directly for all new work.
"""
from fireworks_client import (  # noqa: F401
    FIREWORKS_API_KEY as QWEN_API_KEY,
    FIREWORKS_BASE_URL as QWEN_BASE_URL,
    FIREWORKS_TEXT_MODEL as QWEN_TEXT_MODEL,
    FIREWORKS_OPTIMIZER_MODEL as QWEN_OPTIMIZER_MODEL,
    FIREWORKS_VISION_MODEL as QWEN_VISION_MODEL,
    text_completion,
    json_completion,
    vision_completion,
    optimizer_completion,
    config_agent_completion,
    baseline_god_agent_completion,
)
