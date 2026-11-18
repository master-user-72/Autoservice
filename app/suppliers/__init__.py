from __future__ import annotations

from app.config import SUPPLIER_ADAPTER
from app.suppliers.base import SupplierAdapter
from app.suppliers.composite import CompositeSupplier
from app.suppliers.emex import EmexSupplier
from app.suppliers.exist import ExistSupplier
from app.suppliers.mock import MockSupplier
from app.suppliers.partkom import PartKomSupplier
from app.suppliers.playwright_base import PlaywrightSupplier
from app.suppliers.rossko import RosskoSupplier

_adapter: SupplierAdapter | None = None


def get_adapter() -> SupplierAdapter:
    global _adapter
    if _adapter is None:
        key = SUPPLIER_ADAPTER
        if key in {"live", "composite", "all", ""}:
            _adapter = CompositeSupplier()
        elif key == "rossko":
            _adapter = RosskoSupplier()
        elif key in {"partkom", "part-kom"}:
            _adapter = PartKomSupplier()
        elif key == "emex":
            _adapter = EmexSupplier()
        elif key == "exist":
            _adapter = ExistSupplier()
        elif key in {"playwright", "browser", "web"}:
            _adapter = PlaywrightSupplier()
        else:
            _adapter = MockSupplier()
    return _adapter
