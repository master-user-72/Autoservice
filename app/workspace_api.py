"""HTTP contracts for the Autoservice browser workspace."""

import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import access, catalog, db, garage, workspace as ws
from app.nlu import preview_parts
from app.suppliers import workspace_demo as demo
from app.workspace_db import VERSION, transaction

router = APIRouter(prefix="/api/workspace")
BUYERS = ("buyer", "admin")


class Credentials(BaseModel):
    name: str = Field(max_length=100)
    password: str = Field(max_length=300)


class VehicleInput(BaseModel):
    vin: str
    make: str = Field(max_length=80)
    model: str = Field(max_length=100)
    generation: str = Field(default="", max_length=32)
    plate: str = Field(default="", max_length=20)
    year: str = Field(default="", max_length=4)
    engine: str = Field(default="", max_length=100)
    body: str = Field(default="", max_length=100)
    revision: int | None = None


class Revision(BaseModel):
    revision: int = Field(ge=1)


class DraftInput(BaseModel):
    vin: str | None = None


class EditDraft(DraftInput, Revision):
    accept_reset: bool = False


class ItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: int = Field(default=1, ge=1, le=99)
    urgent: bool = False
    original_required: bool = False
    article: str | None = Field(default=None, max_length=80)


class EditItem(ItemInput, Revision):
    pass


class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class ApplyText(TextInput, Revision):
    items: list[ItemInput] = Field(min_length=1, max_length=100)


class SearchInput(Revision):
    query: str = Field(default="", max_length=300)
    suppliers: list[str] = Field(default_factory=lambda: list(demo.SOURCES), max_length=4)


class Choice(Revision):
    offer: str | None = None


class Basis(Revision):
    comment: str = Field(min_length=10, max_length=500)


class ItemRef(Revision):
    id: int


class Placement(BaseModel):
    items: list[ItemRef] = Field(min_length=1, max_length=100)
    action: Literal["lot", "urgent", "draft"]
    day: date | None = None


class ReviewInput(BaseModel):
    kind: Literal["lot", "urgent"]
    ids: list[int] = Field(default_factory=list, max_length=100)
    day: date | None = None
    group: str | None = Field(default=None, max_length=50)


class Confirmation(BaseModel):
    allow_unknown_delivery: bool = False


class Reference(BaseModel):
    number: str = Field(min_length=4, max_length=80)


class SourceInput(BaseModel):
    enabled: bool
    scenario: str


class Settings(BaseModel):
    cutoff: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    ttl: int | None = Field(default=None, ge=1, le=120)
    sort: Literal["price", "date"] | None = None
    stock_only: bool | None = None
    originals_only: bool | None = None
    fit_only: bool | None = None


@router.post("/login")
def sign_in(request: Request, body: Credentials):
    return access.login(request, body.name, body.password)


@router.post("/logout")
def sign_out(request: Request):
    access.permitted(request)
    return access.logout()


@router.get("/overview")
def overview(request: Request):
    actor = access.permitted(request)
    with transaction() as conn:
        statuses = ws.sources(conn)
        window = ws.lot_window(conn)
        unread_after = ws.preference(conn, actor, "read_after", 0)
        events = ws.read(conn, "SELECT * FROM workspace_journal ORDER BY id DESC LIMIT 25")
        unread = ws.one(conn, "SELECT count(*) AS n FROM workspace_journal WHERE id>?", (unread_after,))["n"]
        counts = ws.one(conn, """SELECT
            count(CASE WHEN i.workspace_lot IS NOT NULL THEN 1 END) AS lot,
            count(CASE WHEN i.urgent=1 THEN 1 END) AS urgent
            FROM line_items i JOIN requests r ON i.request_id=r.id
            LEFT JOIN workspace_order_items oi ON oi.item_id=i.id
            LEFT JOIN workspace_orders o ON o.id=oi.order_id
            WHERE r.workspace=1 AND i.status!='workspace_cancelled'
            AND (o.id IS NULL OR o.status IN ('manual','unknown','sending','error'))""")
        return {"user": request.state.user, "shared": bool(access.USERS), "events": events, "unread": unread,
                "counts": counts, "window": window, "sources": statuses, "mode": "demo",
                "settings": _settings(conn, actor)}


@router.post("/notifications/read")
def read_notifications(request: Request):
    actor = access.permitted(request)
    with transaction() as conn:
        latest = ws.one(conn, "SELECT coalesce(max(id),0) AS id FROM workspace_journal")["id"]
        ws.set_preference(conn, actor, "read_after", latest)
    return {"ok": True}


@router.get("/vehicle-catalog")
def vehicle_catalog():
    return catalog.vehicle_catalog()


@router.get("/vehicles")
def vehicles(q: str = "", archived: bool = False):
    with transaction() as conn:
        rows = ws.read(conn, """SELECT v.*, (SELECT count(*) FROM requests r WHERE r.vin=v.vin) AS request_count
                              FROM vehicles v WHERE archived=? ORDER BY make,model,vin""", (archived,))
        return [row for row in rows if q.casefold().strip() in
                " ".join(row[key] for key in ("vin", "plate", "make", "model", "generation")).casefold()]


@router.get("/vehicles/{vin}")
def vehicle_detail(vin: str):
    with transaction() as conn:
        row = ws.require(ws.vehicle(conn, vin), "Автомобиль не найден", 404)
        row["requests"] = ws.read(conn, """SELECT id,status,created_at,workspace FROM requests
                                       WHERE vin=? ORDER BY id DESC""", (vin,))
        row["events"] = ws.read(conn, """SELECT * FROM workspace_journal WHERE entity='vehicle' AND entity_id=?
                                     ORDER BY id DESC LIMIT 20""", (vin,))
        return row


@router.post("/vehicles")
def save_vehicle(request: Request, body: VehicleInput):
    actor = access.permitted(request)
    data = body.model_dump(exclude={"revision"})
    if "generation" not in body.model_fields_set:
        data.pop("generation")
    data = {key: value.strip() for key, value in data.items()}
    vin = data["vin"] = data["vin"].upper()
    ws.require(re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin), "VIN должен состоять из 17 знаков без I, O, Q", 422)
    ws.require(data["make"] and data["model"], "Укажите марку и модель", 422)
    year = data["year"]
    ws.require(not year or (year.isascii() and year.isdigit() and 1886 <= int(year) <= ws.now().year + 1),
               "Проверьте год выпуска", 422)
    if data["plate"]:
        data["plate"] = ws.require(garage.normalize_plate(data["plate"]), "Проверьте госномер", 422)
    with transaction() as conn:
        existing = ws.vehicle(conn, vin)
        timestamp = ws.stamp()
        conflict = data["plate"] and ws.one(conn, "SELECT vin FROM vehicles WHERE vin!=? AND plate=?",
                                            (vin, data["plate"]))
        fields = (*data, "plate_digits")
        values = (*data.values(), "".join(c for c in data["plate"] if c.isdigit()))
        if existing:
            ws.require(existing["revision"] == body.revision, "Такой VIN уже есть или запись изменилась")
            conn.execute(f"UPDATE vehicles SET {','.join(key+'=?' for key in fields)},"
                         "updated_at=?,revision=revision+1 WHERE vin=?", (*values, timestamp, vin))
            if any(existing[key] != data[key] for key in data if key not in {"vin", "plate"}):
                ws.invalidate_vehicle(conn, vin)
        else:
            ws.require(body.revision is None, "Автомобиль не найден", 404)
            conn.execute(f"INSERT INTO vehicles({','.join(fields)},created_at,updated_at) "
                         f"VALUES({','.join('?' for _ in range(len(values)+2))})", (*values, timestamp, timestamp))
        ws.journal(conn, actor, "vehicle", vin, "Автомобиль обновлён" if existing else "Автомобиль добавлен")
        return {"vehicle": ws.vehicle(conn, vin), "warning": "Этот госномер уже есть в гараже" if conflict else None}


@router.post("/vehicles/{vin}/archive")
def archive_vehicle(request: Request, vin: str, body: Revision, archived: bool = True):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.require(ws.vehicle(conn, vin), "Автомобиль не найден", 404)
        ws.require(row["revision"] == body.revision, "Автомобиль уже изменён")
        if archived:
            unfinished = ws.one(conn, """SELECT r.id FROM requests r WHERE r.vin=? AND r.workspace=1
                AND r.status!='workspace_cancelled' AND (NOT EXISTS(SELECT 1 FROM line_items i WHERE i.request_id=r.id)
                OR EXISTS(SELECT 1 FROM line_items i LEFT JOIN workspace_order_items oi ON oi.item_id=i.id
                LEFT JOIN workspace_orders o ON o.id=oi.order_id WHERE i.request_id=r.id
                AND i.status!='workspace_cancelled' AND (o.id IS NULL OR o.status NOT IN
                ('accepted','manual_confirmed','cancelled')))) LIMIT 1""", (vin,))
            ws.require(not unfinished, "Закройте незавершённые заявки автомобиля")
        conn.execute("UPDATE vehicles SET archived=?,updated_at=?,revision=revision+1 WHERE vin=?",
                     (archived, ws.stamp(), vin))
        ws.journal(conn, actor, "vehicle", vin, "Автомобиль архивирован" if archived else "Автомобиль восстановлен")
        return ws.vehicle(conn, vin)


@router.get("/requests")
def drafts():
    with transaction() as conn:
        return ws.read(conn, """SELECT id,vin,created_at,status,author FROM requests WHERE workspace=1
                              ORDER BY id DESC LIMIT 150""")


@router.post("/requests")
def create_draft(request: Request, body: DraftInput):
    actor = access.permitted(request)
    with transaction() as conn:
        identifier = ws.new_request(conn, actor, body.vin)
        ws.journal(conn, actor, "request", identifier, "Новая заявка")
        return ws.request_view(conn, identifier)


@router.get("/requests/{request_id}")
def get_draft(request_id: int):
    with transaction() as conn:
        return ws.request_view(conn, request_id)


@router.patch("/requests/{request_id}")
def change_vehicle(request: Request, request_id: int, body: EditDraft):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.request_view(conn, request_id)
        ws.require(row["revision"] == body.revision and row["status"] != "workspace_cancelled", "Заявка уже изменена")
        if row["vin"] != body.vin:
            car = ws.vehicle(conn, body.vin)
            ws.require(car and not car["archived"], "Выберите активный автомобиль", 422)
            ws.require(not any(i["order"] for i in row["items"]), "Для другого автомобиля создайте новую заявку")
            ws.require(body.accept_reset or not any(i["selection"] or i["workspace_lot"] for i in row["items"]),
                       "В заявке есть выбранные предложения. Подтвердите повторный подбор для другого автомобиля.")
            conn.execute("UPDATE requests SET vin=?,revision=revision+1 WHERE id=?", (body.vin, request_id))
            for entry in row["items"]:
                ws.invalidate(conn, entry["id"])
            ws.journal(conn, actor, "request", request_id, "Автомобиль изменён")
        return ws.request_view(conn, request_id)


@router.post("/requests/{request_id}/copy")
def copy_draft(request: Request, request_id: int):
    actor = access.permitted(request)
    with transaction() as conn:
        previous = ws.request_view(conn, request_id)
        car = previous["vehicle"]
        identifier = ws.new_request(conn, actor, car["vin"] if car and not car["archived"] else None, previous["raw_text"])
        for entry in previous["items"]:
            ws.add_item(conn, identifier, entry)
        ws.journal(conn, actor, "request", identifier, "Копия заявки", str(request_id))
        return ws.request_view(conn, identifier)


@router.post("/requests/{request_id}/cancel")
def cancel_draft(request: Request, request_id: int, body: Revision):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.request_view(conn, request_id)
        ws.require(row["revision"] == body.revision and row["status"] != "workspace_cancelled", "Заявка уже изменена")
        ws.require(not any(i["workspace_lot"] or i["order"] for i in row["items"]),
                   "Снимите позиции с лота; оформляемые заявки отменить нельзя")
        conn.execute("UPDATE requests SET status='workspace_cancelled',revision=revision+1 WHERE id=?", (request_id,))
        conn.execute("UPDATE line_items SET status='workspace_cancelled',revision=revision+1 WHERE request_id=?", (request_id,))
        ws.journal(conn, actor, "request", request_id, "Заявка отменена")
        return ws.request_view(conn, request_id)


def _item_input(body):
    data = body.model_dump(exclude={"revision"})
    data["description"] = ws.require(data["description"].strip(), "Введите описание детали", 422)
    return data


@router.post("/requests/{request_id}/items")
def add_position(request: Request, request_id: int, body: ItemInput):
    actor = access.permitted(request)
    with transaction() as conn:
        identifier = ws.add_item(conn, request_id, _item_input(body))
        ws.journal(conn, actor, "request", request_id, "Добавлена позиция", str(identifier))
        return ws.item(conn, identifier)


@router.patch("/items/{item_id}")
def edit_position(request: Request, item_id: int, body: EditItem):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.item(conn, item_id)
        ws.editable(row, body.revision)
        values = _item_input(body)
        if any(values[key] != row[key] for key in ("description", "original_required", "article")):
            ws.invalidate(conn, item_id)
        elif row["selection"] and row["selection"]["stock"] < values["quantity"]:
            conn.execute("UPDATE line_items SET selection=NULL,workspace_lot=NULL WHERE id=?", (item_id,))
        conn.execute("""UPDATE line_items SET description=?,quantity=?,urgent=?,original_required=?,article=?,
                        workspace_lot=CASE WHEN ? THEN NULL ELSE workspace_lot END,
                        revision=revision+1 WHERE id=?""",
                     (*values.values(), values["urgent"], item_id))
        ws.journal(conn, actor, "request", row["request_id"], "Позиция изменена", str(item_id))
        return ws.item(conn, item_id)


@router.post("/items/{item_id}/cancel")
def cancel_position(request: Request, item_id: int, body: Revision):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.item(conn, item_id)
        ws.editable(row, body.revision)
        ws.require(not row["workspace_lot"], "Сначала снимите позицию с лота")
        conn.execute("UPDATE line_items SET status='workspace_cancelled',revision=revision+1 WHERE id=?", (item_id,))
        ws.journal(conn, actor, "request", row["request_id"], "Позиция отменена", str(item_id))
        return {"ok": True}


@router.post("/parse")
def parse(body: TextInput):
    vin, parts, clarification = preview_parts(body.text)
    return {"items": parts, "vin": vin, "question": clarification}


@router.post("/requests/{request_id}/apply-text")
def apply_text(request: Request, request_id: int, body: ApplyText):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.request(conn, request_id)
        ws.require(row["revision"] == body.revision, "Заявка уже изменена")
        for entry in body.items:
            ws.add_item(conn, request_id, _item_input(entry))
        conn.execute("UPDATE requests SET raw_text=? WHERE id=?",
                     (("\n\n".join(filter(None, (row["raw_text"], body.text)))), request_id))
        ws.journal(conn, actor, "request", request_id, "Разбор применён")
        return ws.request_view(conn, request_id)


@router.post("/items/{item_id}/search")
def search(request: Request, body: SearchInput, item_id: int):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.item(conn, item_id)
        ws.editable(row, body.revision)
        ws.require(body.suppliers and set(body.suppliers) <= set(demo.SOURCES), "Выберите поставщиков", 422)
        return ws.latest_search(conn, row, body.query.strip() or row["article"] or row["description"], set(body.suppliers), actor)


@router.post("/items/{item_id}/basis")
def manual_basis(request: Request, body: Basis, item_id: int):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.item(conn, item_id)
        ws.editable(row, body.revision)
        result = row["search_result"]
        ws.require(result and result["catalogue"] and result["offers"], "Сначала выберите точную деталь и выполните поиск")
        comment = body.comment.strip()
        ws.require(len(comment) >= 10, "Укажите основание проверки", 422)
        basis = {"comment": comment, "catalogue": result["catalogue"], "actor": actor, "at": ws.stamp()}
        conn.execute("UPDATE line_items SET manual_basis=?,revision=revision+1 WHERE id=?", (ws.dump(basis), item_id))
        ws.journal(conn, actor, "request", row["request_id"], "Ручная проверка применимости", comment)
        return ws.item(conn, item_id)


@router.post("/items/{item_id}/choice")
def choose(request: Request, body: Choice, item_id: int):
    actor = access.permitted(request)
    with transaction() as conn:
        row = ws.item(conn, item_id)
        ws.editable(row, body.revision)
        offer = None
        if body.offer:
            offer = next((o for o in (row["search_result"] or {}).get("offers", []) if o["id"] == body.offer), None)
            ws.require(offer, "Предложение не найдено", 404)
            ws.verified_selection(conn, {**row, "selection": offer})
        conn.execute("""UPDATE line_items SET selection=?,conditions_delta=NULL,revision=revision+1,
                       workspace_lot=CASE WHEN ? IS NULL THEN NULL ELSE workspace_lot END,
                       urgent=CASE WHEN ? IS NULL THEN 0 ELSE urgent END WHERE id=?""",
                     (ws.dump(offer) if offer else None, body.offer, body.offer, item_id))
        ws.journal(conn, actor, "request", row["request_id"], "Предложение выбрано" if offer else "Выбор снят")
        return ws.item(conn, item_id)


@router.post("/placement")
def place(request: Request, body: Placement):
    actor = access.permitted(request)
    with transaction() as conn:
        ws.require(len({entry.id for entry in body.items}) == len(body.items), "Позиции не должны повторяться", 422)
        rows = []
        for entry in body.items:
            row = ws.item(conn, entry.id)
            ws.editable(row, entry.revision)
            rows.append(row)
        if body.action == "lot":
            ws.require(body.day, "Выберите дату лота", 422)
            ws.place_in_lot(conn, rows, body.day.isoformat(), actor)
        else:
            urgent = body.action == "urgent"
            for row in rows:
                if urgent:
                    ws.verified_selection(conn, row)
                conn.execute("UPDATE line_items SET workspace_lot=NULL,urgent=?,revision=revision+1 WHERE id=?",
                             (urgent, row["id"]))
                ws.journal(conn, actor, "request", row["request_id"],
                           "Переведена в срочные" if urgent else "Возвращена в черновик", str(row["id"]))
        return {"ok": True}


@router.get("/lots")
def lots(day: date | None = None):
    with transaction() as conn:
        return ws.lot_view(conn, day.isoformat() if day else None)


@router.get("/urgent")
def urgent():
    with transaction() as conn:
        return [ws.item(conn, row["id"]) for row in ws.read(conn, """SELECT i.id FROM line_items i
                JOIN requests r ON r.id=i.request_id WHERE r.workspace=1 AND i.urgent=1
                AND i.workspace_lot IS NULL AND i.status!='workspace_cancelled' ORDER BY i.id DESC""")]


@router.post("/review")
def review(request: Request, body: ReviewInput):
    actor = access.permitted(request, *BUYERS)
    ws.require((body.day and body.group and not body.ids) if body.kind == "lot" else
               (len(body.ids) == 1 and body.day is None and body.group is None), "Укажите группу или срочную позицию", 422)
    with transaction() as conn:
        return ws.review(conn, actor, body.kind, body.ids, body.day.isoformat() if body.day else None, body.group)


@router.post("/review/{token}/confirm")
def confirm(request: Request, token: str, body: Confirmation):
    actor = access.permitted(request, *BUYERS)
    with transaction() as conn:
        result = ws.confirm(conn, actor, token, body.allow_unknown_delivery)
    for order_id in result["orders"]:
        ws.dispatch(order_id)
    with transaction() as conn:
        return {**result, "orders": [ws.order_view(conn, identifier) for identifier in result["orders"]]}


@router.get("/orders")
def orders(q: str = "", supplier: str = "", status: str = "", kind: str = "",
           start: date | None = None, end: date | None = None, page: int = 1):
    page = max(1, page)
    with transaction() as conn:
        ws.recover_interrupted(conn)
        rows = ws.read(conn, """SELECT id,created_at FROM workspace_orders
                              WHERE (?='' OR supplier=?) AND (?='' OR status=?) AND (?='' OR kind=?)
                              ORDER BY created_at DESC,rowid DESC""", (supplier, supplier, status, status, kind, kind))
        views = []
        for row in rows:
            local_day = ws.datetime.fromisoformat(row["created_at"]).astimezone(ws.EKATERINBURG).date()
            if (start and local_day < start) or (end and local_day > end):
                continue
            order = ws.order_view(conn, row["id"], include_journal=False)
            fields = [order["id"], order["supplier_ref"] or "", order["supplier"]]
            for entry in order["items"]:
                fields += [entry["vehicle"]["vin"], entry["vehicle"]["plate"], entry["offer"]["article"],
                           entry["offer"]["oem"], entry["description"]]
            if q.strip().casefold() in " ".join(fields).casefold():
                views.append(order)
        return {"orders": views[(page-1)*25:page*25], "total": len(views), "page": page}


@router.get("/orders/{order_id}")
def detail(order_id: str):
    with transaction() as conn:
        ws.recover_interrupted(conn)
        return ws.order_view(conn, order_id)


@router.post("/orders/{order_id}/manual")
def record_reference(request: Request, order_id: str, body: Reference):
    actor = access.permitted(request, *BUYERS)
    reference = body.number.strip().upper()
    ws.require(re.fullmatch(r"DEMO-[A-Z0-9-]{2,75}", reference), "Учебный номер должен начинаться с DEMO-", 422)
    with transaction() as conn:
        row = ws.order_view(conn, order_id)
        if row["status"] == "manual_confirmed" and row["supplier_ref"] == reference:
            return row
        ws.require(row["status"] == "manual", "Заказ закрыт для ручного оформления")
        ws.require(not ws.one(conn, "SELECT id FROM workspace_orders WHERE supplier=? AND supplier_ref=?",
                              (row["supplier"], reference)), "Этот номер поставщика уже зарегистрирован")
        ws.order_status(conn, order_id, actor, "manual_confirmed", reference, "Сотрудник записал учебный номер заказа")
        return ws.order_view(conn, order_id)


@router.post("/orders/{order_id}/reconcile")
def reconcile(request: Request, order_id: str):
    actor = access.permitted(request, *BUYERS)
    with transaction() as conn:
        ws.recover_interrupted(conn)
        row = ws.order_view(conn, order_id)
        if row["status"] == "accepted":
            return row
        ws.require(row["status"] == "unknown", "Сверка доступна для неизвестного результата")
        receipt = ws.one(conn, "SELECT ref FROM workspace_demo_receipts WHERE order_id=?", (order_id,))
        if receipt:
            ws.order_status(conn, order_id, actor, "accepted", receipt["ref"], "Сверка: учебный заказ найден")
        else:
            ws.journal(conn, actor, "order", order_id, "Сверка: подтверждение отсутствует. Повтор заблокирован")
        return ws.order_view(conn, order_id)


@router.post("/orders/{order_id}/retry-review")
def retry_review(request: Request, order_id: str):
    actor = access.permitted(request, *BUYERS)
    with transaction() as conn:
        return ws.retry_review(conn, actor, order_id)


@router.post("/orders/{order_id}/cancel")
def cancel_order(request: Request, order_id: str):
    actor = access.permitted(request, *BUYERS)
    with transaction() as conn:
        row = ws.order_view(conn, order_id)
        if row["status"] == "cancelled":
            return row
        ws.require(row["status"] in ("manual", "error"), "Отмена этого заказа через приложение недоступна")
        ws.require(not ws.one(conn, "SELECT 1 FROM workspace_demo_receipts WHERE order_id=?", (order_id,)),
                   "Заказ уже зарегистрирован поставщиком")
        ws.order_status(conn, order_id, actor, "cancelled", None, "Сотрудник отменил незавершённое учебное оформление")
        return ws.order_view(conn, order_id)


@router.post("/orders/{order_id}/copy")
def repeat_order(request: Request, order_id: str):
    actor = access.permitted(request)
    with transaction() as conn:
        order = ws.order_view(conn, order_id)
        vehicles = {line["vehicle"]["vin"] for line in order["items"]}
        vin = next(iter(vehicles)) if len(vehicles) == 1 else None
        car = ws.vehicle(conn, vin)
        identifier = ws.new_request(conn, actor, vin if car and not car["archived"] else None)
        for entry in order["items"]:
            ws.add_item(conn, identifier, {"description": entry["description"], "quantity": entry["quantity"],
                                           "urgent": order["kind"] == "urgent", "original_required": entry["offer"]["original"]})
        ws.journal(conn, actor, "request", identifier, "Создана новая заявка из заказа", order_id)
        return ws.request_view(conn, identifier)


@router.get("/suppliers")
def supplier_list():
    with transaction() as conn:
        rows = ws.sources(conn)
        return [{**row, "title": demo.SOURCES[key], "capabilities": demo.capabilities(key, row["scenario"]),
                 "journal": ws.read(conn, """SELECT * FROM workspace_journal WHERE entity='supplier' AND entity_id=?
                                              ORDER BY id DESC LIMIT 10""", (key,))} for key, row in rows.items()]


@router.patch("/suppliers/{key}")
def supplier_config(request: Request, key: str, body: SourceInput):
    actor = access.permitted(request, "admin")
    ws.require(key in demo.SOURCES and body.scenario in demo.SCENARIOS, "Неизвестный поставщик или сценарий", 422)
    with transaction() as conn:
        ws.sources(conn)
        conn.execute("""UPDATE workspace_sources SET enabled=?,scenario=?,last_status=NULL,
                        checked_at=NULL,revision=revision+1 WHERE name=?""", (body.enabled, body.scenario, key))
        ws.journal(conn, actor, "supplier", key, "Учебная конфигурация изменена", demo.SCENARIOS[body.scenario])
        return {"ok": True}


@router.post("/suppliers/{key}/check")
def supplier_check(request: Request, key: str, body: TextInput):
    actor = access.permitted(request, "admin")
    with transaction() as conn:
        row = ws.require(ws.sources(conn).get(key), "Источник не найден", 404)
        last = row["checked_at"]
        ws.require(not last or ws.datetime.fromisoformat(last) + timedelta(seconds=3) <= ws.now(),
                   "Повторите диагностику через несколько секунд", 429)
        part = demo.catalogue_match(body.text)
        if not row["enabled"]:
            code, offer = "NO_ACCESS", None
        elif not part:
            code, offer = "NO_OFFERS", None
        else:
            code, offer = demo.quote(key, row["scenario"], part, demo.DEMO_CAR,
                                     ws.now().astimezone(ws.EKATERINBURG).date(), ws.stamp())
        conn.execute("""UPDATE workspace_sources SET last_status=?,checked_at=?,
                        last_success=CASE WHEN ? IN ('OK','NO_OFFERS') THEN ? ELSE last_success END WHERE name=?""",
                     (code, ws.stamp(), code, ws.stamp(), key))
        ws.journal(conn, actor, "supplier", key, "Учебная диагностика чтения", code)
        return {"status": code, "offer": offer}


def _settings(conn, actor):
    settings = {key: ws.preference(conn, "*", key, default)
                for key, default in {"cutoff": ws.CUTOFF, "ttl": 15}.items()}
    settings.update({key: ws.preference(conn, actor, key, default)
                     for key, default in {"sort": "price", "stock_only": False,
                                          "originals_only": False, "fit_only": False}.items()})
    return {**settings, "schema": VERSION, "scenarios": demo.SCENARIOS}


@router.patch("/settings")
def update_settings(request: Request, body: Settings):
    actor = access.permitted(request)
    changes = body.model_dump(exclude_none=True)
    if {"cutoff", "ttl"} & changes.keys():
        access.permitted(request, "admin")
    with transaction() as conn:
        ws.close_due(conn)
        for key, value in changes.items():
            ws.set_preference(conn, "*" if key in {"cutoff", "ttl"} else actor, key, value)
        ws.journal(conn, actor, "settings", actor, "Настройки сохранены", ws.dump(changes))
        return _settings(conn, actor)


@router.post("/example")
def example(request: Request):
    actor = access.permitted(request)
    with transaction() as conn:
        car = ws.vehicle(conn, demo.DEMO_VIN)
        if not car:
            data = demo.DEMO_CAR
            conn.execute("""INSERT INTO vehicles(vin,make,model,year,engine,body,plate,plate_digits,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?)""", (*data.values(), "12396", ws.stamp(), ws.stamp()))
        identifier = ws.new_request(conn, actor, demo.DEMO_VIN)
        for index, description in enumerate(("Масляный фильтр", "Воздушный фильтр")):
            item_id = ws.add_item(conn, identifier, {"description": description, "quantity": 1,
                                                   "original_required": bool(index), "urgent": False})
            row = ws.latest_search(conn, ws.item(conn, item_id), description, set(demo.SOURCES), actor)
            for offer in row["search_result"]["offers"]:
                if offer["supplier"] == ("partkom" if index else "rossko") and offer["fit"] == "catalogue" and offer["price"] is not None:
                    conn.execute("UPDATE line_items SET selection=? WHERE id=?", (ws.dump(offer), item_id))
        ws.journal(conn, actor, "request", identifier, "Создан учебный пример")
        return ws.request_view(conn, identifier)
