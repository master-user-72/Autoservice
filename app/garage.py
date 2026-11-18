from __future__ import annotations

import re
from typing import Any, Optional

from app import db

LATIN_TO_PLATE = str.maketrans({
    "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "H": "Н",
    "O": "О", "P": "Р", "C": "С", "T": "Т", "Y": "У", "X": "Х",
})
PLATE_LETTERS = "АВЕКМНОРСТУХ"
PLATE_RE = re.compile(
    rf"([{PLATE_LETTERS}A-Z])\s*(\d{{3}})\s*([{PLATE_LETTERS}A-Z]{{2}})\s*(\d{{2,3}})",
    re.IGNORECASE,
)

MAKE_ALIASES: dict[str, str] = {
    "тойота": "Toyota",
    "toyota": "Toyota",
    "лада": "Lada",
    "ваз": "Lada",
    "веста": "Lada",
    "lada": "Lada",
    "хендай": "Hyundai",
    "хундай": "Hyundai",
    "hyundai": "Hyundai",
    "киа": "Kia",
    "kia": "Kia",
    "фольксваген": "Volkswagen",
    "volkswagen": "Volkswagen",
    "vw": "Volkswagen",
    "шкода": "Skoda",
    "skoda": "Skoda",
    "ниссан": "Nissan",
    "nissan": "Nissan",
    "митсубиси": "Mitsubishi",
    "mitsubishi": "Mitsubishi",
    "форд": "Ford",
    "ford": "Ford",
    "рено": "Renault",
    "renault": "Renault",
    "bmw": "BMW",
    "бмв": "BMW",
    "мерседес": "Mercedes",
    "mercedes": "Mercedes",
    "audi": "Audi",
    "ауди": "Audi",
    "мазда": "Mazda",
    "mazda": "Mazda",
    "chevrolet": "Chevrolet",
    "шевроле": "Chevrolet",
    "уаз": "UAZ",
    "газ": "GAZ",
    "камаз": "Kamaz",
    "suzuki": "Suzuki",
    "сузуки": "Suzuki",
    "honda": "Honda",
    "хонда": "Honda",
    "lexus": "Lexus",
    "лексус": "Lexus",
    "subaru": "Subaru",
    "субару": "Subaru",
    "geely": "Geely",
    "джили": "Geely",
    "haval": "Haval",
    "хавейл": "Haval",
    "chery": "Chery",
    "чери": "Chery",
    "опель": "Opel",
    "opel": "Opel",
}


def normalize_plate(value: str | None) -> Optional[str]:
    if not value:
        return None
    raw = value.upper().translate(LATIN_TO_PLATE)
    raw = re.sub(r"[\s\-]+", "", raw)
    match = PLATE_RE.search(raw) or PLATE_RE.search(value.upper().translate(LATIN_TO_PLATE))
    if not match:
        return None
    letter1, digits, letters, region = match.groups()
    plate = f"{letter1.translate(LATIN_TO_PLATE)}{digits}{letters.translate(LATIN_TO_PLATE)}{region}"
    if not re.fullmatch(rf"[{PLATE_LETTERS}]\d{{3}}[{PLATE_LETTERS}]{{2}}\d{{2,3}}", plate):
        return None
    return plate


def extract_plate_digits(text: str) -> Optional[str]:
    """Цифры госномера без букв: 123, 12372."""
    if not text:
        return None
    stripped = re.sub(r"\bvin\b|\bвин\b", " ", text, flags=re.IGNORECASE)
    stripped = re.sub(r"[A-HJ-NPR-Z0-9]{17}", " ", stripped, flags=re.IGNORECASE)
    compact = "".join(ch.upper() for ch in stripped if ch.isascii() and ch.isalnum())
    for i in range(0, max(0, len(compact) - 16)):
        cand = compact[i : i + 17]
        if cand.isalnum() and not any(ch in cand for ch in "IOQ"):
            compact = compact[:i] + compact[i + 17 :]
            break
    chunks = re.findall(r"\d{3,6}", stripped)
    if not chunks:
        glued = re.sub(r"\D+", "", stripped) or "".join(ch for ch in compact if ch.isdigit())
        if 3 <= len(glued) <= 6:
            chunks = [glued]
    if not chunks:
        leftover = "".join(ch for ch in compact if ch.isdigit())
        leftover_chunks = re.findall(r"\d{3,6}", leftover)
        chunks = leftover_chunks
    if not chunks:
        return None
    chunks.sort(key=len, reverse=True)
    return chunks[0]


def extract_plate(text: str) -> Optional[str]:
    translated = text.upper().translate(LATIN_TO_PLATE)
    match = PLATE_RE.search(translated)
    if match:
        return normalize_plate("".join(match.groups()))
    compact = re.sub(r"[\s\-]+", "", translated)
    match = PLATE_RE.search(compact)
    if match:
        return normalize_plate("".join(match.groups()))
    return extract_plate_digits(text)


def extract_make(text: str) -> Optional[str]:
    blob = text.lower().replace("ё", "е")
    for alias, canon in sorted(MAKE_ALIASES.items(), key=lambda item: -len(item[0])):
        stem = alias[:-1] if alias[-1:] in "аяуыиеa" and len(alias) > 3 else alias
        if re.search(rf"(?<![a-zа-я]){re.escape(stem)}[а-яa-z]{{0,4}}(?![a-zа-я])", blob):
            return canon
    return None


def format_plate(plate: str) -> str:
    if len(plate) >= 8:
        return f"{plate[0]} {plate[1:4]} {plate[4:6]} {plate[6:]}"
    return plate


def resolve_vin(vin: str | None, plate: str | None, make: str | None) -> tuple[Optional[str], Optional[dict[str, Any]], Optional[str]]:
    """Вернуть (vin, запись гаража, вопрос)."""
    if vin:
        row = db.get_vehicle_by_vin(vin)
        return vin, row, None

    plate_n = normalize_plate(plate) if plate else None
    digits = "".join(ch for ch in (plate or "") if ch.isdigit()) if plate else ""
    if plate_n:
        row = db.get_vehicle_by_plate(plate_n)
        if row:
            return row["vin"], row, None
        digit_hits = db.find_vehicles_by_digits(digits) if len(digits) >= 3 else []
        if len(digit_hits) == 1:
            return digit_hits[0]["vin"], digit_hits[0], None
        return None, None, f"Госномер {format_plate(plate_n)} не найден в гараже. Добавьте VIN, марку и номер."

    if len(digits) >= 3:
        rows = db.find_vehicles_by_digits(digits)
        if len(rows) == 1:
            return rows[0]["vin"], rows[0], None
        if len(rows) > 1:
            listed = ", ".join(f"{r['make']} {format_plate(r['plate'])}" for r in rows if r.get("plate"))
            return None, None, f"По цифрам {digits} несколько машин: {listed}. Назовите госномер целиком или марку."
        return None, None, f"Госномер с цифрами {digits} не найден в гараже. Добавьте VIN, марку и номер."

    if make:
        rows = db.find_vehicles_by_make(make)
        if len(rows) == 1:
            return rows[0]["vin"], rows[0], None
        if len(rows) > 1:
            listed = ", ".join(f"{r['make']} {format_plate(r['plate'])}" for r in rows if r.get("plate"))
            return None, None, f"Несколько машин марки {make}: {listed}. Назовите госномер."
        return None, None, f"Марка {make} не найдена в гараже. Добавьте VIN и госномер."

    return None, None, None


def remember(vin: str, make: str | None = None, plate: str | None = None, **spec: Any) -> Optional[dict[str, Any]]:
    if not vin:
        return None
    from app.vin_decode import decode_vin

    plate_n = normalize_plate(plate) if plate else None
    existing = db.get_vehicle_by_vin(vin) or {}
    need_live = not (existing.get("model") or spec.get("model"))
    decoded = decode_vin(vin, live=need_live)
    payload = dict(decoded)
    payload.update({k: v for k, v in spec.items() if str(v or "").strip()})
    make_val = make or existing.get("make") or payload.get("make") or ""
    plate_val = plate_n or existing.get("plate") or payload.get("plate") or ""
    payload.pop("vin", None)
    payload.pop("make", None)
    payload.pop("plate", None)
    if not make_val and not plate_val and not payload.get("spec_key"):
        return existing or None
    row = db.upsert_vehicle(vin=vin, make=make_val, plate=plate_val, **payload)
    try:
        from app.catalog import remember_trim

        remember_trim(
            make=row.get("make") or make_val,
            model=row.get("model") or payload.get("model") or "",
            year=row.get("year") or payload.get("year") or "",
            engine=row.get("engine") or payload.get("engine") or "",
            body=row.get("body") or payload.get("body") or "",
        )
    except Exception:
        pass
    return row


def format_vehicle(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    bits = [
        row.get("make") or "",
        row.get("model") or "",
        row.get("year") or "",
        row.get("engine") or row.get("displacement") or "",
        row.get("series") or "",
    ]
    return " ".join(part for part in bits if part).strip()


def spec_key_of(row: dict[str, Any] | None, vin: str | None = None) -> str:
    if row and (row.get("spec_key") or "").strip():
        return str(row["spec_key"]).strip()
    from app.vin_decode import spec_key_from_vin

    return spec_key_from_vin((row or {}).get("vin") or vin or "")
