"""Explicitly close the disposable SQLite port and roll back failed effects."""

from contextlib import closing, contextmanager
import sqlite3


@contextmanager
def transaction(path, timeout=1):
    with closing(sqlite3.connect(path, timeout=timeout)) as connection, connection:
        yield connection
