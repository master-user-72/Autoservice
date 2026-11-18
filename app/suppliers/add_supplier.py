# -*- coding: utf-8 -*-
"""Интерактивное добавление поставщика.

Запуск из корня проекта:
  .venv\\Scripts\\python.exe -m app.suppliers.add_supplier
или add_supplier.bat в этой папке.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RESERVED = {
    "add_supplier",
    "base",
    "browser",
    "composite",
    "http_util",
    "mock",
    "playwright_base",
    "__init__",
    "rossko",
    "partkom",
    "emex",
    "exist",
}

LIST_SKIP = {
    "add_supplier",
    "base",
    "browser",
    "composite",
    "http_util",
    "mock",
    "playwright_base",
    "__init__",
}

_SLUG_TR = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
})

ADAPTER_TEMPLATE = '''from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from app.config import CITY, DATA_DIR, {prefix}_BASE, {prefix}_PASSWORD, {prefix}_USER
from app.suppliers.base import Offer, OrderResult, VehicleInfo, order_line_details, pick_same_delivery
from app.suppliers.browser import run_playwright, visit_offers_for_order

NAME = {name}
SEARCH_TEMPLATE = {search_tpl}
VIN_TEMPLATE = {vin_tpl}


class {cls}:
    name = NAME
    base = {prefix}_BASE
    city = CITY

    def search_url(self, text: str) -> str:
        q = quote((text or "").strip())
        return SEARCH_TEMPLATE.replace("{{base}}", self.base).replace("{{q}}", q)

    def vin_url(self, vin: str) -> str:
        return VIN_TEMPLATE.replace("{{base}}", self.base).replace("{{vin}}", quote((vin or "").strip()))

    def search_by_vin(self, vin: str) -> VehicleInfo:
        return VehicleInfo(
            vin=vin,
            title="Авто по VIN (" + self.name + ")",
            notes=self.city + " · {note} · " + self.vin_url(vin),
        )

    def match_items(self, description: str, original_required: bool) -> list[Offer]:
        warning = "нужны {prefix}_USER/{prefix}_PASSWORD (кабинет " + self.base + ") для цены"
        if {prefix}_USER and {prefix}_PASSWORD:
            warning = "поиск в кабинете " + self.name
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
            return OrderResult(ok=False, error="пустой список " + self.name)
        start = offers[0].search_url or self.search_url(offers[0].article)
        state = DATA_DIR / {state_file}

        def steps(page) -> None:
            visit_offers_for_order(page, offers, self.search_url)

        err = run_playwright(
            start,
            state,
            steps,
            user={prefix}_USER,
            password={prefix}_PASSWORD,
            headless=False,
        )
        if err:
            return OrderResult(ok=False, error=self.name + " (" + self.city + "): " + err)
        ref = "{prefix}-DRAFT-" + datetime.now().strftime("%Y%m%d-%H%M")
        return OrderResult(
            ok=True,
            order_ref=ref,
            details={{
                "city": self.city,
                "note": {note_lit},
                "payment": "postpay",
                "articles": [o.article for o in offers],
                "lines": order_line_details(offers),
                "url": self.base,
            }},
        )
'''


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _py(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _setup_console() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
            sys.stdin.reconfigure(encoding="utf-8")
        except Exception:
            pass


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return value or default


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = "д" if default else "н"
    raw = ask(f"{prompt} (д/н)", hint).lower()
    if raw in {"д", "да", "y", "yes", "1"}:
        return True
    if raw in {"н", "нет", "n", "no", "0"}:
        return False
    return default


def slugify(name: str) -> str:
    body = (name or "").strip().lower().replace("ё", "е").translate(_SLUG_TR)
    body = re.sub(r"[^a-z0-9]+", "_", body).strip("_")
    if body and body[0].isdigit():
        body = "s_" + body
    return body or "supplier"


def class_name(slug: str) -> str:
    parts = [p.title() for p in slug.split("_") if p]
    return "".join(parts) + "Supplier"


def env_prefix(slug: str) -> str:
    return slug.upper()


@dataclass
class Spec:
    title: str
    slug: str
    cls: str
    prefix: str
    base: str
    search_tpl: str
    vin_tpl: str
    city: str
    role: str
    note: str
    user: str
    password: str
    into_live: bool


def list_modules(root: Path) -> list[str]:
    names = []
    for path in sorted((root / "app" / "suppliers").glob("*.py")):
        if path.stem in LIST_SKIP or path.stem.startswith("_"):
            continue
        names.append(path.stem)
    return names


def show_list(root: Path) -> None:
    print("\nАдаптеры в app/suppliers:")
    for name in list_modules(root):
        print(f"  • {name}.py")
    text = (root / "app" / "suppliers" / "composite.py").read_text(encoding="utf-8")
    title = re.search(r'name = f"([^"]+) \(\{CITY\}\)"', text)
    if title:
        print(f"\nОбщий список live: {title.group(1)}")
    for match in re.finditer(
        r'\{\s*"name":\s*(\w+),\s*"url":\s*(\w+),\s*"city":\s*\w+,\s*"role":\s*"([^"]*)"',
        text,
    ):
        print(f"  • {match.group(1)} — {match.group(3)}")
    adapters = re.search(r"self\.adapters = \[([^\]]*)\]", text)
    if adapters:
        order = re.sub(r"self\.", "", adapters.group(1))
        print("  опрос:", " ".join(order.split()))


def collect_spec() -> Spec | None:
    print("\nНовый поставщик. Пустой ввод оставляет значение в скобках.\n")
    title = ask("Название в лоте и шапке")
    if not title:
        print("Нужно название.")
        return None
    slug = slugify(ask("Идентификатор латиницей (файл и .env)", slugify(title)))
    if slug in RESERVED:
        print(f"Имя «{slug}» занято служебным файлом.")
        return None
    if not re.fullmatch(r"[a-z][a-z0-9_]*", slug):
        print("Идентификатор: латиница, цифры, подчёркивание, начинается с буквы.")
        return None
    existing = _root() / "app" / "suppliers" / f"{slug}.py"
    if existing.exists():
        print(f"Файл {existing.name} уже есть — на шаге записи можно перезаписать.")
    base = ask("Сайт кабинета", "https://example.com").rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base
    search_tpl = ask("Шаблон поиска ({base} = сайт, {q} = запрос)", "{base}/search?text={q}")
    vin_tpl = ask("Шаблон VIN ({base} и {vin})", "{base}/vin?vin={vin}")
    city = ask("Город получения", "Тюмень")
    role = ask("Роль в шапке", "автозапчасти")
    note = ask("Офис / ПВЗ", city)
    user = ask("Логин кабинета (можно пусто)")
    password = ask("Пароль кабинета (можно пусто)")
    into_live = ask_yes("Добавить в общий список live", True)
    spec = Spec(
        title=title,
        slug=slug,
        cls=class_name(slug),
        prefix=env_prefix(slug),
        base=base,
        search_tpl=search_tpl,
        vin_tpl=vin_tpl,
        city=city,
        role=role,
        note=note,
        user=user,
        password=password,
        into_live=into_live,
    )
    print("\nБудет создано:")
    print(f"  файл   app/suppliers/{spec.slug}.py  ({spec.cls})")
    print(f"  .env   {spec.prefix}_BASE / _USER / _PASSWORD")
    print(f"  live   {'да' if spec.into_live else 'нет, режим SUPPLIER_ADAPTER=' + spec.slug}")
    if not ask_yes("Записать", True):
        print("Отменено.")
        return None
    return spec


def adapter_source(spec: Spec) -> str:
    return ADAPTER_TEMPLATE.format(
        prefix=spec.prefix,
        cls=spec.cls,
        name=_py(spec.title),
        search_tpl=_py(spec.search_tpl),
        vin_tpl=_py(spec.vin_tpl),
        note=spec.note.replace("\\", "\\\\").replace('"', '\\"'),
        note_lit=_py(spec.note),
        state_file=_py(spec.slug + "_state.json"),
    )


def patch_config(root: Path, spec: Spec) -> None:
    path = root / "app" / "config.py"
    text = path.read_text(encoding="utf-8")
    p = spec.prefix
    if f"{p}_BASE" in text:
        return
    block = (
        f"{p}_BASE = os.getenv({_py(p + '_BASE')}, {_py(spec.base)}).rstrip(\"/\")\n"
        f"{p}_USER = os.getenv({_py(p + '_USER')}, \"\").strip()\n"
        f"{p}_PASSWORD = os.getenv({_py(p + '_PASSWORD')}, \"\")\n"
    )
    path.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")


def patch_env_file(path: Path, spec: Spec) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    p = spec.prefix
    if f"{p}_BASE=" in text:
        return
    block = (
        f"\n# {spec.title}\n"
        f"{p}_BASE={spec.base}\n"
        f"{p}_USER={spec.user}\n"
        f"{p}_PASSWORD={spec.password}\n"
    )
    path.write_text(text.rstrip() + "\n" + block + "\n", encoding="utf-8")


def patch_init(root: Path, spec: Spec) -> None:
    path = root / "app" / "suppliers" / "__init__.py"
    text = path.read_text(encoding="utf-8")
    imp = f"from app.suppliers.{spec.slug} import {spec.cls}\n"
    if imp not in text:
        anchor = "from app.suppliers.exist import ExistSupplier\n"
        if anchor in text:
            text = text.replace(anchor, anchor + imp)
        else:
            text = text.replace(
                "from app.suppliers.rossko import RosskoSupplier\n",
                "from app.suppliers.rossko import RosskoSupplier\n" + imp,
            )
    branch = (
        f'        elif key == "{spec.slug}":\n'
        f"            _adapter = {spec.cls}()\n"
    )
    if f'key == "{spec.slug}"' not in text:
        text = text.replace(
            '        elif key in {"playwright", "browser", "web"}:\n',
            branch + '        elif key in {"playwright", "browser", "web"}:\n',
        )
    path.write_text(text, encoding="utf-8")


def patch_composite(root: Path, spec: Spec) -> None:
    path = root / "app" / "suppliers" / "composite.py"
    text = path.read_text(encoding="utf-8")
    p, slug, cls = spec.prefix, spec.slug, spec.cls
    alias = f"{p}_NAME"

    cfg_line = next((ln for ln in text.splitlines() if ln.startswith("from app.config import")), "")
    if cfg_line and f"{p}_BASE" not in cfg_line:
        text = text.replace(cfg_line, cfg_line.rstrip() + f", {p}_BASE")

    imp = f"from app.suppliers.{slug} import {cls}, NAME as {alias}\n"
    if imp not in text:
        rossko_imp = "from app.suppliers.rossko import RosskoSupplier, NAME as ROSSKO_NAME\n"
        if rossko_imp in text:
            text = text.replace(rossko_imp, rossko_imp + imp)
        else:
            first = re.search(r"from app\.suppliers\.\w+ import [^\n]+\n", text)
            if first:
                text = text[: first.end()] + imp + text[first.end() :]

    ctor = f"        self.{slug} = {cls}()\n"
    if f"self.{slug} =" not in text:
        exist_ctor = "        self.exist = ExistSupplier()\n"
        if exist_ctor in text:
            text = text.replace(exist_ctor, exist_ctor + ctor)
        else:
            text = text.replace(
                "        self.by_name = {a.name: a for a in self.adapters}\n",
                ctor + "        self.by_name = {a.name: a for a in self.adapters}\n",
            )

    m = re.search(r"self\.adapters = \[([^\]]*)\]", text)
    if m and f"self.{slug}" not in m.group(1):
        inner = m.group(1).rstrip()
        inner = inner + ("" if inner.endswith(",") else ",") + f" self.{slug}"
        text = text[: m.start(1)] + inner + text[m.end(1) :]

    title_line = re.search(r'name = f"([^"]+) \(\{CITY\}\)"', text)
    if title_line and spec.title not in title_line.group(1):
        text = text.replace(title_line.group(0), f'name = f"{title_line.group(1)} + {spec.title} ({{CITY}})"')

    row = (
        f'            {{"name": {alias}, "url": {p}_BASE, "city": CITY, "role": {_py(spec.role)}}},\n'
    )
    if f'"name": {alias}' not in text:
        exist_row = (
            '            {"name": EXIST_NAME, "url": EXIST_BASE, "city": CITY, '
            '"role": "автозапчасти, каталог и офис в городе"},\n'
        )
        if exist_row in text:
            text = text.replace(exist_row, exist_row + row)
        else:
            text = text.replace("        return [\n", "        return [\n" + row, 1)

    vin_body = text.split("def search_by_vin", 1)[-1][:1500]
    marker = "Exist {EXIST_BASE}"
    if f"{p}_BASE" not in vin_body and marker in text:
        text = text.replace(
            marker,
            marker + " · " + spec.title + " {" + p + "_BASE}",
            1,
        )

    path.write_text(text, encoding="utf-8")


def patch_readme(root: Path, spec: Spec) -> None:
    path = root / "README.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    line = f"- {spec.title} — {spec.role}, {spec.base}\n"
    if spec.title + " — " in text:
        return
    needle = "- [Exist](https://www.exist.ru/) — автозапчасти, каталог и офис в Тюмени\n"
    if needle in text:
        path.write_text(text.replace(needle, needle + line), encoding="utf-8")


def apply_spec(root: Path, spec: Spec) -> None:
    module = root / "app" / "suppliers" / f"{spec.slug}.py"
    if module.exists() and not ask_yes(f"Файл {module.name} уже есть. Перезаписать", False):
        print("Остановлено: файл адаптера не трогали.")
        return
    module.write_text(adapter_source(spec), encoding="utf-8")
    patch_config(root, spec)
    patch_env_file(root / ".env", spec)
    patch_env_file(root / ".env.example", spec)
    patch_init(root, spec)
    if spec.into_live:
        patch_composite(root, spec)
    patch_readme(root, spec)
    print("\nГотово. Перезапустите агент (run.bat).")
    print(f"Логин и пароль: {spec.prefix}_USER / {spec.prefix}_PASSWORD в .env")
    print("Пока нет живой цены, в строку лота может по-прежнему вставать Росско.")


def menu() -> None:
    _setup_console()
    root = _root()
    while True:
        print("\n=== Поставщики агента ===")
        print("1. Добавить поставщика")
        print("2. Список текущих")
        print("0. Выход")
        choice = ask("Пункт", "0")
        if choice in {"0", "q", "в", "выход"}:
            return
        if choice == "1":
            spec = collect_spec()
            if spec:
                apply_spec(root, spec)
        elif choice == "2":
            show_list(root)
        else:
            print("Нет такого пункта.")


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\nВыход.")
