"""Deterministic demo catalogue and supplier contracts. No network operations."""

from datetime import timedelta

from app.suppliers.mock import CATALOG, _norm

SOURCES = {"rossko": "Росско", "partkom": "ПартКом", "emex": "Emex", "exist": "Exist"}
SCENARIOS = {
    "normal": "Обычные условия",
    "empty": "Нет товара",
    "stock": "Остаток 2 шт.",
    "offline": "Временная ошибка поиска",
    "price": "Изменение цены",
    "late": "Изменение срока",
    "unknown_delivery": "Доставка не рассчитана",
    "no_price": "Цена не указана",
    "eur": "Предложение в евро",
    "failure": "Отказ при оформлении",
    "lost": "Потеря ответа при оформлении",
    "manual": "Ручное оформление",
}
DEMO_VIN = "JMBXGKH8WLF012745"
DEMO_CAR = {"vin": DEMO_VIN, "make": "Mitsubishi", "model": "Pajero Sport",
            "year": "2020", "engine": "3.0 (6B31), бензин", "body": "SUV", "plate": "А123ВС96"}
_ALIASES = {
    "FLT-OIL-118": ("масляный фильтр", "фильтр масляный", "фильтр масла", "1230a182"),
    "FLT-AIR-332": ("воздушный фильтр", "фильтр воздушный", "1500a608"),
    "SHK-F-90": ("передний амортизатор", "амортизатор передний", "передние амортизаторы"),
    "BRK-F-4410": ("передние тормозные колодки", "колодки передние", "тормозные колодки передние"),
    "BRK-R-2204": ("задние тормозные колодки", "колодки задние", "тормозные колодки задние"),
}


def catalogue_match(query):
    key = _norm(query).strip(" .")
    for part in CATALOG:
        article = part["article"]
        aliases = (article, f"DEMO-OEM-{article}", part["name"], *_ALIASES.get(article, ()))
        if key in map(_norm, aliases):
            return part
    return None


def capabilities(source, scenario):
    manual = scenario == "manual" or (scenario == "normal" and source == "exist")
    return {"search": True, "refresh": True, "order": not manual, "reconcile": not manual,
            "manual": manual, "cancel": False}


def quote(source, scenario, part, car, day, checked_at):
    if scenario == "offline":
        return "TEMPORARY_ERROR", None
    if scenario == "empty":
        return "NO_OFFERS", None

    index = list(SOURCES).index(source)
    original = source != "emex"
    reference = "DEMO-OEM-" + part["article"]
    amount = round(part["price"] * 100) + (index + 1) * 12000 - (51000 if not original else 0)
    if scenario == "price":
        amount += 17500
    delay = part["delivery_days"] + (2 if scenario == "late" else 0)
    confirmed = all(car[key].casefold() == DEMO_CAR[key].casefold()
                    for key in ("vin", "make", "model", "year", "engine", "body"))
    return "OK", {
        "id": source + ":" + part["article"], "supplier": source, "supplier_name": SOURCES[source],
        "brand": "Mitsubishi" if original else "Demo Parts",
        "article": reference if original else "DEMO-ALT-" + part["article"],
        "oem": reference, "catalogue": part["article"], "name": part["name"],
        "original": original, "price": None if scenario == "no_price" else amount,
        "currency": "EUR" if scenario == "eur" else "RUB",
        "stock": 2 if scenario == "stock" else (12, 8, 20, 5)[index],
        "delivery": None if scenario == "unknown_delivery" else (18000, 15000, 24000, 21000)[index],
        "date_from": (day + timedelta(days=delay)).isoformat(),
        "date_to": (day + timedelta(days=delay)).isoformat(),
        "pickup": "Екатеринбург · учебный пункт " + str(index + 1),
        "checked_at": checked_at, "channel": "manual" if capabilities(source, scenario)["manual"] else "demo_api",
        "fit": "catalogue" if confirmed else "unverified",
        "basis": "Учебная связка VIN → OEM" if confirmed else "",
        "analog_basis": "Учебная связь с " + reference if not original else None,
    }


def outcome(scenario, operation):
    """Return simulated supplier status and its persisted receipt, if any."""
    ref = "DEMO-" + operation.upper()
    if scenario == "failure":
        return "error", None
    if scenario == "lost":
        return "unknown", ref
    return "accepted", ref
