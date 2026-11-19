from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app import db, garage
from app.config import CITY, LLM_NONSTANDARD_ONLY, SUPPLIER_NAME
from app.kits import (
    KIT_TITLES,
    expand_items as expand_kit_items,
    forget_part as forget_kit_part,
    remember_article as remember_kit_article,
    replace_part as replace_kit_part,
)
from app.learn import remember_confirmed_request
from app.llm import llm_enabled, provider_name
from app.models import ParsedRequest
from app.nlu import apply_quantity_hints, parse_request
from app.suppliers import get_adapter
from app.suppliers.base import Offer, pick_best_offer, offer_compare_note


def _order_lines_summary(rows: list[dict[str, Any]]) -> str:
    bits: list[str] = []
    for row in rows:
        qty = max(1, min(99, int(row.get("quantity") or 1)))
        label = row.get("article") or row.get("description") or "?"
        bits.append(f"{label}×{qty}" if qty > 1 else label)
    return ", ".join(bits)


def _catalog_article(article: str | None, description: str = "") -> str:
    """В колонку артикула только каталожный номер, не название из заявки."""
    raw = (article or "").strip()
    if not raw or raw.upper() in {"QUERY", "ERR"}:
        return ""
    desc = (description or "").strip()
    if desc and raw.lower() in {desc.lower(), desc.lower()[:40]} and not re.search(r"\d", raw):
        return ""
    if re.search(r"[а-яё]", raw, re.I) and not re.search(r"\d", raw):
        return ""
    return raw


def _bool_int(value: bool) -> int:
    return 1 if value else 0


def _request_status(
    *,
    ok: bool,
    title: str,
    steps: list[dict[str, str]],
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "title": title,
        "steps": steps,
        "errors": [e for e in (errors or []) if e],
        "warnings": [w for w in (warnings or []) if w],
    }


def ingest_text(text: str) -> dict[str, Any]:
    steps: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    def mark(label: str, state: str = "done") -> None:
        steps.append({"label": label, "state": state})

    try:
        parsed: ParsedRequest = parse_request(text)
        source = parsed.nlu_source or "local"
        if source == "llm":
            mark("Разбор заявки (нестандарт, LLM)")
        elif source == "learned":
            mark("Разбор заявки (из базы формулировок)")
        else:
            mark("Разбор заявки")

        vin, garage_row, garage_question = garage.resolve_vin(parsed.vin, parsed.plate, parsed.make)
        if vin:
            parsed.vin = vin
            saved = garage.remember(vin, parsed.make, parsed.plate)
            garage_row = saved or garage_row
            apply_quantity_hints(
                parsed,
                (garage_row or {}).get("engine") or (garage_row or {}).get("displacement"),
            )
            plate_hint = ""
            if garage_row and garage_row.get("plate"):
                plate_hint = garage.format_plate(garage_row["plate"])
            spec_label = garage.format_vehicle(garage_row)
            mark("Машина в гараже" + (f": {plate_hint}" if plate_hint else f": VIN {vin}") + (f" · {spec_label}" if spec_label else ""))
            if parsed.items:
                parsed.clarifying_question = None
            parsed.items, kit_notes = expand_kit_items(
                parsed.items,
                spec_key=garage.spec_key_of(garage_row, vin),
                vehicle=garage_row,
            )
            warnings.extend(kit_notes)
        else:
            parsed.clarifying_question = garage_question or parsed.clarifying_question or (
                "Назовите VIN, госномер (можно только цифры) или марку из гаража."
            )
            mark("Поиск машины в гараже", "error")
            errors.append(parsed.clarifying_question)

        adapter = get_adapter()

        if parsed.clarifying_question and (not parsed.vin or not parsed.items):
            request_id = db.insert_request(
                parsed.raw_text or text,
                parsed.vin,
                parsed.clarifying_question,
                "needs_clarification",
            )
            db.add_event(parsed.clarifying_question, "warn")
            title = "Нужно уточнение"
            return {
                "ok": False,
                "needs_clarification": True,
                "question": parsed.clarifying_question,
                "request_id": request_id,
                "parsed": parsed.model_dump(),
                "status": _request_status(ok=False, title=title, steps=steps, errors=errors or [parsed.clarifying_question], warnings=[]),
            }

        try:
            vehicle = adapter.search_by_vin(parsed.vin or "")
            mark("VIN у поставщиков")
        except Exception as exc:  # noqa: BLE001
            mark("VIN у поставщиков", "error")
            errors.append(f"Ошибка поиска у поставщиков: {exc}")
            db.add_event(errors[-1], "error")
            return {
                "ok": False,
                "needs_clarification": False,
                "question": errors[-1],
                "parsed": parsed.model_dump(),
                "status": _request_status(ok=False, title="Ошибка поставщиков", steps=steps, errors=errors, warnings=warnings),
            }

        saved = garage.remember(parsed.vin or "", parsed.make, parsed.plate)
        garage_row = saved or garage_row
        if garage_row:
            plate_label = garage.format_plate(garage_row["plate"]) if garage_row.get("plate") else ""
            spec_label = garage.format_vehicle(garage_row)
            label = " ".join(part for part in [spec_label or garage_row.get("make"), plate_label] if part)
            if label:
                vehicle.title = label
                vehicle.notes = f"VIN {parsed.vin}. {vehicle.notes}"
        request_id = db.insert_request(parsed.raw_text or text, parsed.vin, None, "matched")
        training = db.get_settings()["training_mode"]
        lot = db.get_or_create_today_lot()
        if lot["status"] in {"skipped_empty", "failed"}:
            db.update_lot(lot["id"], status="collecting", error=None)
            lot = db.get_lot(lot["id"]) or lot
        if lot["status"] in {"sent", "sending"}:
            warnings.append("Сегодняшний лот уже закрыт. Новые обычные позиции не добавлены — оформите как срочные или завтра.")
            db.add_event(warnings[-1], "warn")

        created: list[dict[str, Any]] = []
        regular_offers: list[tuple[Any, Offer]] = []
        unmatched: list[str] = []
        lot_open = lot["status"] in {"collecting", "pending_approval"}
        if lot["status"] == "pending_approval":
            db.update_lot(lot["id"], status="collecting", error=None)
            lot = db.get_lot(lot["id"]) or lot

        for item in parsed.items:
            try:
                matches = adapter.match_items(
                    (getattr(item, "article", None) or item.description or "").strip(),
                    item.original_required,
                )
            except Exception as exc:  # noqa: BLE001
                unmatched.append(item.description)
                warnings.append(f"Ошибка подбора «{item.description}»: {exc}")
                created.append(db.get_item(_store_unknown(
                    request_id=request_id,
                    lot_id=lot["id"] if lot_open and not item.urgent else None,
                    item=item,
                    reason=str(exc),
                )))
                continue
            offer = pick_best_offer(matches)
            if offer is None:
                unmatched.append(item.description)
                warnings.append(f"{item.description}: поставщик не определён — нет в наличии")
                created.append(db.get_item(_store_unknown(
                    request_id=request_id,
                    lot_id=lot["id"] if lot_open and not item.urgent else None,
                    item=item,
                )))
                continue
            offer.warning = offer_compare_note(offer, matches)
            if item.urgent:
                item_id = _store_item(
                    request_id=request_id,
                    lot_id=None,
                    item=item,
                    offer=offer,
                    urgent=True,
                    status="pending_review" if training else "confirmed",
                )
                created.append(db.get_item(item_id))
                if not training:
                    try:
                        sent = send_items([item_id], urgent=True)
                        if not sent.get("ok"):
                            errors.append(sent.get("error") or "Не удалось отправить срочную позицию")
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"Не удалось отправить срочную позицию: {exc}")
            else:
                regular_offers.append((item, offer))

        if regular_offers:
            for item, offer in regular_offers:
                warning = offer.warning
                if offer.warning and "выбрано по цене" not in (offer.warning or ""):
                    warnings.append(f"{offer.name or item.description}: {offer.warning}")
                item_id = _store_item(
                    request_id=request_id,
                    lot_id=lot["id"] if lot_open else None,
                    item=item,
                    offer=offer,
                    urgent=False,
                    status="pending_review" if training else "confirmed",
                    extra_warning=warning,
                )
                created.append(db.get_item(item_id))

            if lot_open and lot["status"] != "collecting":
                db.update_lot(lot["id"], status="collecting")

        if created:
            mark(f"В лот добавлено позиций: {len(created)}")
        else:
            mark("Подбор позиций", "error")
            if not errors:
                errors.append("Ни одна позиция не подобрана.")

        ok = bool(created) and not errors
        title = "Заявка принята" if ok and not unmatched else ("Заявка с пометками" if created else "Заявка не выполнена")
        if created and not training:
            remember_confirmed_request(request_id)
        db.add_event(
            f"Заявка VIN {parsed.vin}: {vehicle.title}. Позиций: {len(created)}.",
            "info" if ok else "warn",
        )
        return {
            "ok": ok,
            "needs_clarification": False,
            "vehicle": {"vin": vehicle.vin, "title": vehicle.title, "notes": vehicle.notes},
            "request_id": request_id,
            "items": created,
            "parsed": parsed.model_dump(),
            "training_mode": training,
            "status": _request_status(ok=ok, title=title, steps=steps, errors=errors, warnings=warnings),
        }
    except Exception as exc:  # noqa: BLE001
        mark("Обработка заявки", "error")
        errors.append(str(exc) or "Неизвестная ошибка при обработке заявки")
        db.add_event(errors[-1], "error")
        return {
            "ok": False,
            "needs_clarification": False,
            "question": errors[-1],
            "status": _request_status(ok=False, title="Ошибка заявки", steps=steps, errors=errors, warnings=warnings),
        }


def _kit_key(item: Any) -> str:
    return (getattr(item, "kit_key", None) or "") if item is not None else ""


def _kit_scope(item: Any) -> str:
    return (getattr(item, "kit_scope", None) or "") if item is not None else ""


def _merge_warning(item: Any, extra: str | None = None) -> str | None:
    notes: list[str] = []
    kit_key = _kit_key(item)
    if kit_key:
        title = KIT_TITLES.get(kit_key, "Комплект")
        notes.append(f"{title} этой комплектации. Лишнее уберите — запомню для всех таких авто")
    if extra:
        notes.append(extra)
    return " · ".join(notes) or None


def _request_vin(item: dict[str, Any]) -> str | None:
    rid = item.get("request_id")
    if not rid:
        return None
    req = db.get_request(int(rid))
    vin = (req or {}).get("vin") or item.get("request_vin")
    return str(vin).strip().upper() if vin else None


def _request_spec(item: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    vin = _request_vin(item)
    row = db.get_vehicle_by_vin(vin) if vin else None
    return garage.spec_key_of(row, vin), row


def _store_unknown(
    *,
    request_id: int,
    lot_id: int | None,
    item: Any,
    reason: str | None = None,
) -> int:
    warning = reason or "Нет в наличии ни у одного поставщика"
    return db.insert_item(
        {
            "request_id": request_id,
            "lot_id": lot_id,
            "description": item.description,
            "article": "",
            "name": item.description,
            "supplier": "",
            "delivery_days": None,
            "price": None,
            "currency": "RUB",
            "original_required": _bool_int(item.original_required),
            "is_original": 0,
            "urgent": _bool_int(item.urgent),
            "status": "supplier_unknown",
            "warning": _merge_warning(item, warning),
            "kit_key": _kit_key(item),
            "kit_scope": _kit_scope(item),
            "quantity": max(1, min(99, int(getattr(item, "quantity", 1) or 1))),
        }
    )


def _store_item(
    *,
    request_id: int,
    lot_id: int | None,
    item: Any,
    offer: Offer,
    urgent: bool,
    status: str,
    extra_warning: str | None = None,
) -> int:
    return db.insert_item(
        {
            "request_id": request_id,
            "lot_id": lot_id,
            "description": item.description,
            "article": _catalog_article(offer.article, item.description)
            or _catalog_article(getattr(item, "article", None) or "", ""),
            "name": offer.name,
            "supplier": offer.supplier or SUPPLIER_NAME,
            "delivery_days": offer.delivery_days,
            "price": offer.price,
            "currency": offer.currency,
            "original_required": _bool_int(item.original_required),
            "is_original": _bool_int(offer.is_original),
            "urgent": _bool_int(urgent),
            "status": status,
            "warning": _merge_warning(item, extra_warning or offer.warning),
            "kit_key": _kit_key(item),
            "kit_scope": _kit_scope(item),
            "quantity": max(1, min(99, int(getattr(item, "quantity", 1) or 1))),
        }
    )


def confirm_item(item_id: int) -> dict[str, Any]:
    item = db.get_item(item_id)
    if not item:
        raise KeyError("позиция не найдена")
    db.update_item(item_id, status="confirmed")
    kit_key = (item.get("kit_key") or "").strip()
    spec_key, _car = _request_spec(item)
    scope = (item.get("kit_scope") or spec_key or "").strip()
    article = (item.get("article") or "").strip()
    if kit_key and scope and article:
        remember_kit_article(kit_key, scope, item.get("description") or "", article)
    db.add_event(f"Подтверждена позиция {item.get('article') or item['description']}.")
    remember_confirmed_request(item.get("request_id"))
    return db.get_item(item_id) or item


def set_item_quantity(item_id: int, quantity: int) -> dict[str, Any]:
    item = db.get_item(item_id)
    if not item:
        raise KeyError("позиция не найдена")
    qty = max(1, min(99, int(quantity)))
    db.update_item(item_id, quantity=qty)
    db.add_event(f"Количество {item.get('description')}: {qty} шт.")
    return db.get_item(item_id) or item


def reject_item(item_id: int) -> dict[str, Any]:
    item = db.get_item(item_id)
    if not item:
        raise KeyError("позиция не найдена")
    db.update_item(item_id, status="rejected")
    kit_key = (item.get("kit_key") or "").strip()
    spec_key, car = _request_spec(item)
    scope = (item.get("kit_scope") or spec_key or "").strip()
    label = garage.format_vehicle(car) or scope
    if kit_key and scope and forget_kit_part(kit_key, scope, item.get("description") or "", item.get("article") or ""):
        kit_title = KIT_TITLES.get(kit_key, "комплекта")
        db.add_event(
            f"Исключена из {kit_title} для {label}: {item.get('description')}.",
            "warn",
        )
    else:
        db.add_event(f"Исключена позиция {item.get('article') or item['description']}.", "warn")
    return db.get_item(item_id) or item


def replace_item(item_id: int, description: str) -> dict[str, Any]:
    item = db.get_item(item_id)
    if not item:
        raise KeyError("позиция не найдена")
    adapter = get_adapter()
    old_description = item.get("description") or ""
    matches = adapter.match_items(description, bool(item["original_required"]))
    offer = pick_best_offer(matches)
    if not offer:
        db.update_item(
            item_id,
            description=description,
            article="",
            name=description,
            supplier="",
            delivery_days=None,
            price=None,
            warning="Нет в наличии ни у одного поставщика",
            status="supplier_unknown",
        )
        kit_key = (item.get("kit_key") or "").strip()
        spec_key, _car = _request_spec(item)
        scope = (item.get("kit_scope") or spec_key or "").strip()
        if kit_key and scope:
            replace_kit_part(kit_key, scope, old_description, description)
        db.add_event(f"Замена: {description} — поставщик не определён.", "warn")
        return db.get_item(item_id) or item
    note = offer_compare_note(offer, matches)
    kit_key = (item.get("kit_key") or "").strip()
    spec_key, car = _request_spec(item)
    scope = (item.get("kit_scope") or spec_key or "").strip()
    if kit_key and scope:
        replace_kit_part(kit_key, scope, old_description, description)
    db.update_item(
        item_id,
        description=description,
        article=_catalog_article(offer.article, description),
        name=offer.name,
        supplier=offer.supplier or SUPPLIER_NAME,
        delivery_days=offer.delivery_days,
        price=offer.price,
        is_original=_bool_int(offer.is_original),
        warning=note,
        status="pending_review" if db.get_settings()["training_mode"] else "confirmed",
    )
    if kit_key and scope:
        label = garage.format_vehicle(car) or scope
        kit_title = KIT_TITLES.get(kit_key, "комплекте")
        db.add_event(f"В {kit_title} {label}: {old_description} → {description}.")
    else:
        db.add_event(f"Замена: {description} → {offer.article}.")
    return db.get_item(item_id) or item


def send_items(item_ids: list[int], urgent: bool = False) -> dict[str, Any]:
    from app.suppliers.mock import MockSupplier
    from app.workspace_db import transaction

    adapter = get_adapter()
    if not isinstance(adapter, MockSupplier):
        return {"ok": False, "error": "Подтверждённого канала оформления нет. Проверьте условия у поставщика."}
    with transaction() as conn:
        rows = []
        for item_id in dict.fromkeys(item_ids):
            row = conn.execute(
                """SELECT * FROM line_items WHERE id=? AND status IN ('confirmed','pending_review')
                   AND urgent=? AND supplier IS NOT NULL AND supplier!=''""", (item_id, urgent),
            ).fetchone()
            if row:
                rows.append(dict(row))
                conn.execute("UPDATE line_items SET status='sending' WHERE id=?", (item_id,))
    if not rows:
        return {"ok": False, "error": "Нет доступных позиций. Проверьте историю отправки."}

    offers = [Offer(
        article=row["article"] or "", name=row["name"] or row["description"],
        delivery_days=int(row["delivery_days"] or 0), price=float(row["price"] or 0),
        currency=row["currency"] or "RUB", is_original=bool(row["is_original"]),
        supplier=row["supplier"], quantity=row["quantity"],
    ) for row in rows]
    try:
        result = adapter.place_order(offers)
    except Exception:
        with transaction() as conn:
            conn.executemany("UPDATE line_items SET status='outcome_unknown' WHERE id=?", [(r["id"],) for r in rows])
        db.add_event("Ответ учебного поставщика неизвестен. Повтор заблокирован.", "warn")
        return {"ok": False, "error": "Неизвестный результат. Проверьте исход оформления."}

    with transaction() as conn:
        conn.executemany("UPDATE line_items SET status=?, order_ref=? WHERE id=?",
                         [("sent" if result.ok else "failed", result.order_ref, row["id"]) for row in rows])
    if result.ok:
        db.add_event(f"Учебный заказ {result.order_ref}: {_order_lines_summary(rows)}")
        return {"ok": True, "order_ref": result.order_ref, "count": len(rows)}
    return {"ok": False, "error": result.error}


def send_urgent_item(item_id: int) -> dict[str, Any]:
    item = db.get_item(item_id)
    if not item:
        raise KeyError("позиция не найдена")
    if not item["urgent"]:
        raise ValueError("позиция не срочная")
    if item["status"] not in {"confirmed", "pending_review"}:
        raise ValueError("позиция недоступна для отправки")
    settings = db.get_settings()
    if settings["training_mode"] and item["status"] != "confirmed":
        db.update_item(item_id, status="confirmed")
    return send_items([item_id], urgent=True)


def confirm_all_in_lot(lot_id: int) -> dict[str, Any]:
    items = db.list_items_for_lot(lot_id)
    count = 0
    for item in items:
        if item["status"] == "pending_review":
            confirm_item(item["id"])
            count += 1
    db.add_event("Все позиции лота подтверждены.")
    return {"ok": True, "count": count}


def process_due_lot(force: bool = False) -> dict[str, Any]:
    lot = db.get_or_create_today_lot()
    settings = db.get_settings()
    items = [
        i
        for i in db.list_items_for_lot(lot["id"])
        if i["status"] in {"confirmed", "pending_review"}
    ]

    if not items:
        return {"ok": True, "status": lot["status"], "skipped": True}

    sendable = [i for i in items if i["status"] == "confirmed"]
    if force:
        sendable = [i for i in items if i["status"] in {"confirmed", "pending_review"}]
        for item in sendable:
            if item["status"] == "pending_review":
                db.update_item(item["id"], status="confirmed")

    if not force:
        db.update_lot(lot["id"], status="pending_approval")
        db.add_event("Лот готов. Нужно подтверждение руководителя перед отправкой.", "warn")
        return {"ok": True, "status": "pending_approval", "count": len(items)}

    if not sendable:
        db.update_lot(lot["id"], status="pending_approval")
        db.add_event("Нет подтверждённых позиций — лот ждёт решения.", "warn")
        return {"ok": False, "status": "pending_approval", "error": "нет подтверждённых позиций"}

    db.update_lot(lot["id"], status="sending")
    result = send_items([i["id"] for i in sendable], urgent=False)
    if result.get("ok"):
        db.update_lot(
            lot["id"],
            status="sent",
            order_ref=result.get("order_ref"),
            error=None,
            sent_at=db.now_iso(),
        )
        return {"ok": True, "status": "sent", **result}

    db.update_lot(lot["id"], status="failed", error=result.get("error"))
    return {"ok": False, "status": "failed", **result}


def approve_and_send_lot(lot_id: int) -> dict[str, Any]:
    lot = db.get_lot(lot_id)
    if not lot:
        raise KeyError("лот не найден")
    today = db.get_or_create_today_lot()
    if lot["id"] != today["id"]:
        raise ValueError("можно отправить только сегодняшний лот")
    return process_due_lot(force=True)


def send_selected_items(lot_id: int, item_ids: list[int]) -> dict[str, Any]:
    lot = db.get_lot(lot_id)
    if not lot:
        raise KeyError("лот не найден")
    if not item_ids:
        raise ValueError("не выбраны позиции")

    sendable: list[int] = []
    for item_id in item_ids:
        item = db.get_item(item_id)
        if not item:
            raise KeyError(f"позиция {item_id} не найдена")
        if item.get("lot_id") != lot_id:
            raise ValueError("позиция не из этого лота")
        if item["status"] not in {"confirmed", "pending_review"}:
            continue
        if not (item.get("supplier") or "").strip():
            continue
        if item["status"] == "pending_review":
            confirm_item(item_id)
        sendable.append(item_id)

    if not sendable:
        raise ValueError("нет позиций к отправке")

    result = send_items(sendable, urgent=False)
    if result.get("ok"):
        db.add_event(f"Вручную отправлено позиций: {result.get('count', len(sendable))}.")
    return result


def maybe_catch_up() -> None:
    settings = db.get_settings()
    now = datetime.now()
    due = now.hour > settings["send_hour"] or (
        now.hour == settings["send_hour"] and now.minute >= settings["send_minute"]
    )
    if not due:
        return
    lot = db.get_or_create_today_lot()
    if lot["status"] != "collecting":
        return
    items = db.list_items_for_lot(lot["id"])
    if items:
        process_due_lot(force=False)


def snapshot() -> dict[str, Any]:
    settings = db.get_settings()
    lot = db.get_or_create_today_lot()
    adapter = get_adapter()
    vin = db.latest_vehicle_vin()
    vehicle = None
    if vin:
        info = adapter.search_by_vin(vin)
        vehicle = {"vin": info.vin, "title": info.title, "notes": info.notes}
        row = db.get_vehicle_by_vin(vin)
        if row:
            plate_label = garage.format_plate(row["plate"]) if row.get("plate") else ""
            spec_label = garage.format_vehicle(row)
            label = " ".join(part for part in [spec_label or row.get("make"), plate_label] if part)
            vehicle["make"] = row.get("make") or ""
            vehicle["plate"] = row.get("plate") or ""
            vehicle["model"] = row.get("model") or ""
            vehicle["year"] = row.get("year") or ""
            vehicle["engine"] = row.get("engine") or ""
            if label:
                vehicle["title"] = label
    directory = getattr(adapter, "directory", lambda: [{"name": adapter.name, "url": "", "city": CITY}])()
    return {
        "settings": settings,
        "supplier": adapter.name,
        "city": CITY,
        "suppliers": directory,
        "vehicles": db.list_vehicles(),
        "lot": lot,
        "lot_items": db.list_items_for_lot(lot["id"]),
        "urgent": db.list_urgent_open(),
        "events": db.list_events(),
        "lots": db.list_recent_lots(),
        "question": db.latest_open_question(),
        "vehicle": vehicle,
        "llm_configured": llm_enabled(),
        "llm_provider": provider_name(),
        "llm_mode": "nonstandard" if LLM_NONSTANDARD_ONLY else "always",
    }


def resend_request(request_id: int) -> dict[str, Any]:
    row = db.get_request(request_id)
    if not row or row["workspace"]:
        raise KeyError("заявка не найдена")
    text = (row.get("raw_text") or "").strip()
    if not text:
        raise ValueError("у заявки нет текста для повторной отправки")
    db.add_event(f"Повторная отправка заявки #{request_id}.")
    return ingest_text(text)


def archive_for_date(day: str | None = None) -> dict[str, Any]:
    dates = db.list_request_dates()
    chosen = (day or (dates[0] if dates else db.utc_today()))[:10]
    return {
        "date": chosen,
        "dates": dates,
        "requests": db.list_requests_on_date(chosen),
    }
