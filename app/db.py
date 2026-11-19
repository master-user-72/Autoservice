from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator, Optional

from app.config import DB_PATH

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

DEFAULT_SETTINGS = {
    "training_mode": "1",
    "send_hour": "16",
    "send_minute": "0",
}


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def utc_today() -> str:
    return datetime.now().date().isoformat()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL")
    return _conn


@contextmanager
def locked() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db() -> None:
    with locked() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_date TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                order_ref TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT
            );

            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                vin TEXT,
                clarifying_question TEXT,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                request_id INTEGER,
                lot_id INTEGER,
                description TEXT NOT NULL,
                article TEXT,
                name TEXT,
                supplier TEXT,
                delivery_days INTEGER,
                price REAL,
                currency TEXT DEFAULT 'RUB',
                original_required INTEGER NOT NULL DEFAULT 0,
                is_original INTEGER NOT NULL DEFAULT 0,
                urgent INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                warning TEXT,
                order_ref TEXT,
                FOREIGN KEY(request_id) REFERENCES requests(id),
                FOREIGN KEY(lot_id) REFERENCES lots(id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vin TEXT NOT NULL UNIQUE,
                make TEXT NOT NULL DEFAULT '',
                plate TEXT NOT NULL DEFAULT '',
                plate_digits TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                year TEXT NOT NULL DEFAULT '',
                engine TEXT NOT NULL DEFAULT '',
                engine_code TEXT NOT NULL DEFAULT '',
                displacement TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                drive TEXT NOT NULL DEFAULT '',
                fuel TEXT NOT NULL DEFAULT '',
                series TEXT NOT NULL DEFAULT '',
                plant TEXT NOT NULL DEFAULT '',
                wmi TEXT NOT NULL DEFAULT '',
                vin_prefix TEXT NOT NULL DEFAULT '',
                spec_key TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(plate);
            CREATE INDEX IF NOT EXISTS idx_vehicles_make ON vehicles(make);

            CREATE TABLE IF NOT EXISTS catalog_trims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                make TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                year TEXT NOT NULL DEFAULT '',
                engine TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'seed',
                UNIQUE(make, model, year, engine, body)
            );
            CREATE INDEX IF NOT EXISTS idx_catalog_make ON catalog_trims(make);

            CREATE TABLE IF NOT EXISTS learned_kits (
                kit_key TEXT NOT NULL,
                spec_key TEXT NOT NULL,
                parts_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (kit_key, spec_key)
            );

            CREATE TABLE IF NOT EXISTS learned_phrases (
                phrase_key TEXT PRIMARY KEY,
                items_json TEXT NOT NULL,
                kit_key TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            """
        )
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vehicles)").fetchall()}
        if cols and "plate_digits" not in cols:
            conn.execute("ALTER TABLE vehicles ADD COLUMN plate_digits TEXT NOT NULL DEFAULT ''")
        for name in (
            "model", "year", "engine", "engine_code", "displacement", "body",
            "drive", "fuel", "series", "plant", "wmi", "vin_prefix", "spec_key",
        ):
            if cols and name not in cols:
                conn.execute(f"ALTER TABLE vehicles ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
        item_cols = {row[1] for row in conn.execute("PRAGMA table_info(line_items)").fetchall()}
        if item_cols and "kit_key" not in item_cols:
            conn.execute("ALTER TABLE line_items ADD COLUMN kit_key TEXT NOT NULL DEFAULT ''")
        if item_cols and "kit_scope" not in item_cols:
            conn.execute("ALTER TABLE line_items ADD COLUMN kit_scope TEXT NOT NULL DEFAULT ''")
        if item_cols and "quantity" not in item_cols:
            conn.execute("ALTER TABLE line_items ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_spec ON vehicles(spec_key)")
        _migrate_learned_kits(conn)
        _backfill_vehicle_specs(conn)
        for row in conn.execute("SELECT vin, plate FROM vehicles").fetchall():
            digits = "".join(ch for ch in (row["plate"] or "") if ch.isdigit())
            conn.execute("UPDATE vehicles SET plate_digits = ? WHERE vin = ?", (digits, row["vin"]))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_digits ON vehicles(plate_digits)")
        from app.catalog import SEED_TRIMS

        seed_catalog_trims(SEED_TRIMS, conn)


def _migrate_learned_kits(conn: sqlite3.Connection) -> None:
    info = {row[1] for row in conn.execute("PRAGMA table_info(learned_kits)").fetchall()}
    if not info:
        return
    if "spec_key" in info and "vin" not in info:
        return
    from app.vin_decode import spec_key_from_vin

    rows = conn.execute("SELECT * FROM learned_kits").fetchall()
    conn.execute("ALTER TABLE learned_kits RENAME TO learned_kits_legacy")
    conn.execute(
        """
        CREATE TABLE learned_kits (
            kit_key TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            parts_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (kit_key, spec_key)
        )
        """
    )
    for row in rows:
        data = dict(row)
        spec = (data.get("spec_key") or "").strip() or spec_key_from_vin(data.get("vin") or "") or (data.get("vin") or "")
        if not spec:
            continue
        conn.execute(
            """
            INSERT INTO learned_kits(kit_key, spec_key, parts_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(kit_key, spec_key) DO UPDATE SET
                parts_json = CASE
                    WHEN excluded.updated_at >= learned_kits.updated_at THEN excluded.parts_json
                    ELSE learned_kits.parts_json
                END,
                updated_at = CASE
                    WHEN excluded.updated_at >= learned_kits.updated_at THEN excluded.updated_at
                    ELSE learned_kits.updated_at
                END
            """,
            (data["kit_key"], spec, data["parts_json"], data["updated_at"]),
        )
    conn.execute("DROP TABLE learned_kits_legacy")


def _backfill_vehicle_specs(conn: sqlite3.Connection) -> None:
    from app.vin_decode import decode_vin_local

    rows = conn.execute("SELECT vin, make, spec_key FROM vehicles").fetchall()
    for row in rows:
        if (row["spec_key"] or "").strip():
            continue
        decoded = decode_vin_local(row["vin"])
        if not decoded:
            continue
        conn.execute(
            """
            UPDATE vehicles SET
                make = CASE WHEN make = '' THEN ? ELSE make END,
                year = CASE WHEN year = '' THEN ? ELSE year END,
                wmi = ?,
                vin_prefix = ?,
                spec_key = ?,
                plant = CASE WHEN plant = '' THEN ? ELSE plant END
            WHERE vin = ?
            """,
            (
                decoded.get("make") or "",
                decoded.get("year") or "",
                decoded.get("wmi") or "",
                decoded.get("vin_prefix") or "",
                decoded.get("spec_key") or "",
                decoded.get("plant") or "",
                row["vin"],
            ),
        )


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def get_settings() -> dict[str, Any]:
    with locked() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    return {
        "training_mode": data.get("training_mode", "1") == "1",
        "send_hour": int(data.get("send_hour", "16")),
        "send_minute": int(data.get("send_minute", "0")),
    }


def set_settings(patch: dict[str, Any]) -> dict[str, Any]:
    mapping = {}
    if "training_mode" in patch and patch["training_mode"] is not None:
        mapping["training_mode"] = "1" if patch["training_mode"] else "0"
    if "send_hour" in patch and patch["send_hour"] is not None:
        mapping["send_hour"] = str(int(patch["send_hour"]))
    if "send_minute" in patch and patch["send_minute"] is not None:
        mapping["send_minute"] = str(int(patch["send_minute"]))
    with locked() as conn:
        for key, value in mapping.items():
            conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
    return get_settings()


def add_event(message: str, level: str = "info") -> None:
    with locked() as conn:
        conn.execute(
            "INSERT INTO events(created_at, level, message) VALUES (?, ?, ?)",
            (now_iso(), level, message),
        )


def list_events(limit: int = 80) -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_or_create_today_lot() -> dict[str, Any]:
    lot_date = utc_today()
    with locked() as conn:
        row = conn.execute("SELECT * FROM lots WHERE lot_date = ?", (lot_date,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT OR IGNORE INTO lots(lot_date, status, created_at) VALUES (?, ?, ?)",
                (lot_date, "collecting", now_iso()),
            )
            row = conn.execute("SELECT * FROM lots WHERE lot_date = ?", (lot_date,)).fetchone()
        return dict(row)


def get_lot(lot_id: int) -> Optional[dict[str, Any]]:
    with locked() as conn:
        row = conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,)).fetchone()
    return row_to_dict(row)


def update_lot(lot_id: int, **fields: Any) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [lot_id]
    with locked() as conn:
        conn.execute(f"UPDATE lots SET {assignments} WHERE id = ?", values)


def insert_request(raw_text: str, vin: Optional[str], clarifying_question: Optional[str], status: str) -> int:
    with locked() as conn:
        cur = conn.execute(
            """
            INSERT INTO requests(created_at, raw_text, vin, clarifying_question, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (now_iso(), raw_text, vin, clarifying_question, status),
        )
        return int(cur.lastrowid)


def insert_item(data: dict[str, Any]) -> int:
    cols = [
        "created_at",
        "request_id",
        "lot_id",
        "description",
        "article",
        "name",
        "supplier",
        "delivery_days",
        "price",
        "currency",
        "original_required",
        "is_original",
        "urgent",
        "status",
        "warning",
        "order_ref",
        "kit_key",
        "kit_scope",
        "quantity",
    ]
    payload = {
        "created_at": now_iso(),
        "currency": "RUB",
        "original_required": 0,
        "is_original": 0,
        "urgent": 0,
        "warning": None,
        "order_ref": None,
        "kit_key": "",
        "kit_scope": "",
        "quantity": 1,
        **data,
    }
    with locked() as conn:
        cur = conn.execute(
            f"INSERT INTO line_items({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [payload.get(c) for c in cols],
        )
        return int(cur.lastrowid)


def get_item(item_id: int) -> Optional[dict[str, Any]]:
    with locked() as conn:
        row = conn.execute("SELECT * FROM line_items WHERE id = ? AND status NOT LIKE 'workspace_%'", (item_id,)).fetchone()
    return row_to_dict(row)


def update_item(item_id: int, **fields: Any) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [item_id]
    with locked() as conn:
        conn.execute(
            f"UPDATE line_items SET {assignments} WHERE id = ? "
            "AND status NOT IN ('sent','failed','sending','outcome_unknown') AND status NOT LIKE 'workspace_%'",
            values,
        )


_ITEM_SELECT = """
SELECT line_items.*,
       requests.vin AS request_vin,
       COALESCE(vehicles.make, '') AS vehicle_make,
       COALESCE(vehicles.plate, '') AS vehicle_plate,
       COALESCE(vehicles.model, '') AS vehicle_model,
       COALESCE(vehicles.year, '') AS vehicle_year,
       COALESCE(vehicles.engine, '') AS vehicle_engine,
       COALESCE(vehicles.spec_key, '') AS vehicle_spec_key
FROM line_items
LEFT JOIN requests ON requests.id = line_items.request_id
LEFT JOIN vehicles ON vehicles.vin = requests.vin
"""


def list_items_for_lot(lot_id: int) -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            _ITEM_SELECT
            + " WHERE line_items.lot_id = ? AND line_items.urgent = 0"
            + " AND line_items.status != 'rejected' ORDER BY line_items.id",
            (lot_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_urgent_open() -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            _ITEM_SELECT
            + """
            WHERE line_items.urgent = 1 AND line_items.status NOT IN ('sent', 'rejected')
              AND NOT EXISTS (SELECT 1 FROM requests r WHERE r.id = line_items.request_id AND r.status LIKE 'workspace_%')
            ORDER BY line_items.id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_request(request_id: int) -> Optional[dict[str, Any]]:
    with locked() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    return row_to_dict(row)


def list_request_dates() -> list[str]:
    with locked() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(created_at, 1, 10) AS d FROM requests WHERE workspace=0 ORDER BY d DESC"
        ).fetchall()
    return [str(r["d"]) for r in rows if r["d"]]


def list_requests_on_date(day: str) -> list[dict[str, Any]]:
    day = (day or utc_today())[:10]
    with locked() as conn:
        reqs = conn.execute(
            """
            SELECT requests.*,
                   COALESCE(vehicles.make, '') AS vehicle_make,
                   COALESCE(vehicles.plate, '') AS vehicle_plate,
                   COALESCE(vehicles.model, '') AS vehicle_model,
                   COALESCE(vehicles.year, '') AS vehicle_year,
                   COALESCE(vehicles.engine, '') AS vehicle_engine
            FROM requests
            LEFT JOIN vehicles ON vehicles.vin = requests.vin
            WHERE requests.workspace=0 AND substr(requests.created_at, 1, 10) = ?
            ORDER BY requests.id DESC
            """,
            (day,),
        ).fetchall()
        out = []
        for req in reqs:
            row = dict(req)
            items = conn.execute(
                "SELECT * FROM line_items WHERE request_id = ? ORDER BY id",
                (req["id"],),
            ).fetchall()
            row["items"] = [dict(i) for i in items]
            out.append(row)
    return out


def list_recent_items(limit: int = 40) -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            "SELECT * FROM line_items ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_recent_lots(limit: int = 14) -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            "SELECT * FROM lots ORDER BY lot_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_vehicle_vin() -> Optional[str]:
    with locked() as conn:
        row = conn.execute(
            """
            SELECT vin FROM requests
            WHERE vin IS NOT NULL AND vin != '' AND status = 'matched'
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    return row["vin"] if row else None


def latest_open_question() -> Optional[str]:
    with locked() as conn:
        row = conn.execute(
            """
            SELECT clarifying_question, status FROM requests WHERE workspace=0
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    if row and row["status"] == "needs_clarification":
        return row["clarifying_question"]
    return None


def list_vehicles(query: str = "") -> list[dict[str, Any]]:
    q = (query or "").strip()
    with locked() as conn:
        if q:
            like = f"%{q}%"
            digits = "".join(ch for ch in q if ch.isdigit())
            digits = digits if len(digits) >= 3 else ""
            rows = conn.execute(
                """
                SELECT * FROM vehicles
                WHERE archived=0 AND (vin LIKE ? OR make LIKE ? OR plate LIKE ?
                   OR model LIKE ? OR engine LIKE ? OR year LIKE ? OR spec_key LIKE ?
                   OR (? != '' AND instr(plate_digits, ?) > 0))
                ORDER BY make, model, plate
                """,
                (like.upper(), like, like.upper(), like, like, like, like.upper(), digits, digits),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM vehicles WHERE archived=0 ORDER BY make, model, plate").fetchall()
    return [dict(r) for r in rows]


def get_vehicle_by_vin(vin: str) -> Optional[dict[str, Any]]:
    with locked() as conn:
        row = conn.execute("SELECT * FROM vehicles WHERE vin = ?", (vin.upper(),)).fetchone()
    return row_to_dict(row)


def get_vehicle_by_plate(plate: str) -> Optional[dict[str, Any]]:
    with locked() as conn:
        row = conn.execute("SELECT * FROM vehicles WHERE plate = ? AND archived=0", (plate.upper(),)).fetchone()
    return row_to_dict(row)


def find_vehicles_by_digits(digits: str) -> list[dict[str, Any]]:
    digits = "".join(ch for ch in (digits or "") if ch.isdigit())
    if len(digits) < 3:
        return []
    with locked() as conn:
        rows = conn.execute(
            """
            SELECT * FROM vehicles
            WHERE archived=0 AND plate_digits != '' AND instr(plate_digits, ?) > 0
            ORDER BY make, plate
            """,
            (digits,),
        ).fetchall()
    hits = [dict(r) for r in rows]
    if hits:
        return hits
    with locked() as conn:
        rows = conn.execute("SELECT * FROM vehicles WHERE archived=0 AND plate != ''").fetchall()
    out = []
    for row in rows:
        pdata = "".join(ch for ch in (row["plate"] or "") if ch.isdigit())
        if digits in pdata:
            out.append(dict(row))
    return out


def find_vehicles_by_make(make: str) -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            "SELECT * FROM vehicles WHERE archived=0 AND lower(make) = lower(?) ORDER BY plate",
            (make.strip(),),
        ).fetchall()
    return [dict(r) for r in rows]


VEHICLE_SPEC_FIELDS = (
    "make", "model", "year", "engine", "engine_code", "displacement", "body",
    "drive", "fuel", "series", "plant", "wmi", "vin_prefix", "spec_key",
)


def upsert_vehicle(*, vin: str, make: str = "", plate: str = "", **spec: Any) -> dict[str, Any]:
    vin = vin.upper().strip()
    plate = (plate or "").upper().strip()
    plate_digits = "".join(ch for ch in plate if ch.isdigit())
    values = {key: str(spec.get(key) or "").strip() for key in VEHICLE_SPEC_FIELDS}
    if make:
        values["make"] = make.strip()
    now = now_iso()
    assignments = ", ".join(
        f"{key} = CASE WHEN ? != '' THEN ? ELSE {key} END" for key in VEHICLE_SPEC_FIELDS
    )
    update_params: list[Any] = []
    for key in VEHICLE_SPEC_FIELDS:
        update_params.extend([values[key], values[key]])
    with locked() as conn:
        existing = conn.execute("SELECT * FROM vehicles WHERE vin = ?", (vin,)).fetchone()
        if existing:
            if any(values[key] and values[key] != existing[key] for key in VEHICLE_SPEC_FIELDS):
                from app.workspace import invalidate_vehicle

                invalidate_vehicle(conn, vin)
                conn.execute("UPDATE vehicles SET revision=revision+1 WHERE vin=?", (vin,))
            conn.execute(
                f"""
                UPDATE vehicles
                SET {assignments},
                    plate = CASE WHEN ? != '' THEN ? ELSE plate END,
                    plate_digits = CASE WHEN ? != '' THEN ? ELSE plate_digits END,
                    updated_at = ?
                WHERE vin = ?
                """,
                (*update_params, plate, plate, plate_digits, plate_digits, now, vin),
            )
        else:
            cols = ["vin", "plate", "plate_digits", "created_at", "updated_at", *VEHICLE_SPEC_FIELDS]
            payload = {
                "vin": vin,
                "plate": plate,
                "plate_digits": plate_digits,
                "created_at": now,
                "updated_at": now,
                **values,
            }
            conn.execute(
                f"INSERT INTO vehicles({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [payload[c] for c in cols],
            )
        row = conn.execute("SELECT * FROM vehicles WHERE vin = ?", (vin,)).fetchone()
    return dict(row)


def get_learned_kit_parts(kit_key: str, spec_key: str) -> Optional[list[Any]]:
    spec_key = (spec_key or "").strip()
    if not spec_key:
        return None
    with locked() as conn:
        row = conn.execute(
            "SELECT parts_json FROM learned_kits WHERE kit_key = ? AND spec_key = ?",
            (kit_key, spec_key),
        ).fetchone()
    if row is None:
        return None
    try:
        data = json.loads(row["parts_json"] or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def set_learned_kit_parts(kit_key: str, spec_key: str, parts: list[Any]) -> None:
    spec_key = (spec_key or "").strip()
    if not spec_key:
        return
    payload = json.dumps(parts, ensure_ascii=False)
    with locked() as conn:
        conn.execute(
            """
            INSERT INTO learned_kits(kit_key, spec_key, parts_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(kit_key, spec_key) DO UPDATE SET
                parts_json = excluded.parts_json,
                updated_at = excluded.updated_at
            """,
            (kit_key, spec_key, payload, now_iso()),
        )


def list_items_for_request(request_id: int) -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            "SELECT * FROM line_items WHERE request_id = ? ORDER BY id",
            (request_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_learned_phrase(phrase_key: str) -> Optional[dict[str, Any]]:
    key = (phrase_key or "").strip()
    if not key:
        return None
    with locked() as conn:
        row = conn.execute(
            "SELECT phrase_key, items_json, kit_key, updated_at FROM learned_phrases WHERE phrase_key = ?",
            (key,),
        ).fetchone()
    if row is None:
        return None
    try:
        items = json.loads(row["items_json"] or "[]")
    except json.JSONDecodeError:
        items = []
    return {
        "phrase_key": row["phrase_key"],
        "items": items if isinstance(items, list) else [],
        "kit_key": row["kit_key"] or "",
        "updated_at": row["updated_at"],
    }


def set_learned_phrase(phrase_key: str, items: list[Any], kit_key: str = "") -> None:
    key = (phrase_key or "").strip()
    if not key:
        return
    payload = json.dumps(items, ensure_ascii=False)
    with locked() as conn:
        conn.execute(
            """
            INSERT INTO learned_phrases(phrase_key, items_json, kit_key, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(phrase_key) DO UPDATE SET
                items_json = excluded.items_json,
                kit_key = excluded.kit_key,
                updated_at = excluded.updated_at
            """,
            (key, payload, (kit_key or "").strip(), now_iso()),
        )


def count_vehicles_by_spec(spec_key: str) -> int:
    spec_key = (spec_key or "").strip()
    if not spec_key:
        return 0
    with locked() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM vehicles WHERE spec_key = ?",
            (spec_key,),
        ).fetchone()
    return int(row["n"] if row else 0)


def seed_catalog_trims(rows: list[tuple], conn: sqlite3.Connection | None = None) -> None:
    sql = """
        INSERT OR IGNORE INTO catalog_trims(make, model, year, engine, body, source)
        VALUES (?, ?, ?, ?, ?, 'seed')
    """
    if conn is not None:
        conn.executemany(sql, rows)
        return
    with locked() as locked_conn:
        locked_conn.executemany(sql, rows)


def list_catalog_trims() -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            """
            SELECT make, model, year, engine, body, source
            FROM catalog_trims
            ORDER BY make COLLATE NOCASE, model COLLATE NOCASE, year, engine, body
            """
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_catalog_trim(
    *,
    make: str,
    model: str = "",
    year: str = "",
    engine: str = "",
    body: str = "",
    source: str = "user",
) -> None:
    make = (make or "").strip()
    if not make:
        return
    with locked() as conn:
        conn.execute(
            """
            INSERT INTO catalog_trims(make, model, year, engine, body, source)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(make, model, year, engine, body) DO UPDATE SET
                source = CASE
                    WHEN catalog_trims.source = 'seed' THEN catalog_trims.source
                    ELSE excluded.source
                END
            """,
            (make, (model or "").strip(), (year or "").strip(), (engine or "").strip(), (body or "").strip(), source),
        )


def delete_vehicle(vin: str) -> bool:
    with locked() as conn:
        cur = conn.execute("DELETE FROM vehicles WHERE vin = ?", (vin.upper(),))
        return cur.rowcount > 0
