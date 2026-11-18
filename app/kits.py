from __future__ import annotations

import re
from typing import Any, Optional

from app import db, garage
from app.models import ParsedItem
from app.vin_decode import spec_key_from_vin

GRM_KIT_NAME = "комплект ГРМ"
GRM_KIT_KEY = "grm"
CHAIN_KIT_NAME = "комплект цепи ГРМ"
CHAIN_KIT_KEY = "chain"

CHAIN_KIT_RE = re.compile(
    r"(?:комплект|набор).{0,40}цеп(?:ь|и).{0,20}(?:грм|распредвала)"
    r"|(?:замен[аые].{0,20})?цеп(?:ь|и)\s+(?:грм|распредвала)",
    re.IGNORECASE,
)

GRM_KIT_RE = re.compile(
    r"^(?:(?:вс[её]|полный)\s+)?"
    r"(?:(?:комплект|набор)\s+)?"
    r"(?:для\s+)?"
    r"(?:замен[аые]\s+)?"
    r"грм$",
    re.IGNORECASE,
)

DEFAULT_KITS: dict[str, list[dict[str, str]]] = {
    GRM_KIT_KEY: [
        {"name": "ремень ГРМ", "article": ""},
        {"name": "ролик натяжной ГРМ", "article": ""},
        {"name": "ролик обводной ГРМ", "article": ""},
        {"name": "помпа водяная", "article": ""},
        {"name": "прокладка помпы", "article": ""},
        {"name": "шкив коленвала", "article": ""},
        {"name": "болт шкива коленвала", "article": ""},
        {"name": "сальник коленвала передний", "article": ""},
    ],
    CHAIN_KIT_KEY: [
        {"name": "цепь ГРМ", "article": ""},
        {"name": "натяжитель цепи ГРМ", "article": ""},
        {"name": "успокоитель цепи ГРМ", "article": ""},
        {"name": "направляющая цепи ГРМ", "article": ""},
        {"name": "прокладка клапанной крышки", "article": ""},
        {"name": "болты клапанной крышки", "article": ""},
    ],
}

KIT_TITLES = {GRM_KIT_KEY: "Комплект ГРМ", CHAIN_KIT_KEY: "Комплект цепи ГРМ"}

_SLUG_TR = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
})


def normalize_kit_key(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip().lower().replace("ё", "е"))
    if not cleaned:
        return GRM_KIT_KEY
    if is_grm_kit_phrase(cleaned) or cleaned in {"грм", "комплект грм", "kit-grm", GRM_KIT_KEY}:
        return GRM_KIT_KEY
    slug = cleaned.translate(_SLUG_TR)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or GRM_KIT_KEY


def is_grm_kit_phrase(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (text or "").strip(" .,-"))
    if cleaned.lower() == GRM_KIT_NAME.lower():
        return True
    return bool(GRM_KIT_RE.fullmatch(cleaned))


def is_chain_kit_phrase(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (text or "").strip(" .,-"))
    if cleaned.lower() == CHAIN_KIT_NAME.lower():
        return True
    return bool(CHAIN_KIT_RE.search(cleaned))


def kit_key_for(description: str) -> Optional[str]:
    if is_grm_kit_phrase(description):
        return GRM_KIT_KEY
    if is_chain_kit_phrase(description):
        return CHAIN_KIT_KEY
    from app.learn import normalize_phrase

    row = db.get_learned_phrase(normalize_phrase(description))
    if row and row.get("kit_key"):
        return row["kit_key"]
    return None


def looks_like_article(token: str) -> bool:
    text = (token or "").strip()
    if len(text) < 4:
        return False
    if re.search(r"[а-яё]", text, re.I) and not re.search(r"\d", text):
        return False
    return bool(re.search(r"\d", text))


def parse_part_line(line: str) -> Optional[dict[str, str]]:
    raw = re.sub(r"\s+", " ", (line or "").strip(" \t;,-"))
    if not raw or raw.startswith("#"):
        return None
    raw = raw.replace(";", " ").replace("\t", " ")
    if "," in raw:
        left, right = raw.split(",", 1)
        if looks_like_article(left) and not looks_like_article(right):
            return {"article": left.strip(), "name": right.strip()}
        if looks_like_article(right) and not looks_like_article(left):
            return {"article": right.strip(), "name": left.strip()}
    bits = raw.split(" ")
    if looks_like_article(bits[0]) and len(bits) > 1:
        return {"article": bits[0], "name": " ".join(bits[1:]).strip()}
    if looks_like_article(bits[-1]) and len(bits) > 1:
        return {"article": bits[-1], "name": " ".join(bits[:-1]).strip()}
    if looks_like_article(raw):
        return {"article": raw, "name": raw}
    return {"article": "", "name": raw}


def parse_kit_text(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        part = parse_part_line(line)
        if not part:
            continue
        key = (part["article"] or part["name"]).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(part)
    return out


def dump_kit_text(parts: list[dict[str, str]]) -> str:
    lines = []
    for part in parts:
        article = (part.get("article") or "").strip()
        name = (part.get("name") or "").strip()
        if article and name and name.lower() != article.lower():
            lines.append(f"{article} {name}")
        else:
            lines.append(article or name)
    return "\n".join(lines)


def as_part(value: Any) -> Optional[dict[str, str]]:
    if isinstance(value, dict):
        name = str(value.get("name") or value.get("description") or "").strip()
        article = str(value.get("article") or "").strip()
        if not name and not article:
            return None
        return {"name": name or article, "article": article}
    return parse_part_line(str(value or ""))


def _norm_parts(values: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for value in values or []:
        part = as_part(value)
        if part:
            out.append(part)
    return out


def _part_key(part: dict[str, str]) -> str:
    return ((part.get("article") or part.get("name") or "").strip().lower())


def _make_scope(make: str = "", model: str = "", engine: str = "") -> str:
    bits = ["MAKE"]
    for piece in (make, model, engine):
        piece = re.sub(r"\s+", " ", (piece or "").strip().lower())
        if piece:
            bits.append(piece)
    return "|".join(bits) if len(bits) > 1 else ""


def scope_keys(vehicle: dict[str, Any] | None = None, **hint: str) -> list[str]:
    row = dict(vehicle or {})
    row.update({k: v for k, v in hint.items() if str(v or "").strip()})
    keys: list[str] = []
    spec = (row.get("spec_key") or "").strip() or spec_key_from_vin(row.get("vin") or "")
    if spec:
        keys.append(spec)
    make, model, engine = row.get("make") or "", row.get("model") or "", row.get("engine") or ""
    for candidate in (
        _make_scope(make, model, engine),
        _make_scope(make, model),
        _make_scope(make),
    ):
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


def scope_for_load(*, vin: str = "", make: str = "", model: str = "", engine: str = "") -> str:
    if vin.strip():
        spec = spec_key_from_vin(vin) or vin.strip().upper()
        if spec:
            return spec
    scope = _make_scope(make, model, engine) or _make_scope(make, model) or _make_scope(make)
    return scope


def scope_label(scope: str, vehicle: dict[str, Any] | None = None) -> str:
    car = garage.format_vehicle(vehicle)
    if car:
        return car
    if scope.startswith("MAKE|"):
        return " ".join(p.title() if i else "" for i, p in enumerate(scope.split("|"))).strip() or scope
    return scope or "базовый список"


def parts_for(kit_key: str, vehicle: dict[str, Any] | None = None, **hint: str) -> tuple[list[dict[str, str]], str]:
    default = [dict(p) for p in DEFAULT_KITS.get(kit_key) or []]
    for key in scope_keys(vehicle, **hint):
        stored = db.get_learned_kit_parts(kit_key, key)
        if stored is not None:
            return _norm_parts(stored), key
    return default, ""


def save_parts(kit_key: str, scope: str, parts: list[Any]) -> list[dict[str, str]]:
    normalized = _norm_parts(parts)
    db.set_learned_kit_parts(kit_key, scope, normalized)
    return normalized


def expand_items(
    items: list[ParsedItem],
    *,
    spec_key: str | None = None,
    vehicle: dict[str, Any] | None = None,
) -> tuple[list[ParsedItem], list[str]]:
    """Разложить комплект (ГРМ, цепь и т.д.) на позиции комплектации."""
    hint = {"spec_key": spec_key or ""}
    label = scope_label(spec_key or "", vehicle)
    twins = db.count_vehicles_by_spec((vehicle or {}).get("spec_key") or spec_key or "") if (vehicle or spec_key) else 0
    out: list[ParsedItem] = []
    notes: list[str] = []
    for item in items:
        key = kit_key_for(item.description)
        if not key:
            out.append(item)
            continue
        kit_title = KIT_TITLES.get(key, "Комплект")
        parts, scope = parts_for(key, vehicle, **hint)
        if not parts:
            item.kit_key = key
            item.kit_scope = scope
            out.append(item)
            notes.append(f"{kit_title} для {label} пуст — загрузите артикулы или назовите детали.")
            continue
        with_art = sum(1 for p in parts if p.get("article"))
        for part in parts:
            name = part.get("name") or part.get("article") or ""
            out.append(
                ParsedItem(
                    description=name,
                    quantity=1,
                    original_required=item.original_required,
                    urgent=item.urgent,
                    kit_key=key,
                    kit_scope=scope,
                    article=part.get("article") or "",
                )
            )
        if with_art:
            notes.append(f"{kit_title} для {label}: {len(parts)} позиций, {with_art} с артикулами.")
        elif twins > 1:
            notes.append(
                f"{kit_title} как у {label} ({twins} машин). Загрузите артикулы или уберите лишнее — запомню для таких авто."
            )
        else:
            notes.append(
                f"{kit_title} для {label} пока по названиям. Вставьте артикулы в гараже — следующим клиентам подставятся сами."
            )
    return out, notes


def _stored_or_default(kit_key: str, scope: str) -> list[dict[str, str]]:
    stored = db.get_learned_kit_parts(kit_key, scope) if scope else None
    if stored is not None:
        return _norm_parts(stored)
    return [dict(p) for p in DEFAULT_KITS.get(kit_key) or []]


def excluded_parts(kit_key: str, scope: str | None) -> list[str]:
    """Детали из типового комплекта, убранные для этой комплектации."""
    if not kit_key or not scope:
        return []
    stored = db.get_learned_kit_parts(kit_key, scope)
    if stored is None:
        return []
    kept = {(p.get("name") or "").strip().lower() for p in _norm_parts(stored)}
    kept |= {(p.get("article") or "").strip().lower() for p in _norm_parts(stored)}
    kept.discard("")
    out: list[str] = []
    for part in DEFAULT_KITS.get(kit_key) or []:
        name = (part.get("name") or "").strip()
        if name and name.lower() not in kept:
            out.append(name)
    return out


def hints_for_spec(spec_key: str) -> str:
    """Контекст комплектов для LLM: сохранённый состав и исключения."""
    spec_key = (spec_key or "").strip()
    if not spec_key:
        return ""
    lines: list[str] = []
    for kit_key, title in KIT_TITLES.items():
        stored = db.get_learned_kit_parts(kit_key, spec_key)
        if stored is not None:
            names = [p.get("name") or p.get("article") or "" for p in _norm_parts(stored)]
            names = [n for n in names if n]
            if names:
                lines.append(f"- {title} для этой комплектации: {', '.join(names)}")
            excluded = excluded_parts(kit_key, spec_key)
            if excluded:
                lines.append(f"- Не включать в {title.lower()} (исключено ранее): {', '.join(excluded)}")
        else:
            default = [p.get("name") or "" for p in DEFAULT_KITS.get(kit_key) or []]
            default = [n for n in default if n]
            if default:
                lines.append(f"- {title} (типовой состав): {', '.join(default)}")
    if not lines:
        return ""
    return "Комплекты для spec_key:\n" + "\n".join(lines)


def forget_part(kit_key: str, scope: str | None, description: str, article: str = "") -> bool:
    if not kit_key or not scope:
        return False
    needle = {(description or "").strip().lower(), (article or "").strip().lower()} - {""}
    parts = _stored_or_default(kit_key, scope)
    kept = [p for p in parts if _part_key(p) not in needle and (p.get("name") or "").lower() not in needle]
    if len(kept) == len(parts):
        return False
    db.set_learned_kit_parts(kit_key, scope, kept)
    return True


def replace_part(kit_key: str, scope: str | None, old: str, new: str) -> bool:
    if not kit_key or not scope or not new:
        return False
    incoming = parse_part_line(new) or {"name": new.strip(), "article": new.strip() if looks_like_article(new) else ""}
    parts = _stored_or_default(kit_key, scope)
    replaced = False
    updated: list[dict[str, str]] = []
    old_l = (old or "").strip().lower()
    for part in parts:
        if (part.get("name") or "").lower() == old_l or (part.get("article") or "").lower() == old_l:
            updated.append(incoming)
            replaced = True
        else:
            updated.append(part)
    if not replaced:
        return False
    db.set_learned_kit_parts(kit_key, scope, updated)
    return True


def remember_article(kit_key: str, scope: str | None, description: str, article: str) -> bool:
    if not kit_key or not scope or not article:
        return False
    parts = _stored_or_default(kit_key, scope)
    changed = False
    needle = (description or "").strip().lower()
    updated: list[dict[str, str]] = []
    for part in parts:
        hit = (part.get("name") or "").lower() == needle or (part.get("article") or "").lower() == needle
        if hit and (part.get("article") or "") != article:
            updated.append({"name": part.get("name") or description, "article": article})
            changed = True
        else:
            updated.append(part)
    if changed:
        db.set_learned_kit_parts(kit_key, scope, updated)
    return changed
