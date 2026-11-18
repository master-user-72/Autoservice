from __future__ import annotations

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
}


def client(**kwargs) -> httpx.Client:
    opts = {"headers": HEADERS, "follow_redirects": True, "timeout": 25.0}
    opts.update(kwargs)
    return httpx.Client(**opts)
