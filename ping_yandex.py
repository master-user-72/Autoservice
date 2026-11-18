"""Проверка доступности Yandex AI Studio API с этого ПК.

Запуск: ping_yandex.bat  или  python ping_yandex.py

Читает LLM_API_KEY, LLM_FOLDER_ID, LLM_MODEL из .env
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import sys
import time
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

load_dotenv(".env", override=True)

HOSTS = (
    "ai.api.cloud.yandex.net",
    "llm.api.cloud.yandex.net",
)
BASE_URL = os.getenv("LLM_BASE_URL", "https://ai.api.cloud.yandex.net/v1").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "").strip()
FOLDER_ID = os.getenv("LLM_FOLDER_ID", "").strip()
MODEL = os.getenv("LLM_MODEL", "yandexgpt-lite").strip()


def step(title: str) -> None:
    print(f"\n=== {title} ===")


def ok(msg: str) -> None:
    print(f"OK   {msg}")


def fail(msg: str) -> None:
    print(f"FAIL {msg}")


def warn(msg: str) -> None:
    print(f"WARN {msg}")


def ping_dns(host: str) -> None:
    try:
        ip = socket.gethostbyname(host)
        ok(f"{host} -> {ip}")
    except OSError as exc:
        fail(f"{host}: DNS {exc}")


def ping_tcp(host: str, port: int = 443, timeout: float = 5.0) -> None:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok(f"{host}:{port} TCP доступен")
    except OSError as exc:
        fail(f"{host}:{port} TCP {exc}")


def ping_tls(host: str, port: int = 443, timeout: float = 10.0) -> None:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                ok(f"{host}:{port} TLS {tls.version()} cipher={tls.cipher()[0]}")
    except OSError as exc:
        fail(f"{host}:{port} TLS {exc}")


def ping_http(host: str, timeout: float = 15.0) -> None:
    url = f"https://{host}/"
    try:
        started = time.perf_counter()
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        elapsed = (time.perf_counter() - started) * 1000
        ok(f"{url} HTTP {response.status_code} ({elapsed:.0f} ms)")
    except Exception as exc:
        fail(f"{url} {type(exc).__name__}: {exc}")


def ping_api() -> None:
    if not API_KEY or not FOLDER_ID:
        warn("LLM_API_KEY или LLM_FOLDER_ID пусты — API-тест пропущен")
        return

    model = f"gpt://{FOLDER_ID}/{MODEL}/latest"
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json",
        "x-folder-id": FOLDER_ID,
        "x-data-logging-enabled": "false",
    }
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": "ping"}],
    }

    print(f"URL:   {BASE_URL}/chat/completions")
    print(f"Model: {model}")

    try:
        started = time.perf_counter()
        response = httpx.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=45.0,
        )
        elapsed = (time.perf_counter() - started) * 1000
        body = response.text[:300].replace("\n", " ")
        if response.is_success:
            ok(f"API HTTP {response.status_code} ({elapsed:.0f} ms)")
            try:
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                print(f"Ответ: {text[:120]}")
            except (KeyError, json.JSONDecodeError, IndexError):
                print(f"Тело: {body}")
        else:
            fail(f"API HTTP {response.status_code} ({elapsed:.0f} ms): {body}")
    except Exception as exc:
        fail(f"API {type(exc).__name__}: {exc}")


def main() -> int:
    parsed = urlparse(BASE_URL)
    primary_host = parsed.hostname or HOSTS[0]

    print("Проверка Yandex AI Studio API")
    print(f"BASE_URL: {BASE_URL}")
    print(f"KEY:      {'задан' if API_KEY else 'нет'} ({len(API_KEY)} симв.)")
    print(f"FOLDER:   {FOLDER_ID or 'нет'}")
    print(f"MODEL:    {MODEL}")

    step("1. DNS")
    for host in HOSTS:
        ping_dns(host)

    step("2. TCP 443")
    for host in HOSTS:
        ping_tcp(host)

    step("3. TLS handshake")
    for host in HOSTS:
        ping_tls(host)

    step("4. HTTP")
    for host in HOSTS:
        ping_http(host)

    step("5. API chat/completions")
    ping_api()

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
