from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db, garage, workspace
from app import access
from app.workspace_api import router as workspace_router
from app.workspace_db import migrate
from app.config import DATA_DIR, WEB_DIR
from app.idle_shutdown import touch as touch_client_activity
from app.log import setup_logging
from app.lot_service import (
    approve_and_send_lot,
    archive_for_date,
    confirm_all_in_lot,
    confirm_item,
    ingest_text,
    process_due_lot,
    reject_item,
    replace_item,
    set_item_quantity,
    resend_request,
    send_selected_items,
    send_urgent_item,
    snapshot,
)
from app.models import IngestBody, KitLoadBody, QuantityBody, ReplaceBody, SendSelectedBody, SettingsPatch, VehicleBody
from app.scheduler import reschedule, start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    db.init_db()
    migrate()
    workspace.tick()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="VIN Parts Agent", lifespan=lifespan)
app.middleware("http")(access.guard)
app.include_router(workspace_router)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def invalid_input(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()
    ]})


@app.middleware("http")
async def track_client_activity(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        touch_client_activity()
    return await call_next(request)


@app.get("/")
@app.get("/requests")
@app.get("/requests/{entry}")
@app.get("/garage")
@app.get("/garage/{entry}")
@app.get("/lots")
@app.get("/lots/{entry}")
@app.get("/urgent")
@app.get("/orders")
@app.get("/orders/{entry}")
@app.get("/suppliers")
@app.get("/settings")
@app.get("/login")
def workspace_page() -> FileResponse:
    return FileResponse(WEB_DIR / "workspace.html")


@app.get("/classic")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/archive")
def archive_page() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/shutdown")
def api_shutdown(request: Request) -> dict:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "только localhost")
    threading.Timer(0.2, os._exit, args=(0,)).start()
    return {"ok": True}


@app.get("/api/state")
def state() -> dict:
    return snapshot()


@app.post("/api/settings")
def patch_settings(body: SettingsPatch) -> dict:
    settings = db.set_settings(body.model_dump(exclude_none=True))
    reschedule()
    db.add_event(
        f"Настройки: обучение={'вкл' if settings['training_mode'] else 'выкл'}, "
        f"лот {settings['send_hour']:02d}:{settings['send_minute']:02d}."
    )
    return snapshot()


@app.post("/api/ingest")
def ingest(body: IngestBody) -> dict:
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "пустой текст")
    result = ingest_text(text)
    return {**snapshot(), **result}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    from app.stt import transcribe_file

    suffix = Path(audio.filename or "speech.webm").suffix or ".webm"
    dest = DATA_DIR / "uploads"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"utterance{suffix}"
    path.write_bytes(await audio.read())
    try:
        text = transcribe_file(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    result = ingest_text(text)
    return {**snapshot(), **result}


@app.post("/api/items/{item_id}/confirm")
def api_confirm(item_id: int) -> dict:
    try:
        return {"item": confirm_item(item_id), **snapshot()}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/items/{item_id}/reject")
def api_reject(item_id: int) -> dict:
    try:
        return {"item": reject_item(item_id), **snapshot()}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/items/{item_id}/quantity")
def api_quantity(item_id: int, body: QuantityBody) -> dict:
    try:
        return {"item": set_item_quantity(item_id, body.quantity), **snapshot()}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/items/{item_id}/replace")
def api_replace(item_id: int, body: ReplaceBody) -> dict:
    try:
        return {"item": replace_item(item_id, body.description), **snapshot()}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/items/{item_id}/send-urgent")
def api_send_urgent(item_id: int) -> dict:
    try:
        result = send_urgent_item(item_id)
        return {**result, **snapshot()}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/lots/{lot_id}/confirm-all")
def api_confirm_all(lot_id: int) -> dict:
    confirm_all_in_lot(lot_id)
    return snapshot()


@app.post("/api/lots/{lot_id}/approve-send")
def api_approve_send(lot_id: int) -> dict:
    try:
        result = approve_and_send_lot(lot_id)
        return {**result, **snapshot()}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/lots/{lot_id}/send-selected")
def api_send_selected(lot_id: int, body: SendSelectedBody) -> dict:
    try:
        result = send_selected_items(lot_id, body.item_ids)
        return {**result, **snapshot()}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/lots/run-due")
def api_run_due() -> dict:
    result = process_due_lot(force=False)
    return {**result, **snapshot()}


@app.get("/api/vehicles")
def api_vehicles() -> dict:
    return snapshot()


@app.post("/api/vehicles")
def api_save_vehicle(body: VehicleBody) -> dict:
    from app.nlu import _is_vin

    vin = (body.vin or "").upper().replace(" ", "")
    if not _is_vin(vin):
        raise HTTPException(400, "VIN должен быть 17 знаков без I, O, Q")
    plate = garage.normalize_plate(body.plate) if body.plate else ""
    if body.plate.strip() and not plate:
        raise HTTPException(400, "некорректный госномер")
    make = (body.make or "").strip()
    make = garage.extract_make(make) or make
    row = garage.remember(
        vin,
        make,
        plate or "",
        model=body.model,
        year=body.year,
        engine=body.engine,
        body=body.body,
    ) or db.get_vehicle_by_vin(vin)
    label = garage.format_vehicle(row) if row else vin
    db.add_event(f"Гараж: {label} {garage.format_plate(row['plate']) if row and row.get('plate') else ''} · {vin}")
    return snapshot()


@app.delete("/api/vehicles/{vin}")
def api_delete_vehicle(vin: str, request: Request) -> dict:
    from app.workspace_api import Revision, archive_vehicle

    row = db.get_vehicle_by_vin(vin)
    if not row:
        raise HTTPException(404, "машина не найдена")
    archive_vehicle(request, row["vin"], Revision(revision=row["revision"]))
    return snapshot()


@app.get("/api/catalog")
def api_catalog() -> dict:
    from app.catalog import catalog_tree

    return catalog_tree()


@app.get("/api/kits")
def api_get_kit(kit_key: str = "grm", vin: str = "", make: str = "", model: str = "", engine: str = "") -> dict:
    from app.kits import KIT_TITLES, dump_kit_text, normalize_kit_key, parts_for, scope_for_load, scope_label

    title = (kit_key or "").strip() or "Комплект ГРМ"
    key = normalize_kit_key(title)
    vehicle = db.get_vehicle_by_vin(vin) if vin else None
    parts, scope = parts_for(key, vehicle, vin=vin, make=make, model=model, engine=engine)
    load_scope = scope or scope_for_load(vin=vin, make=make, model=model, engine=engine)
    return {
        "kit_key": key,
        "title": KIT_TITLES.get(key, title),
        "scope": load_scope,
        "label": scope_label(load_scope, vehicle),
        "parts": parts,
        "text": dump_kit_text(parts),
        "stored": bool(scope),
    }


@app.post("/api/kits")
def api_load_kit(body: KitLoadBody) -> dict:
    from app.kits import KIT_TITLES, dump_kit_text, normalize_kit_key, parse_kit_text, save_parts, scope_for_load, scope_label
    from app.nlu import _is_vin

    if not db.get_settings()["training_mode"]:
        raise HTTPException(403, "загрузка артикулов только в режиме обучения")
    title = (body.kit_key or "").strip() or "Комплект ГРМ"
    key = normalize_kit_key(title)
    vin = (body.vin or "").upper().replace(" ", "")
    if vin and not _is_vin(vin):
        raise HTTPException(400, "VIN должен быть 17 знаков без I, O, Q")
    make = (body.make or "").strip()
    make = garage.extract_make(make) or make
    if vin:
        garage.remember(vin, make or None, None, model=body.model, engine=body.engine)
    scope = scope_for_load(vin=vin, make=make, model=body.model, engine=body.engine)
    if not scope:
        raise HTTPException(400, "укажите VIN или марку")
    parts = parse_kit_text(body.text)
    if not parts:
        raise HTTPException(400, "вставьте артикулы, по одному на строку")
    saved = save_parts(key, scope, parts)
    vehicle = db.get_vehicle_by_vin(vin) if vin else None
    label = scope_label(scope, vehicle)
    shown = KIT_TITLES.get(key, title)
    db.add_event(f"Загружен {shown} для {label}: {len(saved)} позиций.")
    return {
        **snapshot(),
        "kit": {"kit_key": key, "scope": scope, "label": label, "parts": saved, "text": dump_kit_text(saved), "title": shown},
    }


@app.get("/api/archive")
def api_archive(date: str | None = None) -> dict:
    return archive_for_date(date)


@app.post("/api/archive/{request_id}/resend")
def api_archive_resend(request_id: int) -> dict:
    try:
        result = resend_request(request_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**snapshot(), **result, "archive": archive_for_date()}
