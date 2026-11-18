"""Подтверждённые формулировки → SQLite. Без привязки к Яндексу или другому LLM."""

from __future__ import annotations

import re
from typing import Any

from app import db
from app.garage import extract_make, extract_plate, extract_plate_digits
from app.kits import GRM_KIT_KEY, GRM_KIT_NAME, is_grm_kit_phrase
from app.models import ParsedItem


def normalize_phrase(text: str) -> str:
    body = (text or "").lower().replace("ё", "е")
    body = re.sub(r"[^\w\s-]", " ", body, flags=re.UNICODE)
    return re.sub(r"\s+", " ", body).strip()


def _clean_vin(value: str | None) -> str | None:
    if not value:
        return None
    compact = "".join(ch.upper() for ch in value if ch.isascii() and ch.isalnum())
    for i in range(0, max(0, len(compact) - 16)):
        candidate = compact[i : i + 17]
        if len(candidate) == 17 and candidate.isalnum() and not any(ch in candidate for ch in "IOQ"):
            return candidate
    return None


def phrase_key_from_raw(raw: str, vin: str | None = None) -> str:
    body = raw or ""
    found = (vin or "").strip().upper() or _clean_vin(body) or ""
    if found:
        body = re.sub(re.escape(found), " ", body, flags=re.IGNORECASE)
    plate = extract_plate(body)
    if plate:
        body = re.sub(re.escape(plate), " ", body, flags=re.IGNORECASE)
        digits = "".join(ch for ch in plate if ch.isdigit())
        if len(digits) >= 3:
            body = re.sub(re.escape(digits), " ", body)
    else:
        digits = extract_plate_digits(body)
        if digits:
            body = re.sub(re.escape(digits), " ", body)
    make = extract_make(body)
    if make:
        body = re.sub(rf"\b{re.escape(make)}\b", " ", body, flags=re.IGNORECASE)
    body = re.sub(r"\bвин\b|\bvin\b|\bгосномер\b|\bгос\.?\s*номер\b", " ", body, flags=re.IGNORECASE)
    return normalize_phrase(body)


def items_from_learned(row: dict[str, Any]) -> list[ParsedItem]:
    out: list[ParsedItem] = []
    for raw in row.get("items") or []:
        if isinstance(raw, str):
            desc = raw.strip()
            if desc:
                out.append(ParsedItem(description=desc, quantity=1, kit_key=row.get("kit_key") or None))
            continue
        desc = str(raw.get("description") or "").strip()
        if not desc:
            continue
        out.append(
            ParsedItem(
                description=desc,
                quantity=max(1, int(raw.get("quantity") or 1)),
                original_required=bool(raw.get("original_required")),
                urgent=bool(raw.get("urgent")),
                kit_key=(raw.get("kit_key") or row.get("kit_key") or None) or None,
            )
        )
    return out


def remember_confirmed_request(request_id: int | None) -> bool:
    """Пишет фразу в базу, когда по заявке не осталось позиций на проверке."""
    if not request_id:
        return False
    req = db.get_request(int(request_id))
    if not req:
        return False
    rows = db.list_items_for_request(int(request_id))
    if not rows:
        return False
    if any((row.get("status") or "") == "pending_review" for row in rows):
        return False
    confirmed = [row for row in rows if (row.get("status") or "") == "confirmed"]
    if not confirmed:
        return False
    phrase = phrase_key_from_raw(req.get("raw_text") or "", req.get("vin"))
    if len(phrase) < 6:
        return False
    kit_keys = {(row.get("kit_key") or "").strip() for row in confirmed if (row.get("kit_key") or "").strip()}
    if kit_keys == {GRM_KIT_KEY} or (len(confirmed) > 1 and all(is_grm_kit_phrase(row.get("description") or "") or row.get("kit_key") == GRM_KIT_KEY for row in confirmed)):
        payload = [{"description": GRM_KIT_NAME, "original_required": False, "urgent": any(bool(r.get("urgent")) for r in confirmed)}]
        kit_key = GRM_KIT_KEY
    else:
        payload = []
        seen: set[str] = set()
        for row in confirmed:
            desc = (row.get("description") or row.get("name") or "").strip()
            if not desc:
                continue
            key = desc.lower()
            if key in seen:
                continue
            seen.add(key)
            payload.append(
                {
                    "description": desc,
                    "quantity": max(1, int(row.get("quantity") or 1)),
                    "original_required": bool(row.get("original_required")),
                    "urgent": bool(row.get("urgent")),
                    "kit_key": (row.get("kit_key") or "").strip(),
                }
            )
        kit_key = next(iter(kit_keys)) if len(kit_keys) == 1 else ""
        if len(payload) == 1 and normalize_phrase(payload[0]["description"]) == phrase:
            return False
    if not payload:
        return False
    db.set_learned_phrase(phrase, payload, kit_key)
    return True
