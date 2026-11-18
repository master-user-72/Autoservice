from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class VehicleInfo:
    vin: str
    title: str
    notes: str = ""


@dataclass
class Offer:
    article: str
    name: str
    delivery_days: int
    price: float
    currency: str = "RUB"
    is_original: bool = False
    supplier: str = ""
    warning: Optional[str] = None
    search_url: Optional[str] = None
    city: str = "Тюмень"
    quantity: int = 1


def offer_quantity(offer: Offer) -> int:
    return max(1, min(99, int(getattr(offer, "quantity", 1) or 1)))


def order_line_details(offers: list[Offer]) -> list[dict]:
    return [
        {
            "article": offer.article,
            "name": offer.name,
            "quantity": offer_quantity(offer),
            "price": offer.price,
            "supplier": offer.supplier,
        }
        for offer in offers
    ]


@dataclass
class OrderResult:
    ok: bool
    order_ref: Optional[str] = None
    error: Optional[str] = None
    details: dict = field(default_factory=dict)


class SupplierAdapter(Protocol):
    name: str

    def search_by_vin(self, vin: str) -> VehicleInfo: ...

    def match_items(self, description: str, original_required: bool) -> list[Offer]: ...

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]: ...

    def place_order(self, offers: list[Offer]) -> OrderResult: ...


def is_stock_offer(offer: Offer) -> bool:
    """Есть живая цена в каталоге."""
    if not offer:
        return False
    if (offer.article or "").upper() == "ERR":
        return False
    return bool(offer.price and offer.price > 0)


def is_usable_offer(offer: Offer) -> bool:
    """Позицию можно взять у поставщика: цена или ссылка на поиск в кабинете."""
    if not offer:
        return False
    if (offer.article or "").upper() == "ERR":
        return False
    warning = (offer.warning or "").lower()
    if "ошибк" in warning and not (offer.price and offer.price > 0):
        return False
    if offer.price and offer.price > 0:
        return True
    if offer.search_url or (offer.article or "").strip():
        return True
    return bool(offer.supplier)


def pick_best_offer(offers: list[Offer]) -> Offer | None:
    """Сначала ниже цена, при равенстве — короче срок. Без цены берём кабинетный поиск (Росско раньше)."""
    usable = [o for o in offers if is_usable_offer(o)]
    if not usable:
        return None

    def key(o: Offer) -> tuple:
        priced = 0 if (o.price and o.price > 0) else 1
        price = float(o.price) if o.price and o.price > 0 else 10**12
        days = int(o.delivery_days or 99)
        rossko_first = 0 if (o.supplier or "") == "Росско" else 1
        return (priced, price, days, rossko_first, o.supplier or "")

    return min(usable, key=key)


def offer_compare_note(picked: Offer, offers: list[Offer]) -> str | None:
    others = [
        o for o in offers
        if is_stock_offer(o) and (o.supplier or "") != (picked.supplier or "")
    ]
    if not others:
        return picked.warning
    bits = [f"{o.supplier}: {int(o.price)} ₽ / {o.delivery_days} дн." for o in others[:3]]
    extra = "выбрано по цене и сроку; также " + "; ".join(bits)
    return f"{picked.warning}; {extra}" if picked.warning else extra


def pick_same_delivery(offers: list[Offer]) -> list[Offer]:
    if not offers:
        return []
    counts: dict[int, int] = {}
    for offer in offers:
        counts[offer.delivery_days] = counts.get(offer.delivery_days, 0) + 1
    target = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    kept = [o for o in offers if o.delivery_days == target]
    dropped = [o for o in offers if o.delivery_days != target]
    if dropped:
        warning = f"срок выровнен на {target} дн.; исключены позиции с другим сроком"
        for offer in kept:
            extra = warning if offer.warning else warning
            offer.warning = f"{offer.warning}; {warning}" if offer.warning else extra
    return kept
