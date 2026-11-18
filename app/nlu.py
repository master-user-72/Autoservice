from __future__ import annotations

import json
import re
from typing import Any

from app.config import LLM_NONSTANDARD_ONLY
from app import garage
from app.garage import MAKE_ALIASES, extract_make, extract_plate, extract_plate_digits, normalize_plate
from app.log import get_logger
from app.kits import GRM_KIT_NAME, hints_for_spec, is_grm_kit_phrase
from app.llm import chat_json, llm_enabled
from app.learn import items_from_learned, normalize_phrase, phrase_key_from_raw
from app.models import ParsedItem, ParsedRequest
from app import db

log = get_logger("nlu")


def _is_vin(token: str) -> bool:
    token = token.upper()
    return len(token) == 17 and token.isalnum() and not any(ch in token for ch in "IOQ")


def _clean_vin(value: str | None) -> str | None:
    if not value:
        return None
    stripped = re.sub(r"\bvin\b|\bвин\b", " ", value, flags=re.IGNORECASE)
    compact = "".join(ch.upper() for ch in stripped if ch.isascii() and ch.isalnum())
    for i in range(0, max(0, len(compact) - 16)):
        candidate = compact[i : i + 17]
        if _is_vin(candidate):
            return candidate
    return None

SYSTEM_PROMPT = """Ты парсер заявок на автозапчасти для одного руководителя.
Из устной или текстовой заявки извлеки JSON без markdown:
{
  "vin": "17 символов или null",
  "make": "марка или null",
  "plate": "госномер РФ без пробелов (А123АА72) или только цифры без букв (123, 12372), иначе null",
  "items": [
    {"description": "краткое название детали", "quantity": 1, "original_required": false, "urgent": false}
  ],
  "clarifying_question": "вопрос на русском или null"
}
Правила:
- VIN всегда 17 знаков, без I, O, Q. Если назван по буквам/с пробелами — собери.
- Если вместо VIN назвали госномер или марку из гаража — vin=null, заполните plate и/или make.
- Госномер можно назвать целиком или только цифрами, без букв (например «сто двадцать три» / «12372»). Тогда plate — только цифры.
- original_required=true только если явно сказали оригинал/OEM/оригинальная.
- urgent=true если сказали срочно/сегодня/немедленно для этой детали или всей заявки.
- Если VIN/номер/марка неясны или деталь двусмысленна (лево/право) — задай один clarifying_question.
- Не выдумывай артикулы. description — как для поиска в каталоге поставщика.
- quantity — целое число штук в заказе. Свечи зажигания для ДВС: обычно по числу цилиндров (4, 6, 8). Если в заявке «4 свечи» — quantity=4. По умолчанию 1.
- Каждая запчасть — отдельный элемент items. «фильтр масляный фильтр салонный» = два items, не одна строка.
- «все для замены ГРМ», «комплект ГРМ», «замена ГРМ» (ремень) — один item с description «комплект ГРМ». Не перечисляй ремень/ролики сам.
- «комплект для замены цепи», «цепь распредвала», «комплект цепи ГРМ» — перечисли отдельными items: цепь ГРМ, натяжитель цепи ГРМ, успокоитель цепи ГРМ, направляющая цепи ГРМ, прокладка клапанной крышки, болты клапанной крышки.
- «комплект ТО», «ТО-5» и т.п. — перечисли: масло моторное, фильтр масляный, фильтр воздушный, фильтр салонный, свечи зажигания (если в заявке не названо иное).
- Слово «комплект» не означает одну строку, кроме комплекта ГРМ на ремень.
- Если в контексте даны VIN, spec_key, модель — используй их, не переспрашивай марку/модель без необходимости.
- Если дан сохранённый состав комплекта для spec_key — используй именно его.
- Детали из блока «исключено ранее» не включай в items.
- Язык полей description и clarifying_question — русский.
"""


_QTY_RE = re.compile(r"(\d+)\s*(?:шт\.?|штук|pcs|pc)\b", re.IGNORECASE)
_CYL_RE = re.compile(r"(\d+)\s*(?:цил|цилиндр)", re.IGNORECASE)


def _cylinders_from_engine(engine: str | None) -> int | None:
    blob = (engine or "").lower().replace("ё", "е")
    if not blob:
        return None
    if re.search(r"\bv6\b|6v|6 цил", blob):
        return 6
    if re.search(r"\bv8\b|8v|8 цил", blob):
        return 8
    if re.search(r"\bv5\b|5 цил", blob):
        return 5
    if re.search(r"\bv4\b|4v|4 цил|i4", blob):
        return 4
    if re.search(r"\bv3\b|3 цил", blob):
        return 3
    match = _CYL_RE.search(blob)
    if match:
        return max(1, min(12, int(match.group(1))))
    return None


def _quantity_from_text(description: str, engine: str | None = None) -> int:
    desc = description or ""
    match = _QTY_RE.search(desc)
    if match:
        return max(1, min(99, int(match.group(1))))
    if re.search(r"свеч", desc, re.IGNORECASE):
        cyl = _cylinders_from_engine(engine)
        if cyl:
            return cyl
        return 4
    if re.search(r"колодк", desc, re.IGNORECASE) and re.search(r"перед", desc, re.IGNORECASE):
        return 1
    return 1


def _normalize_quantity(value: Any, description: str, engine: str | None = None) -> int:
    try:
        qty = int(value)
    except (TypeError, ValueError):
        qty = 0
    if qty < 1:
        qty = _quantity_from_text(description, engine)
    return max(1, min(99, qty))


def dedupe_items(items: list[ParsedItem]) -> list[ParsedItem]:
    merged: dict[str, ParsedItem] = {}
    for item in items:
        key = normalize_phrase(item.description)
        if not key:
            continue
        if key in merged:
            merged[key].quantity = min(99, merged[key].quantity + max(1, item.quantity))
            merged[key].original_required = merged[key].original_required or item.original_required
            merged[key].urgent = merged[key].urgent or item.urgent
        else:
            merged[key] = item
    return list(merged.values())


def apply_quantity_hints(parsed: ParsedRequest, engine: str | None = None) -> ParsedRequest:
    for item in parsed.items:
        item.quantity = _normalize_quantity(item.quantity, item.description, engine)
    parsed.items = dedupe_items(parsed.items)
    return parsed


PART_HEAD_RE = re.compile(
    r"(?=\b(?:фильтр(?:ы)?|колодк\w*|диск(?:и)?|масл(?:о|а)|ремн(?:ь|и)|свеч\w*|"
    r"ламп\w*|щетк\w*|датчик\w*|прокладк\w*|сальник\w*|подшипник\w*|амортизатор\w*|"
    r"сайлент\w*|рычаг\w*|шаров\w*|наконечник\w*|помп\w*|радиатор\w*|термостат\w*|"
    r"сцеплен\w*|антифриз\w*|жидкост\w*|редуктор\w*|раздатк\w*|акпп|мкпп)\b)",
    re.IGNORECASE,
)


def _normalize_part_description(text: str) -> str:
    """«все для замены грм» — это комплект, не две позиции."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip(" .,-"))
    if is_grm_kit_phrase(cleaned):
        return GRM_KIT_NAME
    return cleaned


def _strip_vehicle_words(text: str, make: str | None = None) -> str:
    body = text or ""
    if make:
        body = re.sub(rf"\b{re.escape(make)}\b", " ", body, flags=re.IGNORECASE)
        for alias, canon in MAKE_ALIASES.items():
            if canon.lower() == make.lower():
                body = re.sub(rf"\b{re.escape(alias)}\b", " ", body, flags=re.IGNORECASE)
    body = re.sub(r"\bвин\b|\bvin\b", " ", body, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", body).strip(" ,.-")


def split_part_descriptions(text: str) -> list[str]:
    """Несколько деталей в одной фразе без запятых: «фильтр масляный фильтр салонный»."""
    if not text:
        return []
    rough = re.split(r"[,;]|\s+и\s+|\s+плюс\s+|\n", text, flags=re.IGNORECASE)
    out: list[str] = []
    for piece in rough:
        piece = re.sub(r"\s+", " ", piece).strip(" .")
        if not piece:
            continue
        bits = [b.strip(" .") for b in PART_HEAD_RE.split(piece) if b and b.strip(" .")]
        if len(bits) >= 2:
            out.extend(bits)
        else:
            out.append(piece)
    return out


def fallback_parse(text: str) -> ParsedRequest:
    vin = _clean_vin(text)
    plate_source = text
    if vin:
        plate_source = re.sub(re.escape(vin), " ", plate_source, flags=re.IGNORECASE)
    plate = extract_plate(plate_source)
    make = extract_make(text)
    urgent_all = bool(re.match(r"^\s*срочн", text, re.IGNORECASE))
    body = text
    if vin:
        body = re.sub(re.escape(vin), " ", body, flags=re.IGNORECASE)
    if plate:
        body = re.sub(re.escape(plate), " ", body, flags=re.IGNORECASE)
        body = re.sub(r"\bгосномер\b|\bгос\.?\s*номер\b|\bномер\s+машин", " ", body, flags=re.IGNORECASE)
        digits = "".join(ch for ch in plate if ch.isdigit())
        if len(digits) >= 3:
            body = re.sub(re.escape(digits), " ", body)
    else:
        digits = extract_plate_digits(plate_source)
        if digits:
            body = re.sub(re.escape(digits), " ", body)
    body = _strip_vehicle_words(body, make)
    chunks = split_part_descriptions(body)
    items: list[ParsedItem] = []
    for chunk in chunks:
        chunk = re.sub(r"^(нужн[аоыи]\s+|закаж[а-я]+\s+|ещ[её]\s+|на\s+)", "", chunk, flags=re.IGNORECASE)
        chunk = re.sub(r"\s+", " ", chunk).strip(" .")
        if len(chunk) < 3:
            continue
        if chunk.lower() in {"вин", "vin", "номер", "марку", "марка"}:
            continue
        if re.fullmatch(r"\d{3,6}", chunk):
            continue
        if make and make.lower() in chunk.lower() and len(chunk) < len(make) + 8:
            continue
        original = bool(re.search(r"оригинал|oem|оем", chunk, re.IGNORECASE))
        urgent = urgent_all or bool(re.search(r"срочн", chunk, re.IGNORECASE))
        description = re.sub(r"\b(оригинал(ьн(ый|ая|ое))?|oem|оем|срочно)\b", "", chunk, flags=re.IGNORECASE)
        description = _normalize_part_description(_strip_vehicle_words(description, make))
        if description:
            items.append(
                ParsedItem(
                    description=description,
                    quantity=_quantity_from_text(description),
                    original_required=original,
                    urgent=urgent,
                )
            )
    question = None
    if not vin and not plate and not make:
        question = "Назовите VIN, госномер или марку из гаража."
    elif not items:
        question = "Какие запчасти нужны?"
    return ParsedRequest(vin=vin, make=make, plate=plate, items=items, clarifying_question=question, raw_text=text)


def _extract_json(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE | re.DOTALL)
    return json.loads(content)


def explode_parsed_items(parsed: ParsedRequest) -> ParsedRequest:
    expanded: list[ParsedItem] = []
    for item in parsed.items:
        cleaned = _strip_vehicle_words(item.description, parsed.make)
        parts = split_part_descriptions(cleaned)
        sources = parts or ([cleaned] if cleaned else [])
        for part in sources:
            part = _normalize_part_description(_strip_vehicle_words(part, parsed.make))
            if len(part) < 3:
                continue
            expanded.append(
                ParsedItem(
                    description=part,
                    quantity=item.quantity,
                    original_required=item.original_required,
                    urgent=item.urgent,
                )
            )
    if expanded:
        parsed.items = expanded
    return parsed


NONSTANDARD_RE = re.compile(
    r"подобрать|вс[её]\s+для|набор\b|комплект(?!\s+грм)|цеп(?:ь|и)\b|"
    r"что\s+нужно|сделай|разбери|все\s+масла|полная\s+замена",
    re.IGNORECASE,
)


def _item_looks_standard(description: str) -> bool:
    desc = (description or "").strip()
    if not desc:
        return False
    if is_grm_kit_phrase(desc):
        return True
    if db.get_learned_phrase(normalize_phrase(desc)):
        return True
    if len(desc) > 70:
        return False
    if NONSTANDARD_RE.search(desc) and not is_grm_kit_phrase(desc):
        return False
    return bool(PART_HEAD_RE.search(desc))


def is_nonstandard(parsed: ParsedRequest, text: str) -> bool:
    if parsed.clarifying_question:
        return True
    if not parsed.items:
        return True
    if any(not _item_looks_standard(item.description) for item in parsed.items):
        return True
    phrase = phrase_key_from_raw(text, parsed.vin)
    joined = normalize_phrase(" ".join(item.description for item in parsed.items))
    if phrase and joined and len(phrase) > len(joined) + 20:
        return True
    return False


def _parsed_from_llm_data(data: dict[str, Any], text: str) -> ParsedRequest:
    vin = _clean_vin(str(data.get("vin") or "")) or _clean_vin(text)
    make = extract_make(str(data.get("make") or "") + " " + text)
    raw_plate = str(data.get("plate") or "").strip()
    plate = normalize_plate(raw_plate)
    if not plate:
        digits = "".join(ch for ch in raw_plate if ch.isdigit())
        plate = digits if len(digits) >= 3 else extract_plate(text)
    if not plate:
        plate = extract_plate_digits(text)
    items = []
    for row in data.get("items") or []:
        desc = str(row.get("description") or "").strip()
        if not desc:
            continue
        items.append(
            ParsedItem(
                description=desc,
                quantity=_normalize_quantity(row.get("quantity"), desc),
                original_required=bool(row.get("original_required")),
                urgent=bool(row.get("urgent")),
            )
        )
    question = data.get("clarifying_question") or None
    if isinstance(question, str):
        question = question.strip() or None
    if not vin and not plate and not make and not question:
        question = "Назовите VIN, госномер или марку из гаража."
    if (vin or plate or make) and not items and not question:
        question = "Какие запчасти нужны?"
    return ParsedRequest(
        vin=vin,
        make=make,
        plate=plate,
        items=items,
        clarifying_question=question,
        raw_text=text,
        nlu_source="llm",
    )


def _garage_hints(parsed: ParsedRequest) -> tuple[str | None, dict[str, Any] | None]:
    vin, row, _ = garage.resolve_vin(parsed.vin, parsed.plate, parsed.make)
    return vin, row


def _llm_user_message(text: str, parsed: ParsedRequest, vin: str | None, row: dict[str, Any] | None) -> str:
    lines: list[str] = []
    if vin or row:
        spec = garage.spec_key_of(row, vin)
        label = garage.format_vehicle(row)
        lines.append("Контекст машины из гаража:")
        if vin:
            lines.append(f"- VIN: {vin}")
        if spec:
            lines.append(f"- spec_key (код комплектации узлов): {spec}")
            kit_hints = hints_for_spec(spec)
            if kit_hints:
                lines.append(kit_hints)
        if label:
            lines.append(f"- {label}")
        elif parsed.make:
            lines.append(f"- марка: {parsed.make}")
        plate = (row or {}).get("plate") or parsed.plate
        if plate:
            lines.append(f"- госномер/цифры: {plate}")
    elif parsed.vin:
        lines.append(f"Контекст: VIN из заявки {parsed.vin}")
    if not lines:
        return text
    return "\n".join(lines) + f"\n\nЗаявка: {text}"


def _merge_garage_into_parsed(parsed: ParsedRequest, vin: str | None, row: dict[str, Any] | None) -> ParsedRequest:
    if vin:
        parsed.vin = vin
    if row:
        if not parsed.make and row.get("make"):
            parsed.make = row["make"]
        if not parsed.plate and row.get("plate"):
            parsed.plate = row["plate"]
    if (parsed.vin or parsed.plate or parsed.make) and parsed.items:
        if parsed.clarifying_question and re.search(
            r"марк|модел|vin|вин|госномер|уточн",
            parsed.clarifying_question,
            re.IGNORECASE,
        ):
            parsed.clarifying_question = None
    return parsed


def parse_via_llm(text: str, *, parsed_hint: ParsedRequest | None = None) -> ParsedRequest:
    hint = parsed_hint or fallback_parse(text)
    vin, row = _garage_hints(hint)
    user = _llm_user_message(text, hint, vin, row)
    if vin or row:
        log.info("LLM контекст: vin=%s spec=%s", vin, garage.spec_key_of(row, vin))
    payload = chat_json(SYSTEM_PROMPT, user)
    content = payload["choices"][0]["message"]["content"]
    data = _extract_json(content)
    parsed = _parsed_from_llm_data(data, text)
    parsed = _merge_garage_into_parsed(parsed, vin, row)
    engine = (row or {}).get("engine") or (row or {}).get("displacement")
    return apply_quantity_hints(parsed, engine)


def parse_request(text: str) -> ParsedRequest:
    text = (text or "").strip()
    if not text:
        return ParsedRequest(clarifying_question="Пустая заявка. Назовите VIN и список деталей.", raw_text=text)

    parsed = explode_parsed_items(fallback_parse(text))
    parsed.raw_text = text
    phrase = phrase_key_from_raw(text, parsed.vin)
    learned = db.get_learned_phrase(phrase) if phrase else None
    if learned:
        items = items_from_learned(learned)
        if items:
            parsed.items = items
            parsed.clarifying_question = None if (parsed.vin or parsed.plate or parsed.make) else parsed.clarifying_question
            parsed.nlu_source = "learned"
            log.info("разбор из базы: phrase=%r items=%d", phrase, len(items))
            return apply_quantity_hints(explode_parsed_items(parsed))

    local_items = [item.description for item in parsed.items]
    nonstandard = is_nonstandard(parsed, text)
    log.info(
        "локальный разбор: make=%s plate=%s items=%s nonstandard=%s llm=%s",
        parsed.make,
        parsed.plate,
        local_items,
        nonstandard,
        llm_enabled(),
    )

    if llm_enabled() and (not LLM_NONSTANDARD_ONLY or nonstandard):
        try:
            llm_parsed = explode_parsed_items(parse_via_llm(text, parsed_hint=parsed))
            log.info(
                "LLM разбор OK: items=%s",
                [item.description for item in llm_parsed.items],
            )
            return llm_parsed
        except Exception as exc:
            log.warning("LLM разбор не удался, локальный fallback: %s: %s", type(exc).__name__, exc)

    parsed.nlu_source = "local"
    log.info("итог локальный: items=%s", local_items)
    return apply_quantity_hints(explode_parsed_items(parsed))

