from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote
from xml.etree import ElementTree as ET

from app.config import (
    CITY,
    DATA_DIR,
    ROSSKO_BASE,
    ROSSKO_DELIVERY_ID,
    ROSSKO_KEY1,
    ROSSKO_KEY2,
    ROSSKO_PASSWORD,
    ROSSKO_USER,
)
from app.suppliers.base import Offer, OrderResult, VehicleInfo, pick_same_delivery
from app.suppliers.base import order_line_details
from app.suppliers.browser import run_playwright, visit_offers_for_order
from app.suppliers.http_util import client

NAME = "Росско"


class RosskoSupplier:
    name = NAME
    base = ROSSKO_BASE
    city = CITY

    def search_url(self, text: str) -> str:
        return f"{self.base}/search?text={quote(text)}"

    def vin_url(self, vin: str) -> str:
        return f"{self.base}/visual-guide/vehicles.php?vtype=vc&ft=findByVIN&vin={quote(vin)}"

    def search_by_vin(self, vin: str) -> VehicleInfo:
        return VehicleInfo(
            vin=vin,
            title="Авто по VIN (OEM-каталог Росско)",
            notes=f"{self.city} · {self.base} · {self.vin_url(vin)}",
        )

    def match_items(self, description: str, original_required: bool) -> list[Offer]:
        offers = self._soap_search(description, original_required)
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
                warning=f"нужны ROSSKO_KEY1/KEY2 или вход в кабинет {self.base} для цены",
                search_url=self.search_url(description),
                city=self.city,
            )
        ]

    def _soap_search(self, text: str, original_required: bool) -> list[Offer]:
        if not (ROSSKO_KEY1 and ROSSKO_KEY2):
            return []
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Body>
    <GetSearch>
      <KEY1>{ROSSKO_KEY1}</KEY1>
      <KEY2>{ROSSKO_KEY2}</KEY2>
      <text>{_xml(text)}</text>
      <delivery_id>{_xml(ROSSKO_DELIVERY_ID)}</delivery_id>
    </GetSearch>
  </soapenv:Body>
</soapenv:Envelope>"""
        try:
            with client() as http:
                response = http.post(
                    "http://api.rossko.ru/service/v2.1/GetSearch",
                    content=body.encode("utf-8"),
                    headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "GetSearch"},
                    timeout=20.0,
                )
                response.raise_for_status()
        except Exception:
            return []
        return _parse_rossko_xml(response.text, original_required, self.search_url(text))

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]:
        return pick_same_delivery(offers)

    def place_order(self, offers: list[Offer]) -> OrderResult:
        if not offers:
            return OrderResult(ok=False, error="пустой список Росско")
        articles = [o.article for o in offers]
        start = offers[0].search_url or self.search_url(articles[0])
        state = DATA_DIR / "rossko_state.json"

        def steps(page) -> None:
            page.wait_for_timeout(800)
            visit_offers_for_order(page, offers, self.search_url)

        err = run_playwright(
            start,
            state,
            steps,
            user=ROSSKO_USER,
            password=ROSSKO_PASSWORD,
            headless=False,
        )
        if err:
            return OrderResult(ok=False, error=f"Росско ({self.city}): {err}")
        ref = f"ROSSKO-DRAFT-{datetime.now().strftime('%Y%m%d-%H%M')}"
        return OrderResult(
            ok=True,
            order_ref=ref,
            details={
                "city": self.city,
                "payment": "postpay",
                "articles": articles,
                "lines": order_line_details(offers),
                "url": self.base,
                "note": "Кабинет открыт, постоплата, получение Тюмень. Подтвердите корзину в браузере при первом обучении.",
            },
        )


def _xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _parse_rossko_xml(xml_text: str, original_required: bool, search_url: str) -> list[Offer]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    offers: list[Offer] = []
    for part in root.iter():
        tag = part.tag.split("}")[-1].lower()
        if tag != "part":
            continue
        fields = {child.tag.split("}")[-1].lower(): (child.text or "").strip() for child in list(part)}
        article = fields.get("partnumber") or fields.get("guid") or ""
        name = fields.get("name") or article
        brand = fields.get("brand") or ""
        price = 0.0
        days = 2
        for stock in part.iter():
            st = stock.tag.split("}")[-1].lower()
            if st != "stock":
                continue
            sf = {c.tag.split("}")[-1].lower(): (c.text or "").strip() for c in list(stock)}
            try:
                price = float(sf.get("price") or 0)
            except ValueError:
                price = 0.0
            try:
                days = int(float(sf.get("deliverytime") or 2))
            except ValueError:
                days = 2
            break
        if not article and not name:
            continue
        original = bool(re.search(r"оригинал|oem|original", f"{name} {brand}", re.I))
        if original_required and not original:
            continue
        offers.append(
            Offer(
                article=article or name[:40],
                name=f"{brand} {name}".strip(),
                delivery_days=max(days, 0),
                price=price,
                is_original=original,
                supplier=NAME,
                search_url=search_url,
                city=CITY,
            )
        )
        if len(offers) >= 8:
            break
    offers.sort(key=lambda o: (o.price <= 0, o.price, o.delivery_days))
    return offers
