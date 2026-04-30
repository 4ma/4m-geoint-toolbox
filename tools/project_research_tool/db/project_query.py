"""Queries the analysis-operation DB for project_request records.

Table: on_demand.project_request
DB:    analysis-operation
Full path used in SQL client: data.on_demand.project_request
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .connections import get_analysis_engine, safe_read_sql

logger = logging.getLogger(__name__)

_TABLE = "on_demand.project_request"
_FIELDS = """
    project_id,
    project_name,
    company_name,
    request_ts,
    state,
    ST_AsText(geom) AS geom_wkt
"""


def search_projects(
    query: str, env_path: Optional[Path] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    """Search project_request by name or project_id substring.

    Args:
        query: Free-text search string matched against project_name and project_id.
        env_path: Path to .env file (defaults to tool's .env).
        limit: Maximum rows to return.

    Returns:
        List of project dicts with keys: project_id, project_name, company_name,
        request_ts, state, geom_wkt.
    """
    logger.info(f"[DB] Search projects: '{query}'")
    engine = get_analysis_engine(env_path)

    sql = f"""
        SELECT {_FIELDS}
        FROM {_TABLE}
        WHERE project_name ILIKE %(q)s
           OR project_id::text ILIKE %(q)s
        ORDER BY request_ts DESC
        LIMIT %(limit)s
    """
    df = safe_read_sql(sql, engine, params={"q": f"%{query}%", "limit": limit})
    rows = df.to_dict(orient="records")
    for row in rows:
        if row.get("request_ts"):
            row["request_ts"] = str(row["request_ts"])
    return rows


def get_project_by_id(
    project_id: str, env_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Fetch a single project by exact project_id.

    Returns:
        Project dict or None if not found.
    """
    logger.info(f"[DB] Fetch project: {project_id}")
    engine = get_analysis_engine(env_path)

    sql = f"""
        SELECT {_FIELDS}
        FROM {_TABLE}
        WHERE project_id = %(project_id)s
        LIMIT 1
    """
    df = safe_read_sql(sql, engine, params={"project_id": project_id})
    if df.empty:
        return None

    row = df.iloc[0].to_dict()
    if row.get("request_ts"):
        row["request_ts"] = str(row["request_ts"])
    return row