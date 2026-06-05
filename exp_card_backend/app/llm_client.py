from __future__ import annotations

import json
import time
from typing import Any
from typing import List, Dict

from openai import OpenAI

from .config import settings


_client = OpenAI(
    api_key=settings.api_key,
    base_url=settings.base_url,
    timeout=settings.timeout_seconds,
)


class LLMError(RuntimeError):
    pass


def _extract_text_content(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        chunks: List[str] = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
        return "\n".join(chunks).strip()
    return str(message_content)


def chat_completion(messages: List[Dict[str, Any]], model: str | None = None) -> str:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries + 1):
        try:
            response = _client.chat.completions.create(
                model=model or settings.chat_model,
                messages=messages,
                temperature=settings.temperature,
            )
            return _extract_text_content(response.choices[0].message.content).strip()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < settings.max_retries:
                time.sleep(1 + attempt)
                continue
            raise LLMError(f"LLM call failed: {exc}") from exc
    raise LLMError(f"LLM call failed: {last_error}")


def vision_completion(prompt_text: str, image_data_url: str) -> str:
    if not settings.support_image_input:
        raise LLMError(
            "Current config disables image input. Set llm.support_image_input=true if your internal gateway supports vision."
        )

    messages: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]
    return chat_completion(messages, model=settings.vision_model)


def extract_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        return json.loads(candidate)

    raise ValueError("Model output is not valid JSON")
