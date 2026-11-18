from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote
from xml.etree import ElementTree as ET

from app.config import CITY, DATA_DIR, EMEX_BASE, EMEX_PASSWORD, EMEX_PICKUP, EMEX_USER
from app.suppliers.base import Offer, OrderResult, VehicleInfo, pick_same_delivery
from app.suppliers.base import order_line_details
from app.suppliers.browser import run_playwright, visit_offers_for_order
from app.suppliers.http_util import client

NAME = "Emex"
SOAP_URL = "http://ws.emex.ru/EmExService.asmx"


class EmexSupplier:
    name = NAME
    base = EMEX_BASE
    city = CITY

    def search_url(self, text: str) -> str:
        q = quote(text.strip())
        compact = re.sub(r"[\s\-]", "", text)
        if re.fullmatch(r"[A-Za-z0-9]{4,32}", compact):
            return f"{self.base}/products?detailNum={quote(compact)}"
        return f"{self.base}/products?q={q}"

    def vin_url(self, vin: str) -> str:
        return f"{self.base}/catalogs/vin?vin={quote(vin)}"

    def search_by_vin(self, vin: str) -> VehicleInfo:
        return VehicleInfo(
            vin=vin,
            title="Авто по VIN (Emex)",
            notes=f"{self.city}, {EMEX_PICKUP} · {self.vin_url(vin)}",
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
                warning=f"нужны EMEX_USER/PASSWORD (веб-сервис ws.emex.ru) или кабинет. Получение: {EMEX_PICKUP}",
                search_url=self.search_url(description),
                city=self.city,
            )
        ]

    def _soap_search(self, text: str, original_required: bool) -> list[Offer]:
        if not (EMEX_USER and EMEX_PASSWORD):
            return []
        compact = re.sub(r"[\s\-]", "", text)
        if not re.fullmatch(r"[A-Za-z0-9]{4,32}", compact):
            return []
        subst = "OriginalOnly" if original_required else "All"
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <FindDetailAdv4 xmlns="http://tempuri.org/">
      <login>{_xml(EMEX_USER)}</login>
      <password>{_xml(EMEX_PASSWORD)}</password>
      <makeLogo></makeLogo>
      <detailNum>{_xml(compact)}</detailNum>
      <substLevel>{subst}</substLevel>
      <substFilter>None</substFilter>
      <deliveryRegionType>PRI</deliveryRegionType>
      <maxOneDetailOffersCount>20</maxOneDetailOffersCount>
      <minQuantity>1</minQuantity>
    </FindDetailAdv4>
  </soap:Body>
</soap:Envelope>"""
        try:
            with client() as http:
                response = http.post(
                    SOAP_URL,
                    content=body.encode("utf-8"),
                    headers={
                        "Content-Type": "text/xml; charset=utf-8",
                        "SOAPAction": '"http://tempuri.org/FindDetailAdv4"',
                    },
                    timeout=20.0,
                )
                if response.status_code >= 400:
                    return []
                return _parse_emex_xml(response.text, original_required, self.search_url(compact))
        except Exception:
            return []

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]:
        return pick_same_delivery(offers)

    def place_order(self, offers: list[Offer]) -> OrderResult:
        if not offers:
            return OrderResult(ok=False, error="пустой список Emex")
        start = offers[0].search_url or self.search_url(offers[0].article)
        state = DATA_DIR / "emex_state.json"

        def steps(page) -> None:
            visit_offers_for_order(page, offers, self.search_url)

        err = run_playwright(
            start,
            state,
            steps,
            user=EMEX_USER,
            password=EMEX_PASSWORD,
            headless=False,
        )
        if err:
            return OrderResult(ok=False, error=f"Emex ({self.city}): {err}")
        ref = f"EMEX-DRAFT-{datetime.now().strftime('%Y%m%d-%H%M')}"
        return OrderResult(
            ok=True,
            order_ref=ref,
            details={
                "city": self.city,
                "pickup": EMEX_PICKUP,
                "payment": "postpay",
                "articles": [o.article for o in offers],
                "lines": order_line_details(offers),
                "url": self.base,
            },
        )


def _xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _parse_emex_xml(xml_text: str, original_required: bool, search_url: str) -> list[Offer]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    offers: list[Offer] = []
    for node in root.iter():
        tag = node.tag.split("}")[-1]
        if tag != "SoapDetailItem":
            continue
        fields = {child.tag.split("}")[-1]: (child.text or "").strip() for child in list(node)}
        article = fields.get("DetailNum") or ""
        name = fields.get("DetailNameRus") or article
        brand = fields.get("MakeName") or ""
        group = (fields.get("PriceGroup") or "").lower()
        try:
            price = float((fields.get("ResultPrice") or "0").replace(",", "."))
        except ValueError:
            price = 0.0
        try:
            days = int(float(fields.get("ADDays") or fields.get("DeliverTimeGuaranteed") or 2))
        except ValueError:
            days = 2
        original = group == "original" or "оригинал" in name.lower()
        if original_required and not original:
            continue
        if not article and not name:
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
