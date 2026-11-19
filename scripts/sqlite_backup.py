"""Copy or restore an Autoservice database to a new file using SQLite backup."""

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def copy_database(source: Path, target: Path) -> None:
    source = source.resolve(strict=True)
    target = target.resolve()
    if source == target:
        raise ValueError("Source and target must differ.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            with closing(sqlite3.connect(target)) as copy:
                original.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup failed PRAGMA integrity_check.")
                if copy.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("Backup failed PRAGMA foreign_key_check.")
        except BaseException:
            target.unlink()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path, help="New SQLite database file")
    args = parser.parse_args()
    copy_database(args.source, args.target)
    print(f"SQLite copy verified: {args.target}")


if __name__ == "__main__":
    main()
