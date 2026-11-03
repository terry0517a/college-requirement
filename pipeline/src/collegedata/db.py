import os

import psycopg


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or os.environ["DATABASE_URL"])
