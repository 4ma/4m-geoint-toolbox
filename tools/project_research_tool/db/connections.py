"""Multi-database connection manager for project_research_tool.

Handles two PostgreSQL/PostGIS connections:
  - analysis-operation: project_request table (schema: on_demand)
  - geo-ing: municipalities_new (schema: db4data) + blueprints (schema: public_records)

Follows the same credential-safety patterns as shared/db.py:
  - Never prints credential values
  - Sanitizes SQLAlchemy errors before they reach stdout
"""
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError


def _load_env(env_path: Optional[Path]) -> None:
    if env_path and env_path.exists():
        load_dotenv(env_path)


def _build_engine(prefix: str) -> Engine:
    """Build a SQLAlchemy engine for the given env-var prefix (ANALYSIS or GEOING)."""
    host = os.environ.get(f"DB_{prefix}_HOST")
    port = int(os.environ.get(f"DB_{prefix}_PORT", "5432"))
    name = os.environ.get(f"DB_{prefix}_NAME")
    user = os.environ.get(f"DB_{prefix}_USER")
    password = os.environ.get(f"DB_{prefix}_PASSWORD")

    missing = [
        f"DB_{prefix}_{k}"
        for k, v in [("HOST", host), ("NAME", name), ("USER", user), ("PASSWORD", password)]
        if not v
    ]
    if missing:
        print(f"ERROR: Missing credentials: {', '.join(missing)}", file=sys.stderr)
        print("       Copy .env.example to .env and fill in credentials.", file=sys.stderr)
        sys.exit(1)

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=user,
        password=password,
        host=host,
        port=port,
        database=name,
    )

    try:
        engine = create_engine(url, hide_parameters=True)
        with engine.connect():
            pass
        return engine
    except SQLAlchemyError:
        print(f"ERROR: Could not connect to the {prefix.lower()} database.", file=sys.stderr)
        print("       Check credentials and network/VPN access.", file=sys.stderr)
        print("       (Original error suppressed to avoid leaking credentials.)", file=sys.stderr)
        sys.exit(1)


def get_analysis_engine(env_path: Optional[Path] = None) -> Engine:
    """Engine for the analysis-operation database."""
    _load_env(env_path)
    return _build_engine("ANALYSIS")


def get_geoing_engine(env_path: Optional[Path] = None) -> Engine:
    """Engine for the geo-ing database."""
    _load_env(env_path)
    return _build_engine("GEOING")


def safe_read_sql(query: str, engine: Engine, params: Optional[dict] = None) -> pd.DataFrame:
    """Run a SQL query and return a DataFrame, with sanitized errors."""
    try:
        return pd.read_sql(query, engine, params=params)
    except SQLAlchemyError:
        print("ERROR: Database query failed.", file=sys.stderr)
        print("       (Original error suppressed to avoid leaking credentials.)", file=sys.stderr)
        sys.exit(1)