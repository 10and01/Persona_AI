"""
Lightweight migration runner for the Persona AI database.

Usage
-----
Run as a standalone script to apply the schema to a PostgreSQL database::

    python -m persona_ai.migrate          # uses DATABASE_URL from env
    python -m persona_ai.migrate --echo   # prints SQL to stdout instead

Or import and call ``run_migration`` programmatically.
"""

from __future__ import annotations

import argparse
import os
import sys


def run_migration(*, database_url: str | None = None, echo: bool = False) -> None:
    """Apply the Persona AI DDL to *database_url*.

    Parameters
    ----------
    database_url:
        PostgreSQL connection string.  Falls back to the ``DATABASE_URL``
        environment variable when *None*.
    echo:
        When *True* the SQL is printed to stdout instead of being executed.
    """
    from .database_schema import generate_schema_sql

    sql = generate_schema_sql()

    if echo:
        print(sql)
        return

    url = database_url or os.getenv("DATABASE_URL", "")
    if not url:
        print(
            "ERROR: No database URL provided.  Set DATABASE_URL or pass --url.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import psycopg2  # type: ignore[import-untyped]
    except ImportError:
        print(
            "ERROR: psycopg2 is required to run migrations.  "
            "Install it with: pip install psycopg2-binary",
            file=sys.stderr,
        )
        sys.exit(1)

    conn = psycopg2.connect(url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Migration applied successfully.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Persona AI database schema")
    parser.add_argument("--url", default=None, help="PostgreSQL connection URL")
    parser.add_argument(
        "--echo",
        action="store_true",
        help="Print SQL to stdout instead of executing",
    )
    args = parser.parse_args()
    run_migration(database_url=args.url, echo=args.echo)


if __name__ == "__main__":
    main()
