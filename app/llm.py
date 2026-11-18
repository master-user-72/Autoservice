"""Единая точка вызова LLM. Смена провайдера — только .env, без правок лота и гаража."""

from __future__ import annotations

from typing import Any

import httpx

from app.log import get_logger
from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_FOLDER_ID,
    LLM_MODEL,
    LLM_PROVIDER,
    QWEN_API_KEY,
    QWEN_BASE_URL,
    QWEN_FALLBACK,
    QWEN_MODEL,
)

_OFF = {"off", "none", "local", "disabled"}
log = get_logger("llm")


def _primary_ready() -> bool:
    if LLM_PROVIDER in _OFF:
        return False
    if LLM_PROVIDER == "qwen":
        return bool(QWEN_API_KEY)
    return bool(LLM_API_KEY)


def _qwen_fallback_ready() -> bool:
    return QWEN_FALLBACK and bool(QWEN_API_KEY)


def llm_enabled() -> bool:
    if LLM_PROVIDER in _OFF:
        return False
    if _primary_ready():
        return True
    return LLM_PROVIDER == "yandex" and _qwen_fallback_ready()


def provider_name() -> str:
    if not llm_enabled():
        return "off"
    if LLM_PROVIDER == "yandex" and _qwen_fallback_ready():
        return "yandex+qwen"
    return LLM_PROVIDER or "openai"


def _yandex_model_name() -> str:
    model = (LLM_MODEL or "yandexgpt").strip()
    if LLM_FOLDER_ID:
        model = model.replace("FOLDER_ID", LLM_FOLDER_ID)
    if model.startswith("gpt://"):
        return model
    slug = model.strip("/") or "yandexgpt"
    if slug.endswith("/latest"):
        slug = slug[: -len("/latest")]
    if LLM_FOLDER_ID:
        return f"gpt://{LLM_FOLDER_ID}/{slug}/latest"
    return slug


def _provider_chain() -> list[str]:
    if LLM_PROVIDER in _OFF:
        return []
    if LLM_PROVIDER == "yandex":
        chain = ["yandex"] if _primary_ready() else []
        if _qwen_fallback_ready() and "qwen" not in chain:
            chain.append("qwen")
        return chain
    if LLM_PROVIDER == "qwen" and QWEN_API_KEY:
        return ["qwen"]
    if LLM_PROVIDER == "openai" and LLM_API_KEY:
        return ["openai"]
    if LLM_API_KEY:
        return [LLM_PROVIDER or "openai"]
    return []


def _request_config(provider: str) -> tuple[str, dict[str, str], str, bool]:
    """base_url, headers, model, use_json_response_format."""
    if provider == "yandex":
        headers = {
            "Authorization": f"Api-Key {LLM_API_KEY}",
            "Content-Type": "application/json",
            "x-data-logging-enabled": "false",
        }
        if LLM_FOLDER_ID:
            headers["x-folder-id"] = LLM_FOLDER_ID
        return LLM_BASE_URL, headers, _yandex_model_name(), False
    if provider == "qwen":
        return (
            QWEN_BASE_URL,
            {
                "Authorization": f"Bearer {QWEN_API_KEY}",
                "Content-Type": "application/json",
            },
            QWEN_MODEL or "qwen-plus",
            True,
        )
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    if LLM_FOLDER_ID:
        headers["x-folder-id"] = LLM_FOLDER_ID
    return LLM_BASE_URL, headers, (LLM_MODEL or "gpt-4o-mini"), True


def _chat_provider(provider: str, system: str, user: str, *, timeout: float) -> dict[str, Any]:
    base_url, headers, model, json_mode = _request_config(provider)
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    url = f"{base_url}/chat/completions"
    log.debug("LLM запрос %s model=%s", provider, model)
    response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    if response.is_error:
        body = response.text[:300].replace("\n", " ")
        log.warning("LLM %s HTTP %s: %s", provider, response.status_code, body)
    response.raise_for_status()
    log.info("LLM %s OK model=%s", provider, model)
    return response.json()


def chat_json(system: str, user: str, *, timeout: float = 45.0) -> dict[str, Any]:
    """Chat Completions, ответ — JSON-объект. Yandex → Qwen при сбое основного."""
    if not llm_enabled():
        raise RuntimeError("LLM выключен")
    chain = _provider_chain()
    if not chain:
        raise RuntimeError("LLM не настроен")
    last_error: Exception | None = None
    log.info("LLM цепочка: %s", " → ".join(chain))
    for provider in chain:
        try:
            return _chat_provider(provider, system, user, timeout=timeout)
        except Exception as exc:
            last_error = exc
            log.warning("LLM %s недоступен: %s: %s", provider, type(exc).__name__, exc)
            if provider != chain[-1]:
                log.info("LLM переключение на запасной провайдер")
                continue
            raise
    raise RuntimeError("LLM не настроен") from last_error
