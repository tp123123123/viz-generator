from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_VISION_MODEL


class LLMNotConfigured(RuntimeError):
    pass


def require_llm() -> None:
    if not OPENAI_API_KEY:
        raise LLMNotConfigured("未配置 OPENAI_API_KEY，无法调用模型。请复制 webapp/.env.example 为 .env 并填入密钥。")


def client() -> OpenAI:
    require_llm()
    kwargs: dict[str, Any] = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return OpenAI(**kwargs)


def _message_text(message) -> str:
    text = (message.content or "").strip()
    if text:
        return text
    extra = getattr(message, "reasoning_content", None)
    if extra:
        return str(extra).strip()
    return ""


def chat_text(system: str, user: str, *, temperature: float = 0.2) -> str:
    resp = client().chat.completions.create(
        model=OPENAI_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        extra_body={"thinking": {"type": "disabled"}},
    )
    return _message_text(resp.choices[0].message)


def chat_vision(system: str, user: str, image_png: bytes, *, temperature: float = 0.1) -> str:
    import base64

    b64 = base64.b64encode(image_png).decode("ascii")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
            ],
        },
    ]
    extras: list[dict[str, Any]] = [
        {"thinking": {"type": "disabled"}, "response_format": {"type": "json_object"}},
        {"thinking": {"type": "disabled"}},
    ]
    last_err: Exception | None = None
    for extra in extras:
        try:
            resp = client().chat.completions.create(
                model=OPENAI_VISION_MODEL,
                temperature=temperature,
                messages=messages,
                extra_body=extra,
            )
            return _message_text(resp.choices[0].message)
        except Exception as exc:  # noqa: BLE001 — 兼容智谱不支持 json_object 的情况
            last_err = exc
            continue
    raise last_err or RuntimeError("视觉审查调用失败")


def extract_python(text: str) -> str:
    fence = re.search(r"```(?:python)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text.strip()


def _repair_json_text(raw: str) -> str:
    s = raw.strip()
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def extract_json(text: str) -> dict[str, Any]:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    raw = fence.group(1).strip() if fence else text.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("模型未返回 JSON")
    blob = raw[start : end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        data = json.loads(_repair_json_text(blob))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点不是对象")
    return data
