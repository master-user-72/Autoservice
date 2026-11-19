"""Workspace transactions, search, draft state and purchase orchestration."""

import json
import uuid
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.suppliers import workspace_demo as demo
from app.workspace_db import transaction

EKATERINBURG = ZoneInfo("Asia/Yekaterinburg")
TERMS = ("price", "currency", "stock", "delivery", "date_from", "date_to", "pickup", "channel")
CUTOFF = "16:00"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp():
    return now().isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def read(conn, sql, args=()):
    return [dict(row) for row in conn.execute(sql, args)]


def one(conn, sql, args=()):
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def require(value, message, code=409):
    if not value:
        raise HTTPException(code, message)
    return value


def journal(conn, actor, entity, entity_id, action, detail=""):
    conn.execute(
        "INSERT INTO workspace_journal(at,actor,entity,entity_id,action,detail) VALUES(?,?,?,?,?,?)",
        (stamp(), actor, entity, str(entity_id), action, detail),
    )


def preference(conn, owner, key, default):
    row = one(conn, "SELECT value FROM workspace_preferences WHERE owner=? AND key=?", (owner, key))
    return json.loads(row["value"]) if row else default


def set_preference(conn, owner, key, value):
    conn.execute("INSERT OR REPLACE INTO workspace_preferences VALUES(?,?,?)", (owner, key, dump(value)))


def sources(conn):
    for key in demo.SOURCES:
        conn.execute("INSERT OR IGNORE INTO workspace_sources(name) VALUES(?)", (key,))
    return {row["name"]: row for row in read(conn, "SELECT * FROM workspace_sources")}


def vehicle(conn, vin):
    return one(conn, "SELECT * FROM vehicles WHERE vin=?", (vin,))


def request(conn, request_id):
    return require(one(conn, "SELECT * FROM requests WHERE id=? AND workspace=1", (request_id,)),
                   "Заявка не найдена", 404)


def item(conn, item_id):
    row = require(one(conn, """SELECT i.*, r.vin, r.author FROM line_items i JOIN requests r
                      ON r.id=i.request_id WHERE i.id=? AND r.workspace=1""", (item_id,)),
                  "Позиция не найдена", 404)
    for key in ("search_result", "selection", "manual_basis", "conditions_delta"):
        row[key] = json.loads(row[key]) if row[key] else None
    row["order"] = one(conn, """SELECT o.id,o.status,o.supplier_ref FROM workspace_order_items i
                               JOIN workspace_orders o ON o.id=i.order_id WHERE i.item_id=?""", (item_id,))
    return row


def request_view(conn, request_id):
    row = request(conn, request_id)
    row["vehicle"] = vehicle(conn, row["vin"])
    row["items"] = [item(conn, entry["id"]) for entry in read(
        conn, "SELECT id FROM line_items WHERE request_id=? AND status!='workspace_cancelled' ORDER BY id",
        (request_id,))]
    row["status"] = request_status(row)
    return row


def request_status(row):
    if row["status"] == "workspace_cancelled":
        return row["status"]
    if row["items"] and all(i["order"] and i["order"]["status"] in ("accepted", "manual_confirmed") for i in row["items"]):
        return "workspace_complete"
    if any(i["order"] or i["workspace_lot"] or i["urgent"] for i in row["items"]):
        return "workspace_in_progress"
    return "workspace_draft"


def new_request(conn, author, vin=None, raw_text=""):
    if vin:
        car = vehicle(conn, vin)
        require(car and not car["archived"], "Выберите активный автомобиль", 422)
    return conn.execute("""INSERT INTO requests(created_at,raw_text,vin,status,workspace,author)
                           VALUES(?,?,?,'workspace_draft',1,?)""", (stamp(), raw_text, vin, author)).lastrowid


def add_item(conn, request_id, values):
    row = request(conn, request_id)
    require(row["status"] != "workspace_cancelled", "Заявка отменена")
    cursor = conn.execute("""INSERT INTO line_items(created_at,request_id,description,quantity,urgent,
                             original_required, article, status) VALUES(?,?,?,?,?,?,?,'workspace_draft')""",
                          (stamp(), request_id, values["description"], values["quantity"], values["urgent"],
                           values["original_required"], values.get("article")))
    conn.execute("UPDATE requests SET revision=revision+1 WHERE id=?", (request_id,))
    return cursor.lastrowid


def invalidate_vehicle(conn, vin):
    for row in read(conn, """SELECT i.id FROM line_items i JOIN requests r ON r.id=i.request_id
        WHERE r.workspace=1 AND r.vin=? AND NOT EXISTS (
        SELECT 1 FROM workspace_order_items o WHERE o.item_id=i.id)""", (vin,)):
        invalidate(conn, row["id"])


def invalidate(conn, item_id):
    conn.execute("""UPDATE line_items SET search_result=NULL,selection=NULL,manual_basis=NULL,conditions_delta=NULL,
                    workspace_lot=NULL,revision=revision+1 WHERE id=?""", (item_id,))


def editable(row, revision=None):
    require(not row["order"] and row["status"] != "workspace_cancelled", "Позиция закрыта для изменения")
    if revision is not None:
        require(row["revision"] == revision, "Позиция уже изменена. Обновите данные и повторите действие.")


def latest_search(conn, row, query, supplier_keys, actor):
    editable(row)
    car = vehicle(conn, row["vin"])
    require(car and not car["archived"], "Сначала выберите активный автомобиль", 422)
    part = demo.catalogue_match(query)
    described = demo.catalogue_match(row["description"])
    if described and part and described["article"] != part["article"]:
        raise HTTPException(422, "Артикул относится к другой детали. Исправьте описание позиции.")
    checked = stamp()
    checked_day = now().astimezone(EKATERINBURG).date()
    offers = []
    results = {}
    for name, source in sources(conn).items():
        status = "NOT_QUERIED"
        if name in supplier_keys:
            if not source["enabled"]:
                status = "NO_ACCESS"
            elif part:
                status, offer = demo.quote(name, source["scenario"], part, car, checked_day, checked)
                if offer and (not row["original_required"] or offer["original"]):
                    offer["source_revision"] = source["revision"]
                    offers.append(offer)
                elif offer:
                    status = "NO_OFFERS"
                conn.execute(
                    """UPDATE workspace_sources SET last_status=?,checked_at=?,
                       last_success=CASE WHEN ? IN ('OK','NO_OFFERS') THEN ? ELSE last_success END
                       WHERE name=?""", (status, checked, status, checked, name),
                )
        results[name] = status
    result = {"at": checked, "query": query, "offers": offers, "sources": results,
              "needs_detail": part is None, "catalogue": part["article"] if part else None}
    previous = row["search_result"]
    if previous and previous["query"] == query:
        result["offers"] += [o for o in previous["offers"] if o["supplier"] not in supplier_keys]
        for key, code in previous["sources"].items():
            if key not in supplier_keys:
                results[key] = code
    delta = row["conditions_delta"]
    selection = row["selection"]
    if selection and selection["supplier"] in supplier_keys:
        replacement = next((o for o in offers if o["id"] == selection["id"]), None)
        delta = changes(selection, replacement)
        if replacement:
            selection = replacement
        else:
            selection = None
    if previous and previous["catalogue"] != result["catalogue"]:
        selection = None
        conn.execute("UPDATE line_items SET manual_basis=NULL WHERE id=?", (row["id"],))
    conn.execute("""UPDATE line_items SET search_result=?, selection=?, conditions_delta=?,
                    workspace_lot=CASE WHEN ? IS NULL THEN NULL ELSE workspace_lot END,
                    revision=revision+1 WHERE id=?""",
                 (dump(result), dump(selection) if selection else None, dump(delta) if delta else None,
                  selection["id"] if selection else None, row["id"]))
    journal(conn, actor, "request", row["request_id"], "Предложения проверены", dump(results))
    return item(conn, row["id"])


def fit(row, offer):
    if offer["fit"] == "catalogue":
        return "Каталог · " + offer["basis"]
    manual = row["manual_basis"]
    if manual and manual["catalogue"] == offer["catalogue"]:
        return "Ручная проверка · " + manual["comment"]
    return None


def eligible(row, offer, *, allow_unknown=True):
    require(offer and fit(row, offer), "Укажите основание применимости", 422)
    require(not row["original_required"] or offer["original"], "Допустим только оригинал", 422)
    require(offer["price"] is not None, "Цена не указана", 422)
    require(offer["stock"] is not None and offer["stock"] >= row["quantity"], "Недостаточный остаток", 422)
    require(offer["delivery"] is not None or allow_unknown, "Подтвердите предварительную стоимость доставки", 422)


def cutoff_for(conn, day):
    value = preference(conn, "*", "cutoff", CUTOFF)
    return datetime.combine(day, time.fromisoformat(value), EKATERINBURG).astimezone(timezone.utc).isoformat()


def close_due(conn):
    when = stamp()
    due = read(conn, "SELECT day FROM workspace_lots WHERE closed_at IS NULL AND cutoff<=?", (when,))
    for row in due:
        day = row["day"]
        conn.execute("UPDATE workspace_lots SET closed_at=? WHERE day=?", (when, day))
        if one(conn, "SELECT id FROM line_items WHERE workspace_lot=? LIMIT 1", (day,)):
            journal(conn, "Планировщик", "lot", day, "Лот ждёт подтверждения")


def tick():
    with transaction() as conn:
        close_due(conn)
        recover_interrupted(conn)


def next_workday(day):
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def lot_window(conn):
    close_due(conn)
    today = now().astimezone(EKATERINBURG).date()
    stored = one(conn, "SELECT * FROM workspace_lots WHERE day=?", (today.isoformat(),))
    current = today.weekday() < 5 and (
        not stored["closed_at"] if stored else stamp() < cutoff_for(conn, today))
    return {"today": today.isoformat(), "open": today.isoformat() if current else None,
            "next": next_workday(today).isoformat()}


def verified_selection(conn, row):
    offer = row["selection"]
    eligible(row, offer)
    source = sources(conn)[offer["supplier"]]
    require(source["enabled"], "Поставщик отключён")
    require(source["revision"] == offer.get("source_revision", 1), "Настройки поставщика изменились. Повторите поиск.")
    ttl = preference(conn, "*", "ttl", 15)
    require(datetime.fromisoformat(offer["checked_at"]) + timedelta(minutes=ttl) >= now(), "Предложение устарело. Повторите поиск.")
    return offer


def place_in_lot(conn, rows, day, actor):
    window = lot_window(conn)
    require(day in (window["open"], window["next"]) and day, "Лот закрыт. Выберите следующую рабочую дату.")
    stored = one(conn, "SELECT * FROM workspace_lots WHERE day=?", (day,))
    require(not stored or not stored["closed_at"], "Лот закрыт")
    conn.execute("INSERT OR IGNORE INTO workspace_lots(day,cutoff) VALUES(?,?)",
                 (day, cutoff_for(conn, datetime.fromisoformat(day).date())))
    for row in rows:
        editable(row)
        verified_selection(conn, row)
    for row in rows:
        conn.execute("UPDATE line_items SET urgent=0,workspace_lot=?,revision=revision+1 WHERE id=?", (day, row["id"]))
    journal(conn, actor, "lot", day, "Позиции сохранены в лот", str(len(rows)))


def delivery_key(offer):
    return (offer["date_from"] or "") + "/" + (offer["date_to"] or "")


def lot_rows(conn, day):
    return [item(conn, row["id"]) for row in read(conn,
            "SELECT id FROM line_items WHERE workspace_lot=? ORDER BY id", (day,))]


def lot_view(conn, day):
    window = lot_window(conn)
    day = day or window["today"]
    lot = one(conn, "SELECT * FROM workspace_lots WHERE day=?", (day,))
    groups = defaultdict(list)
    for row in lot_rows(conn, day):
        groups[delivery_key(row["selection"]) if row["selection"] else "/"].append(row)
    orders = [order_view(conn, order["id"], include_journal=False) for order in
              read(conn, "SELECT id FROM workspace_orders WHERE lot_day=? ORDER BY created_at,id", (day,))]
    outcomes = {order["status"] for order in orders}
    if not lot:
        status = "empty"
    elif len(outcomes) > 1 or orders and any(not i["order"] for rows in groups.values() for i in rows):
        status = "partial"
    elif orders and outcomes <= {"accepted", "manual_confirmed"}:
        status = "complete"
    elif orders:
        status = next(iter(outcomes))
    else:
        status = "closed" if lot["closed_at"] else "open"
    return {"day": day, "cutoff": lot["cutoff"] if lot else cutoff_for(conn, datetime.fromisoformat(day).date()),
            "status": status, "lot": lot, "groups": dict(sorted(groups.items())), "orders": orders,
            "dates": [r["day"] for r in read(conn, "SELECT day FROM workspace_lots ORDER BY day DESC")], "window": window}


def changes(before, after):
    return {key: {"before": before[key], "after": after[key] if after else None}
            for key in TERMS if after is None or before[key] != after[key]}


def review(conn, actor, kind, identifiers, day=None, group=None):
    if kind == "lot":
        view = lot_view(conn, day)
        require(view["lot"] and view["lot"]["closed_at"], "Подтверждение доступно после закрытия лота")
        rows = [row for row in view["groups"].get(group, []) if not row["order"]]
    else:
        rows = [item(conn, i) for i in identifiers]
        require(len(rows) == 1 and rows[0]["urgent"] and not rows[0]["workspace_lot"],
                "Сначала переместите позицию в срочные")
    require(rows, "Нет позиций для подтверждения")
    payload = {"kind": kind, "day": day, "group": group, "rows": []}
    for row in rows:
        editable(row)
        offer = row["selection"]
        eligible(row, offer)
        car = require(vehicle(conn, row["vin"]), "Автомобиль не найден")
        payload["rows"].append({"id": row["id"], "revision": row["revision"], "request_id": row["request_id"],
                                "vehicle": car, "description": row["description"], "quantity": row["quantity"],
                                "offer": offer, "basis": fit(row, offer), "manual_basis": row["manual_basis"]})
    return store_review(conn, actor, payload)


def store_review(conn, actor, payload):
    token = uuid.uuid4().hex
    conn.execute("DELETE FROM workspace_reviews WHERE expires<? AND result IS NULL", ((now() - timedelta(days=1)).isoformat(),))
    conn.execute("INSERT INTO workspace_reviews(id,actor,payload,expires) VALUES(?,?,?,?)",
                 (token, actor, dump(payload), (now() + timedelta(minutes=15)).isoformat()))
    return {"id": token, **payload}


def retry_review(conn, actor, order_id):
    order = order_view(conn, order_id)
    require(order["status"] == "error" and order["channel"] == "demo_api", "Повтор для этого заказа недоступен")
    require(not one(conn, "SELECT 1 FROM workspace_demo_receipts WHERE order_id=?", (order_id,)),
            "Обнаружен заказ поставщика. Повтор заблокирован.")
    return store_review(conn, actor, {"kind": "retry", "order_id": order_id, "rows": order["items"],
                                     "last_event": order["journal"][-1]["id"]})


def confirm_retry(conn, actor, payload, allow_unknown):
    order_id = payload["order_id"]
    order = order_view(conn, order_id)
    require(order["status"] == "error" and order["journal"][-1]["id"] == payload["last_event"],
            "Состояние заказа изменилось. Откройте новый обзор.")
    require(not one(conn, "SELECT 1 FROM workspace_demo_receipts WHERE order_id=?", (order_id,)),
            "Обнаружен заказ поставщика. Повтор заблокирован.")
    source = sources(conn)[order["supplier"]]
    require(source["enabled"], "Поставщик отключён")
    issues = []
    for line in payload["rows"]:
        row = item(conn, line["id"])
        car = vehicle(conn, line["vehicle"]["vin"])
        require(car and not car["archived"]
                and all(car[k] == line["vehicle"][k] for k in ("make", "model", "year", "engine", "body")),
                "Автомобиль изменился. Для новой закупки создайте заявку.")
        old = line["offer"]
        part = demo.catalogue_match(old["catalogue"])
        code, current = demo.quote(order["supplier"], source["scenario"], part, car,
                                   now().astimezone(EKATERINBURG).date(), stamp())
        if code != "OK":
            issues.append({"id": line["id"], "status": code})
        elif delta := changes(old, current):
            issues.append({"id": line["id"], "changes": delta})
        else:
            eligible(row, current, allow_unknown=allow_unknown)

    if issues:
        return {"orders": [], "issues": issues, "requires_new_request": True}

    conn.execute("UPDATE workspace_orders SET dispatch_scenario=? WHERE id=?", (source["scenario"], order_id))
    order_status(conn, order_id, actor, "sending", None, "Подтверждён повтор после известного отказа")
    return {"orders": [order_id], "issues": []}


def confirm(conn, actor, token, allow_unknown):
    record = require(one(conn, "SELECT * FROM workspace_reviews WHERE id=? AND actor=?", (token, actor)),
                     "Обзор не найден", 404)
    if record["result"]:
        return json.loads(record["result"])
    require(record["expires"] >= stamp(), "Срок подтверждения истёк. Откройте новый обзор.")
    payload = json.loads(record["payload"])
    if payload["kind"] == "retry":
        result = confirm_retry(conn, actor, payload, allow_unknown)
        conn.execute("UPDATE workspace_reviews SET result=? WHERE id=?", (dump(result), token))
        return result
    if payload["kind"] == "lot":
        rows = [row["id"] for row in lot_rows(conn, payload["day"])
                if not row["order"] and row["selection"] and delivery_key(row["selection"]) == payload["group"]]
        require(rows == [entry["id"] for entry in payload["rows"]], "Состав группы изменился. Откройте новый обзор.")
    active = sources(conn)
    by_supplier = defaultdict(list)
    issues = []
    for snapshot in payload["rows"]:
        row = item(conn, snapshot["id"])
        editable(row, snapshot["revision"])
        offer = snapshot["offer"]
        require(offer == row["selection"], "Выбор изменился. Откройте новый обзор.")
        source = active[offer["supplier"]]
        part = demo.catalogue_match(offer["catalogue"])
        car = vehicle(conn, row["vin"])
        require(car and not car["archived"] and car["revision"] == snapshot["vehicle"]["revision"],
                "Данные автомобиля изменились. Выполните повторный поиск.")
        code, current = ("NO_ACCESS", None)
        if source["enabled"] and part:
            code, current = demo.quote(offer["supplier"], source["scenario"], part, car,
                                       now().astimezone(EKATERINBURG).date(), stamp())
        if code != "OK":
            issues.append({"id": row["id"], "status": code})
            continue
        current["source_revision"] = source["revision"]
        delta = changes(offer, current)
        if delta:
            issues.append({"id": row["id"], "changes": delta})
            search = row["search_result"]
            if search:
                search["offers"] = [current if o["id"] == current["id"] else o for o in search["offers"]]
            conn.execute("""UPDATE line_items SET selection=?,conditions_delta=?,search_result=?,
                            revision=revision+1 WHERE id=?""",
                         (dump(current), dump(delta), dump(search) if search else None, row["id"]))
            journal(conn, actor, "request", row["request_id"], "Условия изменились", dump(delta))
            continue
        eligible(row, current, allow_unknown=allow_unknown)
        snapshot["offer"] = current
        by_supplier[offer["supplier"]].append(snapshot)
    operations = []
    if not issues:
        for supplier, lines in by_supplier.items():
            requested = defaultdict(int)
            for line in lines:
                offer = line["offer"]
                requested[offer["id"]] += line["quantity"]
                require(requested[offer["id"]] <= offer["stock"],
                        "Общего остатка недостаточно для нескольких позиций одной детали", 422)
            operation = uuid.uuid4().hex
            channel = lines[0]["offer"]["channel"]
            status = "manual" if channel == "manual" else "sending"
            conn.execute("""INSERT INTO workspace_orders(id,supplier,kind,lot_day,delivery_key,channel,status,
                         author,created_at,updated_at,dispatch_scenario) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                         (operation, supplier, payload["kind"], payload["day"], payload["group"], channel,
                          status, actor, stamp(), stamp(), active[supplier]["scenario"]))
            for line in lines:
                conn.execute("INSERT INTO workspace_order_items VALUES(?,?,?)", (operation, line["id"], dump(line)))
                conn.execute("UPDATE line_items SET conditions_delta=NULL,revision=revision+1 WHERE id=?", (line["id"],))
            journal(conn, actor, "order", operation, "Подтверждение и перепроверка", token)
            journal(conn, actor, "order", operation,
                    "Ожидается номер из учебного кабинета" if status == "manual" else "Попытка отправки зарегистрирована")
            operations.append(operation)
    result = {"orders": operations, "issues": issues}
    conn.execute("UPDATE workspace_reviews SET result=? WHERE id=?", (dump(result), token))
    return result


def order_status(conn, order_id, actor, status, reference, action):
    conn.execute("UPDATE workspace_orders SET status=?,supplier_ref=?,updated_at=? WHERE id=?",
                 (status, reference, stamp(), order_id))
    journal(conn, actor, "order", order_id, action)


def dispatch(order_id):
    with transaction() as conn:
        order = one(conn, "SELECT * FROM workspace_orders WHERE id=?", (order_id,))
        if not order or order["status"] != "sending":
            return
        status, reference = demo.outcome(order["dispatch_scenario"], order_id)
        if reference:
            conn.execute("INSERT INTO workspace_demo_receipts VALUES(?,?)", (order_id, reference))
        order_status(conn, order_id, "Демо-адаптер", status, reference if status == "accepted" else None,
                     {"accepted": "Учебный поставщик принял заказ", "unknown": "Ответ потерян. Требуется сверка",
                      "error": "Учебный поставщик отклонил заказ"}[status])


def recover_interrupted(conn):
    for order in read(conn, "SELECT id FROM workspace_orders WHERE status='sending' AND updated_at<=?",
                      ((now() - timedelta(seconds=30)).isoformat(),)):
        order_status(conn, order["id"], "Сервер", "unknown", None, "Отправка прервана. Требуется сверка")


def order_view(conn, order_id, *, include_journal=True):
    row = require(one(conn, "SELECT * FROM workspace_orders WHERE id=?", (order_id,)), "Заказ не найден", 404)
    row["items"] = [json.loads(line["snapshot"]) for line in read(
        conn, "SELECT snapshot FROM workspace_order_items WHERE order_id=? ORDER BY item_id", (order_id,))]
    if include_journal:
        row["journal"] = read(conn, "SELECT * FROM workspace_journal WHERE entity='order' AND entity_id=? ORDER BY id",
                              (order_id,))
    return row
