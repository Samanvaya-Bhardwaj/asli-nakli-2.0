"""Connections to the three engines. Read-only mode uses a different account (or file mode)."""

import sqlite3
from typing import Any


def pg_pool(url: str) -> Any:
    from psycopg_pool import ConnectionPool

    return ConnectionPool(url, min_size=1, max_size=4, open=True, kwargs={"autocommit": False})


def mongo_db(url: str) -> Any:
    from pymongo import MongoClient

    client: MongoClient[Any] = MongoClient(url, serverSelectionTimeoutMS=3000, tz_aware=True)
    return client[client.get_default_database().name]


def sqlite_conn(path: str, ro: bool) -> sqlite3.Connection:
    if ro:
        uri = "file:" + path.replace("\\", "/").replace("?", "%3f") + "?mode=ro"
        return sqlite3.connect(uri, uri=True, check_same_thread=False, timeout=5)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
