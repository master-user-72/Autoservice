"""Local access by default; optional signed sessions for an HTTPS deployment."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from collections import OrderedDict
from threading import Lock

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

USERS = json.loads(os.getenv("AUTOSERVICE_USERS", "{}"))
SECRET = os.getenv("AUTOSERVICE_SESSION_KEY", "").encode()
if USERS and len(SECRET) < 32:
    raise RuntimeError("AUTOSERVICE_SESSION_KEY must contain at least 32 bytes")
ROLES = {"employee", "buyer", "admin"}
if any(not username or not account.get("password") or account.get("role") not in ROLES
       for username, account in USERS.items()):
    raise RuntimeError("Invalid AUTOSERVICE_USERS configuration")


def signature(value):
    return hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()


_attempts = OrderedDict()
_login_lock = Lock()


def login(request, username, password):
    ip = request.client.host if request.client else ""
    with _login_lock:
        now = time.monotonic()
        start, count = _attempts.get(ip, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        if count >= 10:
            raise HTTPException(429, "Подождите минуту перед новой попыткой")
        _attempts[ip] = (start, count + 1)
        _attempts.move_to_end(ip)
        if len(_attempts) > 2048:
            _attempts.popitem(last=False)
    account = USERS.get(username)
    if not account or not hmac.compare_digest(account["password"].encode(), password.encode()):
        raise HTTPException(401, "Неверное имя или пароль")
    with _login_lock:
        _attempts.pop(ip, None)
    encoded = base64.urlsafe_b64encode(username.encode()).decode()
    value = f"{encoded}:{int(time.time()) + 8 * 3600}"
    response = JSONResponse({"ok": True})
    response.set_cookie("autoservice", f"{value}:{signature(value)}", max_age=8 * 3600,
                        httponly=True, secure=True, samesite="strict", path="/")
    return response


def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("autoservice", secure=True, httponly=True, samesite="strict")
    return response


def session(request):
    raw = request.cookies.get("autoservice", "")
    encoded, sep, rest = raw.partition(":")
    expires, _, sig = rest.partition(":")
    try:
        username = base64.urlsafe_b64decode(encoded).decode()
    except (ValueError, UnicodeError, binascii.Error):
        return None
    account = USERS.get(username)
    if sep and account and expires.isascii() and expires.isdigit() and len(expires) <= 12             and int(expires) > time.time():
        if hmac.compare_digest(signature(f"{encoded}:{expires}"), sig):
            return {"name": username, "role": account["role"]}
    return None


def permitted(request: Request, *roles):
    actor = request.state.user
    if roles and actor["role"] not in roles:
        raise HTTPException(403, "Недостаточно прав для операции")
    return actor["name"]


async def guard(request, call_next):
    path = request.url.path
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") in {"cross-site", "same-site"} or (
            origin and origin != f"{request.url.scheme}://{request.url.netloc}"
        ):
            return JSONResponse({"detail": "Запрос с другого сайта отклонён"}, 403)
    if not USERS:
        client = request.client.host if request.client else ""
        if client not in {"127.0.0.1", "::1"} or request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse({"detail": "Для общего доступа настройте пользователей и HTTPS"}, 403)
        request.state.user = {"name": "Демо-сотрудник", "role": "admin"}
    else:
        if request.url.scheme != "https":
            return JSONResponse({"detail": "Для общего доступа требуется HTTPS"}, 403)
        if path in {"/login", "/api/workspace/login", "/api/health"} or path.startswith("/static/"):
            return await call_next(request)
        user = session(request)
        if not user:
            return (JSONResponse({"detail": "Войдите в систему"}, 401) if path.startswith("/api/")
                    else RedirectResponse("/login", status_code=303))
        request.state.user = user
        if (path.startswith("/api/") and not path.startswith("/api/workspace/")) or path in {"/classic", "/archive"}:
            return JSONResponse({"detail": "Локальные старые маршруты доступны только в локальном режиме"}, 403)
    response = await call_next(request)
    if not path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response
