import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def data_dir():
    return Path(os.environ.get("CABLEPLAN_DATA", ".runtime"))


@contextmanager
def connect():
    data_dir().mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(data_dir() / "database.sqlite", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def migrate():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY)")
        for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            if not db.execute("SELECT 1 FROM migrations WHERE name=?", (path.name,)).fetchone():
                # SQL files are bundled trusted source, never user input.
                db.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + path.read_text()
                    + "\nINSERT INTO migrations VALUES ('"
                    + path.name
                    + "');\nCOMMIT;"
                )


def setting(db, key):
    row = db.execute("SELECT value FROM site_settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else ""
