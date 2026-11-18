from __future__ import annotations

import base64
from datetime import datetime
from urllib.parse import quote

from app.config import (
    CITY,
    DATA_DIR,
    PARTKOM_API,
    PARTKOM_BASE,
    PARTKOM_PASSWORD,
    PARTKOM_PICKUP,
    PARTKOM_USER,
)
from app.suppliers.base import Offer, OrderResult, VehicleInfo, pick_same_delivery
from app.suppliers.base import order_line_details
from app.suppliers.browser import run_playwright, visit_offers_for_order
from app.suppliers.http_util import client

NAME = "ПартКом"


class PartKomSupplier:
    name = NAME
    base = PARTKOM_BASE
    city = CITY

    def search_url(self, text: str) -> str:
        return f"{self.base}/search?text={quote(text)}"

    def vin_url(self, vin: str) -> str:
        return f"{self.base}/catalog-vin"

    def search_by_vin(self, vin: str) -> VehicleInfo:
        return VehicleInfo(
            vin=vin,
            title="Авто по VIN (ПартКом)",
            notes=f"{self.city}, {PARTKOM_PICKUP} · {self.vin_url(vin)}",
        )

    def match_items(self, description: str, original_required: bool) -> list[Offer]:
        offers = self._api_search(description, original_required)
        if offers:
            return offers
        return [
            Offer(
                article="",
                name=description.strip() or "Позиция по описанию",
                delivery_days=2,
                price=0.0,
                is_original=original_required,
                supplier=self.name,
                warning=f"нужен PARTKOM_USER/PASSWORD (B2B API) или кабинет. ПВЗ: {PARTKOM_PICKUP}",
                search_url=self.search_url(description),
                city=self.city,
            )
        ]

    def _api_search(self, text: str, original_required: bool) -> list[Offer]:
        if not (PARTKOM_USER and PARTKOM_PASSWORD):
            return []
        token = base64.b64encode(f"{PARTKOM_USER}:{PARTKOM_PASSWORD}".encode()).decode()
        headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
        number = text.replace(" ", "")
        try:
            with client() as http:
                response = http.get(
                    f"{PARTKOM_API}/search/parts",
                    params={"number": number, "find_substitutes": "false" if original_required else "true"},
                    headers=headers,
                    timeout=20.0,
                )
                if response.status_code >= 400:
                    return []
                payload = response.json()
        except Exception:
            return []
        rows = payload if isinstance(payload, list) else payload.get("data") or payload.get("parts") or []
        offers: list[Offer] = []
        for row in rows[:10]:
            if not isinstance(row, dict):
                continue
            article = str(row.get("number") or row.get("article") or row.get("part_number") or "")
            name = str(row.get("name") or row.get("description") or article)
            brand = str(row.get("brand") or row.get("maker") or "")
            try:
                price = float(row.get("price") or row.get("cost") or 0)
            except (TypeError, ValueError):
                price = 0.0
            try:
                days = int(row.get("delivery") or row.get("delivery_days") or row.get("min_days") or 2)
            except (TypeError, ValueError):
                days = 2
            original = bool(row.get("original")) or "оригинал" in name.lower() or "oem" in brand.lower()
            if original_required and not original:
                continue
            offers.append(
                Offer(
                    article=article or name[:40],
                    name=f"{brand} {name}".strip(),
                    delivery_days=days,
                    price=price,
                    is_original=original,
                    supplier=self.name,
                    search_url=self.search_url(article or text),
                    city=self.city,
                )
            )
        offers.sort(key=lambda o: (o.price <= 0, o.price, o.delivery_days))
        return offers

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]:
        return pick_same_delivery(offers)

    def place_order(self, offers: list[Offer]) -> OrderResult:
        if not offers:
            return OrderResult(ok=False, error="пустой список ПартКом")
        start = offers[0].search_url or self.search_url(offers[0].article)
        state = DATA_DIR / "partkom_state.json"

        def steps(page) -> None:
            visit_offers_for_order(page, offers, self.search_url)

        err = run_playwright(
            start,
            state,
            steps,
            user=PARTKOM_USER,
            password=PARTKOM_PASSWORD,
            headless=False,
        )
        if err:
            return OrderResult(ok=False, error=f"ПартКом ({self.city}): {err}")
        ref = f"PARTKOM-DRAFT-{datetime.now().strftime('%Y%m%d-%H%M')}"
        return OrderResult(
            ok=True,
            order_ref=ref,
            details={
                "city": self.city,
                "pickup": PARTKOM_PICKUP,
                "payment": "postpay",
                "articles": [o.article for o in offers],
                "lines": order_line_details(offers),
                "url": self.base,
            },
        )
