"""Playwright smoke test against a running Autoservice instance with an empty demo DB."""

import argparse
import shutil
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

VIEWS = {
    "requests": "Заявки и поиск",
    "garage": "Гараж",
    "lots": "Дневной лот",
    "urgent": "Срочные позиции",
    "orders": "История заказов",
    "suppliers": "Подключения",
    "settings": "Настройки",
}


def check_routes(page, base_url):
    for path, title in VIEWS.items():
        for _ in range(2):
            response = page.goto(base_url + "/" + path)
            assert response.ok
            expect(page.locator("#title")).to_have_text(title)
            expect(page.locator("#nav [aria-current=page]")).to_have_attribute("href", "/" + path)
            expect(page.locator("#content")).not_to_contain_text("Загрузка")
            expect(page.locator("#content")).not_to_contain_text("Не удалось загрузить раздел")


def check_layout(browser, base_url, draft_path, output):
    for width, height in ((1920, 1080), (1600, 900), (1366, 768), (1024, 768)):
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(base_url + draft_path)
        expect(page.get_by_role("heading", name="Выбранные позиции (2)")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        expect(page.get_by_role("button", name="Найти предложения")).to_be_visible()
        if width == 1024:
            assert not page.locator("#cart").evaluate("(el) => el.open")
            page.locator("#cart summary").click()
            expect(page.get_by_role("button", name="Сохранить в лот")).to_be_visible()
            assert page.locator("#cart").bounding_box()["y"] >= 0
            page.locator("#cart summary").click()
        if output:
            page.screenshot(path=str(output / f"autoservice-{width}x{height}.png"), full_page=True)
        page.close()


def workflow(page, base_url, browser, output):
    page.goto(base_url + "/")
    page.get_by_role("button", name="Создать учебный пример").click()
    expect(page.get_by_role("heading", name="Выбранные позиции (2)")).to_be_visible()
    draft_path = page.evaluate("location.pathname")
    check_layout(browser, base_url, draft_path, output)
    check_routes(page, base_url)

    page.goto(base_url + draft_path)
    page.get_by_role("button", name="Разобрать заявку").click()
    page.get_by_label("Исходный текст").fill("передний амортизатор 2 шт.")
    page.get_by_role("button", name="Показать разбор").click()
    expect(page.get_by_label("Описание детали")).to_have_value("передний амортизатор")
    expect(page.get_by_label("Кол-во, шт.")).to_have_value("2")
    page.get_by_role("button", name="Добавить позиции в заявку").click()
    expect(page.get_by_role("button", name="передний амортизатор", exact=True)).to_be_visible()

    page.get_by_role("button", name="Масляный фильтр", exact=True).click()
    page.get_by_role("button", name="Найти предложения").click()
    expect(page.get_by_role("heading", name="Предложения по позиции: Масляный фильтр (1 шт.)")).to_be_visible()
    page.get_by_role("radio", name="Выбрать предложение Росско").check()
    page.get_by_role("button", name="Увеличить количество").first.click()
    expect(page.locator("#cart .stepper span").first).to_have_text("2")
    page.get_by_role("button", name="Сохранить в лот").click()
    modal = page.get_by_role("dialog")
    modal.get_by_role("button", name="Сохранить в лот").or_(
        modal.get_by_role("button", name="Подтвердить перенос")).click()
    expect(page.get_by_role("status")).to_have_text("Позиции сохранены в лот")

    page.get_by_role("button", name="Оформить срочно").click()
    modal.get_by_role("button", name="Перевести и открыть срочные").click()
    expect(page).to_have_url(base_url + "/urgent")
    page.get_by_role("row", name="Масляный фильтр", exact=False).get_by_role("button", name="Оформить", exact=True).click()
    modal.get_by_role("button", name="Подтвердить учебное оформление").click()
    expect(page.locator("#content")).to_contain_text("Принят поставщиком")
    order_path = page.evaluate("location.pathname")
    page.reload()
    expect(page.locator("#content")).to_contain_text("Принят поставщиком")
    expect(page.locator("#content")).to_contain_text("DEMO-")
    page.go_back()
    expect(page.locator("#title")).to_have_text("Срочные позиции")
    page.go_forward()
    expect(page).to_have_url(base_url + order_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--shots", type=Path)
    parser.add_argument("--chromium", default=shutil.which("chromium"))
    config = parser.parse_args()
    if config.shots:
        config.shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=config.chromium)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        workflow(page, config.url.rstrip("/"), browser, config.shots)
        assert not errors, errors
        browser.close()
    print("Chromium: 7 routes, 4 resolutions and end-to-end urgent checkout passed.")


if __name__ == "__main__":
    main()
