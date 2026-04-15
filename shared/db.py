"""
Shared database connection helper for geoint_toolbox tools.

Designed so that NO credential value (host, port, user, password) ever appears
in stdout or stderr — even if the connection fails. Errors are sanitized at
this boundary so that calling tools (and any AI assistant watching their
output) only see generic failure messages.

Usage:
    from shared.db import get_engine

    engine = get_engine()  # reads from .env in the calling tool's directory
    df = pd.read_sql(query, engine)
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


def _load_credentials(env_path: Path = None) -> dict:
    """Read credentials from environment (or a .env file). Never prints values."""
    if env_path and env_path.exists():
        load_dotenv(env_path)

    creds = {
        "host":     os.environ.get("DB_HOST"),
        "port":     int(os.environ.get("DB_PORT", "5432")),
        "database": os.environ.get("DB_NAME", "utility_owners"),
        "user":     os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASSWORD"),
    }

    missing = [name for name, key in
               (("DB_HOST", "host"), ("DB_USER", "user"), ("DB_PASSWORD", "password"))
               if not creds[key]]

    if missing:
        # Report ONLY which env vars are missing — never echo what is set.
        print(f"ERROR: Missing required credentials: {', '.join(missing)}", file=sys.stderr)
        print("       Copy .env.example to .env and fill in your credentials,", file=sys.stderr)
        print("       or configure them via your team's secret store.", file=sys.stderr)
        sys.exit(1)

    return creds


def get_engine(env_path: Path = None):
    """
    Create a SQLAlchemy engine and verify the connection.

    All exceptions are caught and replaced with a sanitized message — no host,
    user, password, port, or database name appears in any error output.
    """
    creds = _load_credentials(env_path)

    # URL.create() returns an object whose __str__ masks the password as '***',
    # so even if SQLAlchemy logs or raises with the URL, the password is hidden.
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"],
        database=creds["database"],
    )

    try:
        # hide_parameters=True suppresses bound parameter values in error messages
        engine = create_engine(url, hide_parameters=True)
        # Force a connection now so we fail here (with sanitized output) rather
        # than later inside the caller, where exception handling is harder to
        # control.
        with engine.connect():
            pass
        return engine
    except SQLAlchemyError:
        # Deliberately do NOT include the original exception — it can contain
        # the connection URL, host, or username. Print a generic message only.
        print("ERROR: Could not connect to the database.", file=sys.stderr)
        print("       Check that your credentials are correct and the host is reachable.", file=sys.stderr)
        print("       (Original error suppressed to avoid leaking credentials.)", file=sys.stderr)
        sys.exit(1)


def safe_read_sql(query, engine, params=None):
    """
    Run a SQL query and return a pandas DataFrame, with sanitized errors.

    Use this instead of calling pd.read_sql directly — it ensures that any
    SQLAlchemy exception (which may contain the connection URL) is replaced
    with a generic message before reaching stdout.
    """
    import pandas as pd  # local import keeps shared/db.py importable without pandas
    try:
        return pd.read_sql(query, engine, params=params)
    except SQLAlchemyError:
        print("ERROR: Database query failed.", file=sys.stderr)
        print("       (Original error suppressed to avoid leaking credentials.)", file=sys.stderr)
        sys.exit(1)
