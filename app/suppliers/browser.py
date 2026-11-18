from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from app.config import DATA_DIR
from app.suppliers.base import Offer, offer_quantity


def run_playwright(
    start_url: str,
    state_path: Path,
    after_open: Callable,
    *,
    user: str = "",
    password: str = "",
    headless: bool = False,
) -> Optional[str]:
    """Открывает кабинет поставщика. after_open(page) выполняет шаги заказа. Возвращает ошибку или None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright не установлен"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            kwargs = {}
            if state_path.exists():
                kwargs["storage_state"] = str(state_path)
            context = browser.new_context(**kwargs)
            page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            if user and page.locator("input[type=password]").count():
                box = page.locator(
                    "input[type=email], input[name='auth[email]'], input[name=login], input[name=user], input[type=text]"
                ).first
                if box.count():
                    box.fill(user)
                page.locator("input[type=password]").first.fill(password)
                submit = page.locator("button[type=submit], input[type=submit]").first
                if submit.count():
                    submit.click()
                    page.wait_for_timeout(1500)
            after_open(page)
            context.storage_state(path=str(state_path))
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    return None


def try_set_quantity(page, quantity: int) -> bool:
    if quantity <= 1:
        return False
    selectors = [
        "input[name=quantity]",
        "input[name=qty]",
        "input[name=count]",
        "input[type=number]",
        "input.qty",
        "input.quantity",
    ]
    for selector in selectors:
        field = page.locator(selector).first
        if field.count():
            field.fill(str(quantity))
            page.wait_for_timeout(250)
            return True
    return False


def try_add_to_cart(page) -> bool:
    selectors = [
        "button:has-text('В корзину')",
        "button:has-text('Купить')",
        "button:has-text('Добавить')",
        "a:has-text('В корзину')",
        ".add-to-cart",
        "[data-action='add-to-cart']",
    ]
    for selector in selectors:
        button = page.locator(selector).first
        if button.count():
            button.click()
            page.wait_for_timeout(500)
            return True
    return False


def visit_offers_for_order(page, offers: list[Offer], search_url) -> None:
    for offer in offers:
        url = offer.search_url or search_url(offer.article)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(700)
        qty = offer_quantity(offer)
        try_set_quantity(page, qty)
        try_add_to_cart(page)
