"""
Shared database connection helper for geoint_toolbox tools.

Usage:
    from shared.db import get_engine

    engine = get_engine()  # reads from .env in the calling tool's directory
    df = pd.read_sql(query, engine)
"""
import os
import sys
from pathlib import Path
from urllib import parse

from dotenv import load_dotenv
from sqlalchemy import create_engine


def get_engine(env_path: Path = None):
    """
    Create a SQLAlchemy engine from .env credentials.

    Args:
        env_path: Path to .env file. If None, looks for .env in the caller's
                  tool directory (the directory of the script that imported this).
    """
    if env_path and env_path.exists():
        load_dotenv(env_path)

    host = os.environ.get("DB_HOST")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "utility_owners")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")

    missing = []
    if not host:
        missing.append("DB_HOST")
    if not user:
        missing.append("DB_USER")
    if not password:
        missing.append("DB_PASSWORD")

    if missing:
        print(f"ERROR: {', '.join(missing)} must be set in .env or environment.")
        print("       Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    encoded_pw = parse.quote(password)
    url = f"postgresql+psycopg2://{user}:{encoded_pw}@{host}:{port}/{name}"
    return create_engine(url)
