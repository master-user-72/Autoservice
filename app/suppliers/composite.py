from __future__ import annotations

from collections import defaultdict

from app.config import CITY, EMEX_BASE, EXIST_BASE, PARTKOM_BASE, ROSSKO_BASE
from app.suppliers.base import Offer, OrderResult, VehicleInfo, pick_same_delivery
from app.suppliers.emex import EmexSupplier, NAME as EMEX_NAME
from app.suppliers.exist import ExistSupplier, NAME as EXIST_NAME
from app.suppliers.partkom import PartKomSupplier, NAME as PARTKOM_NAME
from app.suppliers.rossko import RosskoSupplier, NAME as ROSSKO_NAME


class CompositeSupplier:
    name = f"Росско + ПартКом + Emex + Exist ({CITY})"

    def __init__(self) -> None:
        self.rossko = RosskoSupplier()
        self.partkom = PartKomSupplier()
        self.emex = EmexSupplier()
        self.exist = ExistSupplier()
        self.adapters = [self.rossko, self.partkom, self.emex, self.exist]
        self.by_name = {a.name: a for a in self.adapters}

    def directory(self) -> list[dict[str, str]]:
        return [
            {"name": ROSSKO_NAME, "url": ROSSKO_BASE, "city": CITY, "role": "автозапчасти, OEM по VIN"},
            {"name": PARTKOM_NAME, "url": PARTKOM_BASE, "city": CITY, "role": "автозапчасти, VIN-каталог, ПВЗ Малышева"},
            {"name": EMEX_NAME, "url": EMEX_BASE, "city": CITY, "role": "автозапчасти, SOAP-поиск по артикулу"},
            {"name": EXIST_NAME, "url": EXIST_BASE, "city": CITY, "role": "автозапчасти, каталог и офис в городе"},
        ]

    def search_by_vin(self, vin: str) -> VehicleInfo:
        return VehicleInfo(
            vin=vin,
            title="Подбор по VIN, город получения Тюмень",
            notes=(
                f"Росско {ROSSKO_BASE} · ПартКом {PARTKOM_BASE} · "
                f"Emex {EMEX_BASE} · Exist {EXIST_BASE}"
            ),
        )

    def match_items(self, description: str, original_required: bool) -> list[Offer]:
        collected: list[Offer] = []
        for adapter in self.adapters:
            try:
                collected.extend(adapter.match_items(description, original_required)[:4])
            except Exception as exc:  # noqa: BLE001
                collected.append(
                    Offer(
                        article="ERR",
                        name=description,
                        delivery_days=2,
                        price=0.0,
                        supplier=adapter.name,
                        warning=str(exc),
                        city=CITY,
                    )
                )
        collected.sort(key=lambda o: (o.price <= 0, o.price, o.delivery_days))
        return collected

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]:
        return pick_same_delivery(offers)

    def place_order(self, offers: list[Offer]) -> OrderResult:
        groups: dict[str, list[Offer]] = defaultdict(list)
        for offer in offers:
            groups[offer.supplier or self.name].append(offer)
        by_supplier: dict[str, str | None] = {}
        refs: list[str] = []
        errors: list[str] = []
        for name, group in groups.items():
            adapter = self.by_name.get(name)
            if adapter is None:
                by_supplier[name] = None
                errors.append(f"нет адаптера «{name}»")
                continue
            result = adapter.place_order(group)
            if result.ok and result.order_ref:
                by_supplier[name] = result.order_ref
                refs.append(result.order_ref)
            else:
                by_supplier[name] = None
                errors.append(result.error or name)
        ok = bool(refs)
        return OrderResult(
            ok=ok,
            order_ref="+".join(refs) if refs else None,
            error="; ".join(errors) if errors else None,
            details={"by_supplier": by_supplier, "city": CITY, "payment": "postpay"},
        )
