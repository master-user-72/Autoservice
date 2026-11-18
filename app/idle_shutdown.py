"""Остановка сервера, если браузер закрыт и нет запросов к API."""

from __future__ import annotations

import os
import threading
import time

IDLE_SECONDS = int(os.getenv("AGENT_IDLE_SECONDS", "12"))
ENABLED = os.getenv("AGENT_SHUTDOWN_ON_CLOSE") == "1"

_last_touch = time.time()
_watchdog_started = False


def touch() -> None:
    global _last_touch
    _last_touch = time.time()


def start_watchdog() -> None:
    global _watchdog_started
    if not ENABLED or _watchdog_started:
        return
    _watchdog_started = True
    touch()

    def loop() -> None:
        while True:
            time.sleep(2)
            if time.time() - _last_touch > IDLE_SECONDS:
                os._exit(0)

    threading.Thread(target=loop, name="agent-idle-shutdown", daemon=True).start()
