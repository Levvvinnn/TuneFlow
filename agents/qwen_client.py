"""
Centralized Qwen Cloud API client.
All text and vision calls route through here. Model identifiers come from env vars.
"""
import base64
import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# Model identifiers — override via env to match what's available in your Qwen Cloud console
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-plus")
QWEN_OPTIMIZER_MODEL = os.getenv("QWEN_OPTIMIZER_MODEL", "qwen-max")
QWEN_VISION_MODEL = os.getenv("QWEN_VISION_MODEL", "qwen-vl-plus")

TIMEOUT = 120.0


def _raise_with_body(resp: httpx.Response) -> None:
    """Like resp.raise_for_status(), but includes the response body in the
    exception message. httpx's default HTTPStatusError text is just
    "Client error '403 Forbidden' for url '...'" — it discards the body,
    which is exactly where DashScope puts the actual reason (bad model id,
    expired key, no quota, workspace mismatch, etc). Without this, a 403
    is unactionable; with it, the real cause shows up in the logs directly.
    """
    if resp.status_code >= 400:
        body = resp.text[:2000]
        raise httpx.HTTPStatusError(
            f"{resp.status_code} {resp.reason_phrase} for url '{resp.url}' — response body: {body}",
            request=resp.request,
            response=resp,
        )


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=QWEN_BASE_URL,
        headers={
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=TIMEOUT,
    )


async def text_completion(
    prompt: str,
    system: str = "You are a backend performance optimization expert.",
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    response_format: Optional[dict] = None,
) -> str:
    """Send a text prompt and return the completion string."""
    if not QWEN_API_KEY:
        raise EnvironmentError("QWEN_API_KEY is not set")

    model = model or QWEN_TEXT_MODEL
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    async with _client() as client:
        resp = await client.post("/chat/completions", json=payload)
        _raise_with_body(resp)
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def json_completion(
    prompt: str,
    system: str = "You are a backend performance optimization expert. Respond with valid JSON only.",
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> dict:
    """Send a prompt and parse the response as JSON. Strips markdown fences if present."""
    raw = await text_completion(
        prompt=prompt,
        system=system,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Qwen response was not valid JSON: {e}\nRaw: {raw[:500]}")


async def vision_completion(
    prompt: str,
    image_path: str,
    system: str = "You are a performance monitoring expert analyzing charts.",
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """Send a text prompt + chart image and return diagnosis text."""
    if not QWEN_API_KEY:
        raise EnvironmentError("QWEN_API_KEY is not set")

    model = model or QWEN_VISION_MODEL

    # Encode image as base64
    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    # Detect mime type from extension
    ext = Path(image_path).suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext.lstrip("."), "image/png")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with _client() as client:
        resp = await client.post("/chat/completions", json=payload)
        _raise_with_body(resp)
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def optimizer_completion(prompt: str, system: str, temperature: float = 0.1) -> dict:
    """Use the stronger optimizer model for tradeoff decisions."""
    return await json_completion(
        prompt=prompt,
        system=system,
        model=QWEN_OPTIMIZER_MODEL,
        temperature=temperature,
    )


async def config_agent_completion(prompt: str, system: str) -> dict:
    """Lighter model for Config Agent baseline proposals."""
    return await json_completion(
        prompt=prompt,
        system=system,
        model=QWEN_TEXT_MODEL,
        temperature=0.15,
    )


async def baseline_god_agent_completion(prompt: str, system: str) -> dict:
    """Single-agent baseline: one Qwen call does propose+diagnose+decide."""
    return await json_completion(
        prompt=prompt,
        system=system,
        model=QWEN_TEXT_MODEL,
        temperature=0.2,
    )
