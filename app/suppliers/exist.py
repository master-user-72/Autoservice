from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from app.config import CITY, DATA_DIR, EXIST_BASE, EXIST_OFFICE, EXIST_PASSWORD, EXIST_USER
from app.suppliers.base import Offer, OrderResult, VehicleInfo, pick_same_delivery
from app.suppliers.base import order_line_details
from app.suppliers.browser import run_playwright, visit_offers_for_order

NAME = "Exist"


class ExistSupplier:
    name = NAME
    base = EXIST_BASE
    city = CITY

    def search_url(self, text: str) -> str:
        return f"{self.base}/Price/?pcode={quote(text.strip())}"

    def vin_url(self, vin: str) -> str:
        return f"{self.base}/Catalog/Global/Cars?vin={quote(vin)}"

    def search_by_vin(self, vin: str) -> VehicleInfo:
        return VehicleInfo(
            vin=vin,
            title="Авто по VIN (Exist)",
            notes=f"{self.city}, офис {EXIST_OFFICE} · {self.vin_url(vin)}",
        )

    def match_items(self, description: str, original_required: bool) -> list[Offer]:
        warning = f"нужны EXIST_USER/PASSWORD (кабинет {self.base}) для цены. Офис: {EXIST_OFFICE}"
        if EXIST_USER and EXIST_PASSWORD:
            warning = f"поиск в кабинете Exist, офис {EXIST_OFFICE}"
        return [
            Offer(
                article="",
                name=description.strip() or "Позиция по описанию",
                delivery_days=2,
                price=0.0,
                is_original=original_required,
                supplier=self.name,
                warning=warning,
                search_url=self.search_url(description),
                city=self.city,
            )
        ]

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]:
        return pick_same_delivery(offers)

    def place_order(self, offers: list[Offer]) -> OrderResult:
        if not offers:
            return OrderResult(ok=False, error="пустой список Exist")
        start = offers[0].search_url or self.search_url(offers[0].article)
        state = DATA_DIR / "exist_state.json"

        def steps(page) -> None:
            visit_offers_for_order(page, offers, self.search_url)

        err = run_playwright(
            start,
            state,
            steps,
            user=EXIST_USER,
            password=EXIST_PASSWORD,
            headless=False,
        )
        if err:
            return OrderResult(ok=False, error=f"Exist ({self.city}): {err}")
        ref = f"EXIST-DRAFT-{datetime.now().strftime('%Y%m%d-%H%M')}"
        return OrderResult(
            ok=True,
            order_ref=ref,
            details={
                "city": self.city,
                "office": EXIST_OFFICE,
                "payment": "postpay",
                "articles": [o.article for o in offers],
                "lines": order_line_details(offers),
                "url": self.base,
            },
        )
