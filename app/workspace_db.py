"""Additive schema for the workspace in the existing SQLite database."""

from contextlib import contextmanager

from app import db

VERSION = 2

COLUMNS = {
    "requests": {
        "workspace": "INTEGER NOT NULL DEFAULT 0",
        "revision": "INTEGER NOT NULL DEFAULT 1",
        "author": "TEXT NOT NULL DEFAULT ''",
    },
    "line_items": {
        "revision": "INTEGER NOT NULL DEFAULT 1",
        "workspace_lot": "TEXT",
        "search_result": "TEXT",
        "selection": "TEXT",
        "manual_basis": "TEXT",
        "conditions_delta": "TEXT",
    },
    "workspace_sources": {
        "revision": "INTEGER NOT NULL DEFAULT 1",
    },
    "workspace_orders": {
        "dispatch_scenario": "TEXT NOT NULL DEFAULT 'normal'",
    },
    "vehicles": {
        "generation": "TEXT NOT NULL DEFAULT ''",
        "archived": "INTEGER NOT NULL DEFAULT 0",
        "revision": "INTEGER NOT NULL DEFAULT 1",
    },
}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS workspace_lots (
        day TEXT PRIMARY KEY, cutoff TEXT NOT NULL, closed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS workspace_orders (
        id TEXT PRIMARY KEY, supplier TEXT NOT NULL, kind TEXT NOT NULL,
        lot_day TEXT REFERENCES workspace_lots(day), delivery_key TEXT,
        channel TEXT NOT NULL, status TEXT NOT NULL, supplier_ref TEXT,
        author TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(supplier, supplier_ref)
    )""",
    """CREATE TABLE IF NOT EXISTS workspace_order_items (
        order_id TEXT NOT NULL REFERENCES workspace_orders(id),
        item_id INTEGER NOT NULL UNIQUE REFERENCES line_items(id),
        snapshot TEXT NOT NULL, PRIMARY KEY(order_id, item_id)
    )""",
    """CREATE TABLE IF NOT EXISTS workspace_journal (
        id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL,
        entity TEXT NOT NULL, entity_id TEXT NOT NULL,
        action TEXT NOT NULL, detail TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS workspace_preferences (
        owner TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
        PRIMARY KEY(owner, key)
    )""",
    """CREATE TABLE IF NOT EXISTS workspace_sources (
        name TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
        scenario TEXT NOT NULL DEFAULT 'normal', checked_at TEXT, last_success TEXT,
        last_status TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS workspace_demo_receipts (
        order_id TEXT PRIMARY KEY REFERENCES workspace_orders(id), ref TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS workspace_reviews (
        id TEXT PRIMARY KEY, actor TEXT NOT NULL, payload TEXT NOT NULL,
        expires TEXT NOT NULL, result TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS workspace_orders_date ON workspace_orders(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS workspace_orders_status ON workspace_orders(status, supplier)",
    "CREATE INDEX IF NOT EXISTS workspace_journal_object ON workspace_journal(entity, entity_id, id)",
)


@contextmanager
def transaction():
    with db.locked() as conn:
        conn.execute("BEGIN IMMEDIATE")
        yield conn


def migrate():
    with transaction() as conn:
        for statement in SCHEMA:
            conn.execute(statement)
        for table, columns in COLUMNS.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        conn.execute("CREATE INDEX IF NOT EXISTS workspace_items_lot ON line_items(workspace_lot, status)")
