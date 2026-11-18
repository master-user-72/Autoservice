from __future__ import annotations

import hashlib
import random
from datetime import datetime

from app.suppliers.base import Offer, OrderResult, VehicleInfo, order_line_details, pick_same_delivery

CATALOG: list[dict] = [
    {
        "keywords": ("колодк", "передн", "тормоз"),
        "article": "BRK-F-4410",
        "name": "Колодки тормозные передние",
        "delivery_days": 2,
        "price": 4680.0,
        "is_original": False,
    },
    {
        "keywords": ("колодк", "передн", "оригинал"),
        "article": "OEM-BRK-F-4410",
        "name": "Колодки тормозные передние оригинал",
        "delivery_days": 2,
        "price": 8920.0,
        "is_original": True,
    },
    {
        "keywords": ("колодк", "задн"),
        "article": "BRK-R-2204",
        "name": "Колодки тормозные задние",
        "delivery_days": 2,
        "price": 3920.0,
        "is_original": False,
    },
    {
        "keywords": ("фильтр масл", "масляный фильтр", "фильтр масла"),
        "article": "FLT-OIL-118",
        "name": "Фильтр масляный",
        "delivery_days": 2,
        "price": 740.0,
        "is_original": False,
    },
    {
        "keywords": ("фильтр воздуш", "воздушный фильтр"),
        "article": "FLT-AIR-332",
        "name": "Фильтр воздушный",
        "delivery_days": 2,
        "price": 980.0,
        "is_original": False,
    },
    {
        "keywords": ("фильтр салон", "салонный"),
        "article": "FLT-CAB-019",
        "name": "Фильтр салонный",
        "delivery_days": 2,
        "price": 860.0,
        "is_original": False,
    },
    {
        "keywords": ("свеч", "зажиган"),
        "article": "SPK-IR-04",
        "name": "Свечи зажигания (комплект)",
        "delivery_days": 2,
        "price": 2140.0,
        "is_original": False,
    },
    {
        "keywords": ("ремень грм", "грм"),
        "article": "BLT-TIM-77",
        "name": "Ремень ГРМ",
        "delivery_days": 2,
        "price": 3560.0,
        "is_original": False,
    },
    {
        "keywords": ("помп", "водяной насос"),
        "article": "PMP-W-12",
        "name": "Помпа водяная",
        "delivery_days": 2,
        "price": 4890.0,
        "is_original": False,
    },
    {
        "keywords": ("амортизатор перед", "стойк перед"),
        "article": "SHK-F-90",
        "name": "Амортизатор передний",
        "delivery_days": 7,
        "price": 6720.0,
        "is_original": False,
    },
    {
        "keywords": ("диск тормозн перед", "тормозной диск"),
        "article": "DSC-F-18",
        "name": "Диск тормозной передний",
        "delivery_days": 2,
        "price": 5340.0,
        "is_original": False,
    },
    {
        "keywords": ("масло мотор", "моторное масло"),
        "article": "OIL-5W30-4",
        "name": "Масло моторное 5W-30 4л",
        "delivery_days": 2,
        "price": 3180.0,
        "is_original": False,
    },
    {
        "keywords": ("аккумулятор", "батарея"),
        "article": "BAT-74AH",
        "name": "Аккумулятор 74Ah",
        "delivery_days": 2,
        "price": 11200.0,
        "is_original": False,
    },
    {
        "keywords": ("дворник", "щетк стекло"),
        "article": "WPR-24-18",
        "name": "Щётки стеклоочистителя",
        "delivery_days": 2,
        "price": 890.0,
        "is_original": False,
    },
]

_VEHICLE_HINTS = [
    ("Toyota Camry 2.5", "бензин, автомат"),
    ("Hyundai Tucson 2.0", "полный привод"),
    ("Kia Sportage 2.0", "бензин"),
    ("Volkswagen Tiguan 2.0 TSI", "робот DSG"),
    ("Skoda Octavia 1.8 TSI", "передний привод"),
    ("Lada Vesta 1.6", "механика"),
]


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


class MockSupplier:
    name = "Демо-поставщик"

    def search_by_vin(self, vin: str) -> VehicleInfo:
        digest = hashlib.sha256(vin.encode("utf-8")).digest()
        idx = digest[0] % len(_VEHICLE_HINTS)
        title, notes = _VEHICLE_HINTS[idx]
        return VehicleInfo(vin=vin, title=title, notes=notes)

    def match_items(self, description: str, original_required: bool) -> list[Offer]:
        query = _norm(description)
        scored: list[tuple[int, dict]] = []
        for row in CATALOG:
            hay = " ".join(row["keywords"]) + " " + _norm(row["name"])
            kw_hits = sum(1 for kw in row["keywords"] if kw in query)
            token_hits = sum(1 for token in query.split() if len(token) > 3 and token in hay)
            hits = kw_hits * 4 + token_hits
            if original_required and not row["is_original"]:
                hits -= 2
            if original_required and row["is_original"]:
                hits += 5
            if kw_hits or token_hits >= 2:
                scored.append((hits, row))
        scored.sort(key=lambda x: (-x[0], x[1]["price"]))
        offers: list[Offer] = []
        for _, row in scored[:3]:
            offers.append(
                Offer(
                    article=row["article"],
                    name=row["name"],
                    delivery_days=row["delivery_days"],
                    price=row["price"],
                    is_original=row["is_original"],
                    supplier=self.name,
                )
            )
        if not offers:
            offers.append(
                Offer(
                    article=f"ASK-{int(hashlib.sha256(query.encode()).hexdigest()[:4], 16):04d}",
                    name=description.strip().capitalize() or "Позиция по описанию",
                    delivery_days=2,
                    price=0.0,
                    is_original=original_required,
                    supplier=self.name,
                    warning="точного совпадения в демо-каталоге нет, оставлено как заявка",
                )
            )
        if original_required:
            originals = [o for o in offers if o.is_original]
            if originals:
                return originals
            offers[0].warning = "оригинал запрошен, в демо-каталоге показан ближайший аналог"
        return offers

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]:
        return pick_same_delivery(offers)

    def place_order(self, offers: list[Offer]) -> OrderResult:
        if not offers:
            return OrderResult(ok=False, error="пустой список позиций")
        stamp = datetime.now().strftime("%Y%m%d")
        suffix = random.randint(1000, 9999)
        ref = f"MOCK-{stamp}-{suffix}"
        lines = order_line_details(offers)
        total = sum(float(line["price"] or 0) * int(line["quantity"] or 1) for line in lines)
        pieces = sum(int(line["quantity"] or 1) for line in lines)
        return OrderResult(
            ok=True,
            order_ref=ref,
            details={"count": len(offers), "pieces": pieces, "lines": lines, "total": total, "payment": "postpay"},
        )
