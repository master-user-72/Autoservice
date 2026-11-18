from __future__ import annotations

from app.config import (
    SUPPLIER_LOGIN_URL,
    SUPPLIER_NAME,
    SUPPLIER_PASSWORD,
    SUPPLIER_STATE_PATH,
    SUPPLIER_USER,
)
from app.suppliers.base import Offer, OrderResult, VehicleInfo, order_line_details, pick_same_delivery
from app.suppliers.mock import MockSupplier


class PlaywrightSupplier:
    """Каркас заказа в кабинете поставщика. Селекторы заполняются, когда будут URL."""

    name = SUPPLIER_NAME or "Поставщик (Playwright)"

    def __init__(self) -> None:
        self._fallback = MockSupplier()

    def search_by_vin(self, vin: str) -> VehicleInfo:
        return self._fallback.search_by_vin(vin)

    def match_items(self, description: str, original_required: bool) -> list[Offer]:
        offers = self._fallback.match_items(description, original_required)
        for offer in offers:
            offer.supplier = self.name
        return offers

    def filter_same_delivery(self, offers: list[Offer]) -> list[Offer]:
        return pick_same_delivery(offers)

    def place_order(self, offers: list[Offer]) -> OrderResult:
        if not offers:
            return OrderResult(ok=False, error="пустой список позиций")
        if not SUPPLIER_LOGIN_URL:
            return OrderResult(
                ok=False,
                error="SUPPLIER_LOGIN_URL пуст. Укажите кабинет поставщика в .env; подбор пока идёт через демо-каталог.",
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return OrderResult(ok=False, error="Playwright не установлен. pip install playwright && playwright install chromium")

        SUPPLIER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = order_line_details(offers)
        articles = ", ".join(f"{line['article']}×{line['quantity']}" for line in lines)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context_kwargs = {}
                if SUPPLIER_STATE_PATH.exists():
                    context_kwargs["storage_state"] = str(SUPPLIER_STATE_PATH)
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                page.goto(SUPPLIER_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

                # Плейсхолдеры: замените селекторы под конкретный кабинет.
                if SUPPLIER_USER and page.locator("input[type=password]").count():
                    user_box = page.locator("input[type=email], input[name=login], input[name=user], input[type=text]").first
                    if user_box.count():
                        user_box.fill(SUPPLIER_USER)
                    page.locator("input[type=password]").first.fill(SUPPLIER_PASSWORD)
                    submit = page.locator("button[type=submit], input[type=submit]").first
                    if submit.count():
                        submit.click()
                    page.wait_for_timeout(1500)

                context.storage_state(path=str(SUPPLIER_STATE_PATH))
                browser.close()
        except Exception as exc:  # noqa: BLE001
            return OrderResult(ok=False, error=f"ошибка браузера поставщика: {exc}")

        return OrderResult(
            ok=False,
            error=(
                "Каркас Playwright открыл кабинет, но шаги VIN → корзина → оформление "
                f"ещё не заданы. Позиции: {articles}. Оплата не выполняется (постоплата)."
            ),
            details={"login_url": SUPPLIER_LOGIN_URL, "articles": [o.article for o in offers], "lines": lines},
        )
