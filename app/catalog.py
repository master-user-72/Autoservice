from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from app import db, garage
from data.doc1_catalog import doc1_trims
from data.garage_catalog import garage_trims, generation_trims

# Типовой рынок РФ: марка, модель, годы, мотор, кузов.
SEED_TRIMS: list[tuple[str, str, str, str, str]] = [
    ("Lada", "Granta", "2018-2024", "1.6", "седан"),
    ("Lada", "Granta", "2018-2024", "1.6", "лифтбек"),
    ("Lada", "Vesta", "2015-2024", "1.6", "седан"),
    ("Lada", "Vesta", "2017-2024", "1.8", "универсал"),
    ("Lada", "Niva Travel", "2021-2024", "1.7", "внедорожник"),
    ("Lada", "Largus", "2012-2024", "1.6", "универсал"),
    ("Toyota", "Camry", "2011-2017", "2.5", "седан"),
    ("Toyota", "Camry", "2018-2024", "2.5", "седан"),
    ("Toyota", "Camry", "2018-2024", "3.5", "седан"),
    ("Toyota", "RAV4", "2013-2018", "2.0", "кроссовер"),
    ("Toyota", "RAV4", "2019-2024", "2.5", "кроссовер"),
    ("Toyota", "Land Cruiser Prado", "2009-2023", "2.8D", "внедорожник"),
    ("Toyota", "Land Cruiser Prado", "2009-2023", "4.0", "внедорожник"),
    ("Toyota", "Corolla", "2013-2018", "1.6", "седан"),
    ("Toyota", "Hilux", "2015-2024", "2.4D", "пикап"),
    ("Hyundai", "Solaris", "2011-2016", "1.4", "седан"),
    ("Hyundai", "Solaris", "2017-2024", "1.6", "седан"),
    ("Hyundai", "Creta", "2016-2021", "1.6", "кроссовер"),
    ("Hyundai", "Creta", "2021-2024", "2.0", "кроссовер"),
    ("Hyundai", "Tucson", "2015-2020", "2.0", "кроссовер"),
    ("Hyundai", "Santa Fe", "2018-2024", "2.2D", "кроссовер"),
    ("Kia", "Rio", "2011-2016", "1.4", "седан"),
    ("Kia", "Rio", "2017-2024", "1.6", "седан"),
    ("Kia", "Sportage", "2016-2021", "2.0", "кроссовер"),
    ("Kia", "Sorento", "2015-2020", "2.2D", "кроссовер"),
    ("Kia", "Ceed", "2018-2024", "1.6", "хэтчбек"),
    ("Volkswagen", "Polo", "2010-2020", "1.6", "седан"),
    ("Volkswagen", "Polo", "2020-2024", "1.6", "лифтбек"),
    ("Volkswagen", "Tiguan", "2017-2024", "2.0", "кроссовер"),
    ("Volkswagen", "Passat", "2015-2022", "1.8", "седан"),
    ("Skoda", "Rapid", "2014-2020", "1.6", "лифтбек"),
    ("Skoda", "Octavia", "2013-2020", "1.4", "лифтбек"),
    ("Skoda", "Kodiaq", "2017-2024", "2.0", "кроссовер"),
    ("Renault", "Logan", "2014-2022", "1.6", "седан"),
    ("Renault", "Duster", "2015-2021", "2.0", "кроссовер"),
    ("Renault", "Sandero", "2014-2022", "1.6", "хэтчбек"),
    ("Nissan", "Qashqai", "2014-2021", "2.0", "кроссовер"),
    ("Nissan", "X-Trail", "2015-2021", "2.5", "кроссовер"),
    ("Nissan", "Almera", "2013-2018", "1.6", "седан"),
    ("Ford", "Focus", "2011-2018", "1.6", "хэтчбек"),
    ("Ford", "Kuga", "2013-2019", "1.6", "кроссовер"),
    ("Ford", "Transit", "2014-2024", "2.2D", "фургон"),
    ("Mazda", "CX-5", "2012-2016", "2.0", "кроссовер"),
    ("Mazda", "CX-5", "2017-2024", "2.5", "кроссовер"),
    ("Mazda", "6", "2013-2018", "2.5", "седан"),
    ("Suzuki", "Swift", "2005-2010", "1.3", "хэтчбек"),
    ("Suzuki", "Swift", "2011-2016", "1.2", "хэтчбек"),
    ("Suzuki", "Vitara", "2015-2024", "1.6", "кроссовер"),
    ("Suzuki", "Grand Vitara", "2005-2014", "2.0", "внедорожник"),
    ("Suzuki", "SX4", "2006-2013", "1.6", "хэтчбек"),
    ("Mitsubishi", "Outlander", "2012-2021", "2.4", "кроссовер"),
    ("Mitsubishi", "L200", "2015-2024", "2.4D", "пикап"),
    ("Mitsubishi", "Pajero Sport", "2016-2024", "2.4D", "внедорожник"),
    ("BMW", "3 Series", "2012-2018", "2.0", "седан"),
    ("BMW", "5 Series", "2010-2016", "2.0D", "седан"),
    ("BMW", "X5", "2013-2018", "3.0D", "кроссовер"),
    ("Mercedes", "C-Class", "2014-2021", "2.0", "седан"),
    ("Mercedes", "E-Class", "2016-2023", "2.0", "седан"),
    ("Mercedes", "Sprinter", "2013-2024", "2.2D", "фургон"),
    ("Audi", "A4", "2012-2018", "2.0", "седан"),
    ("Audi", "A6", "2011-2018", "2.0", "седан"),
    ("Audi", "Q5", "2017-2024", "2.0", "кроссовер"),
    ("Honda", "CR-V", "2012-2017", "2.4", "кроссовер"),
    ("Honda", "Civic", "2012-2016", "1.8", "седан"),
    ("Chevrolet", "Niva", "2009-2020", "1.7", "внедорожник"),
    ("Chevrolet", "Cruze", "2009-2015", "1.6", "седан"),
    ("UAZ", "Patriot", "2014-2024", "2.7", "внедорожник"),
    ("UAZ", "Hunter", "2003-2024", "2.7", "внедорожник"),
    ("GAZ", "Gazelle Next", "2013-2024", "2.8D", "фургон"),
    ("GAZ", "Sobol", "2010-2024", "2.8D", "фургон"),
    ("Geely", "Atlas", "2018-2024", "2.0", "кроссовер"),
    ("Geely", "Coolray", "2020-2024", "1.5", "кроссовер"),
    ("Haval", "Jolion", "2021-2024", "1.5", "кроссовер"),
    ("Haval", "F7", "2019-2024", "2.0", "кроссовер"),
    ("Chery", "Tiggo 4", "2019-2024", "1.5", "кроссовер"),
    ("Chery", "Tiggo 7 Pro", "2020-2024", "1.5", "кроссовер"),
    ("Subaru", "Forester", "2013-2018", "2.5", "кроссовер"),
    ("Lexus", "RX", "2016-2022", "3.5", "кроссовер"),
]


def seed_catalog(conn: Connection | None = None) -> None:
    db.seed_catalog_trims([*SEED_TRIMS, *doc1_trims(), *garage_trims()], conn)


def vehicle_catalog() -> list[dict[str, str]]:
    generations = {}
    bmw_bodies = {}
    for make, model, generation, _, _, body in generation_trims():
        key = (make.casefold(), f"{model} {generation}".casefold())
        generations[key] = (model, generation)
        if make == "BMW" and body:
            bmw_bodies[key] = body
    with db.locked() as conn:
        trims = conn.execute("SELECT make,model,year,engine,body FROM catalog_trims").fetchall()
        cars = conn.execute("""SELECT DISTINCT make,model,generation,year,engine,body
                               FROM vehicles WHERE archived=0 AND make!='' AND model!=''""").fetchall()

    fields = ("make", "model", "generation", "year", "engine", "body")
    unique = {}
    for row in [*cars, *trims]:
        from_catalog = "generation" not in row.keys()
        car = {"generation": "", **dict(row)}
        key = (car["make"].casefold(), car["model"].casefold())
        if from_catalog and key in bmw_bodies and car["body"]:
            # The previous import expanded BMW body types across a whole generation group.
            car["body"] = bmw_bodies[key]
        if key in generations and not car["generation"]:
            car["model"], car["generation"] = generations[key]
        key = tuple(car[field].strip().casefold() for field in fields)
        unique.setdefault(key, car)
    return list(unique.values())


def remember_trim(*, make: str = "", model: str = "", year: str = "", engine: str = "", body: str = "") -> None:
    make = (garage.extract_make(make) or make or "").strip()
    model = (model or "").strip()
    if not make:
        return
    db.upsert_catalog_trim(
        make=make,
        model=model,
        year=(year or "").strip(),
        engine=(engine or "").strip(),
        body=(body or "").strip(),
        source="user",
    )


def catalog_tree() -> dict[str, Any]:
    rows = db.list_catalog_trims()
    tree: dict[str, Any] = {}
    for row in rows:
        make = row["make"]
        model = row["model"] or ""
        node = tree.setdefault(make, {})
        trim = node.setdefault(model, {"years": [], "engines": [], "bodies": []})
        for field, key in (("year", "years"), ("engine", "engines"), ("body", "bodies")):
            value = (row.get(field) or "").strip()
            if value and value not in trim[key]:
                trim[key].append(value)
    makes = sorted(tree.keys(), key=str.lower)
    return {"makes": makes, "tree": tree}
