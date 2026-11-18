"""Загрузка каталога из Doc1.docx в базу агента.

Использование:
  .venv\\Scripts\\python.exe import_doc1.py
  .venv\\Scripts\\python.exe import_doc1.py c:\\Temp\\Doc1.docx
"""

from __future__ import annotations

import sys
from pathlib import Path

from app import db
from app.catalog import catalog_tree
from data.doc1_catalog import doc1_trims

ROOT = Path(__file__).resolve().parent


def _check_docx(path: Path) -> None:
    if not path.exists():
        print(f"Файл не найден: {path}")
        return
    size = path.stat().st_size
    print(f"Источник: {path} ({size // 1024} КБ, таблицы в виде изображений)")


def import_doc1(*, source: str = "doc1") -> int:
    db.init_db()
    rows = doc1_trims()
    count = 0
    for make, model, year, engine, body in rows:
        db.upsert_catalog_trim(
            make=make,
            model=model,
            year=year,
            engine=engine,
            body=body,
            source=source,
        )
        count += 1
    return count


def main() -> int:
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"c:\Temp\Doc1.docx")
    _check_docx(docx)
    loaded = import_doc1()
    tree = catalog_tree()
    print(f"Загружено записей: {loaded}")
    print(f"Марок в каталоге: {len(tree['makes'])}")
    for make in ("BMW", "Mercedes", "Audi", "Volkswagen"):
        if make in tree["tree"]:
            models = sorted(tree["tree"][make].keys())
            print(f"  {make}: {len(models)} моделей")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
