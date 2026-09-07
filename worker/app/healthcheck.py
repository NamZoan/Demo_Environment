from __future__ import annotations

import os
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import psycopg


def check_database(database_url: str, connect: Callable = psycopg.connect) -> None:
    connect_kwargs = {}
    if "connect_timeout" not in parse_qs(urlsplit(database_url).query):
        connect_kwargs["connect_timeout"] = 3

    with connect(database_url, **connect_kwargs) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")


def main() -> int:
    try:
        check_database(os.environ["DATABASE_URL"], connect=psycopg.connect)
    except Exception:
        print("Worker database healthcheck failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
