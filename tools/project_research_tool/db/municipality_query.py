"""Queries the geo-ing DB to resolve municipality/county/state from a project polygon.

Table: db4data.municipalities_new
DB:    geo-ing
Full path used in SQL client: data.db4data.municipalities_new

Relevant columns: municipality, state_name, counties, geom
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .connections import get_geoing_engine, safe_read_sql

logger = logging.getLogger(__name__)

_TABLE = "db4data.municipalities_new"


def get_municipality(geom_wkt: str, env_path: Optional[Path] = None) -> Dict[str, Any]:
    """Intersect the project polygon with municipalities_new to resolve location metadata.

    Args:
        geom_wkt: Project polygon as WKT string (SRID 4326), from project_request.geom.
        env_path: Path to .env file.

    Returns:
        Dict with keys: municipality, state, county.
        Values are None if no intersection is found.
    """
    logger.info("[DB] Municipality intersection query")
    engine = get_geoing_engine(env_path)

    sql = f"""
        SELECT municipality, state_name, counties
        FROM {_TABLE}
        WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromText(%(wkt)s), 4326))
        LIMIT 1
    """
    df = safe_read_sql(sql, engine, params={"wkt": geom_wkt})
    if df.empty:
        logger.warning("[DB] No municipality found for project polygon")
        return {"municipality": None, "state": None, "county": None}

    row = df.iloc[0].to_dict()
    # counties may be a PostgreSQL array — convert to string if needed
    counties = row.get("counties")
    if isinstance(counties, list):
        counties = ", ".join(str(c) for c in counties if c)
    elif counties is not None:
        counties = str(counties)

    return {
        "municipality": row.get("municipality"),
        "state": row.get("state_name"),
        "county": counties,
    }