"""Тест Yandex AI Studio. Ключи берутся из .env (LLM_API_KEY, LLM_FOLDER_ID, LLM_MODEL)."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv(".env", override=True)

YANDEX_API_KEY = os.getenv("LLM_API_KEY", "").strip()
YANDEX_FOLDER_ID = os.getenv("LLM_FOLDER_ID", "").strip()
YANDEX_MODEL = os.getenv("LLM_MODEL", "yandexgpt-lite").strip()
YANDEX_BASE_URL = os.getenv("LLM_BASE_URL", "https://ai.api.cloud.yandex.net/v1").rstrip("/")

if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
    sys.exit("Заполните LLM_API_KEY и LLM_FOLDER_ID в .env")

try:
    import openai
except ImportError:
    sys.exit("Установите: pip install openai")

# URI модели: gpt://<каталог>/<модель>/latest
model_uri = f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_MODEL}/latest"

client = openai.OpenAI(
    api_key=YANDEX_API_KEY,
    base_url=YANDEX_BASE_URL,
    project=YANDEX_FOLDER_ID,
    default_headers={
        "x-folder-id": YANDEX_FOLDER_ID,
        "x-data-logging-enabled": "false",
    },
)

print(f"URL:   {YANDEX_BASE_URL}")
print(f"Model: {model_uri}")
print()

# Responses API (рекомендуемый путь Yandex AI Studio)
response = client.responses.create(
    model=model_uri,
    input="Придумай 3 необычные идеи для стартапа в сфере путешествий.",
    temperature=0.8,
    max_output_tokens=1500,
)

# Было неверно: response.output.content.text
print(response.output_text)
