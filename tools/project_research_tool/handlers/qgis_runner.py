"""QGIS plugin runner stubs for project_research_tool.

Architecture note
-----------------
All four plugins (pdf_prioritizer, utility_owners, query_plugin, fcc) are QGIS
GUI plugins — they are NOT CLI scripts and cannot be called via subprocess.
Integration is done by extracting their core SQL queries and running them
directly via SQLAlchemy (no QGIS runtime needed).

SQL sources (read-only reference, never modify):
  Prioritizer:    4ma-qgis-plugins/pdf_prioritizer_plugin/pdf_prioritizer_plugin_core/pdf_prioritizer_plugin_utils.py
  Utility Owners: 4ma-qgis-plugins/utility_owners_qgis_plugin/utility_owner_plugin_core/utility_owner_plugin_utils.py
  Query Plugin:   4ma-qgis-plugins/query_plugin/query_plugin_core/query_plugin_utils.py

Each stub below documents:
  - Exact input contract
  - Exact output schema
  - Which DB + tables to query
  - The SQL template to port when wiring up
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def run_prioritizer(geom_wkt: str, filters: Dict[str, Any]) -> Dict[str, Any]:
    """Query public_records.blueprints for files intersecting the project polygon.

    Replicates get_blueprints_intersecting_polygon() from pdf_prioritizer_plugin_utils.py.

    Args:
        geom_wkt: Project polygon as WKT string (SRID 4326).
        filters: {
            "buffer_m":       int   — extra buffer in meters (default 500),
            "source_ids":     list  — filter by source_id values (empty = all),
            "blueprint_types": list — filter by blueprint_type (empty = all),
            "sectors":        list  — e.g. ["Electricity", "Water"] (empty = all),
            "min_file_size_mb": float — minimum file size filter (default 0),
            "file_types":     list  — e.g. ["pdf", "dwg"] (empty = all),
        }

    Returns:
        {
            "status": "success" | "error" | "not_implemented",
            "records": [
                {
                    "uuid": str,
                    "blueprint_id": str,
                    "url": str,
                    "raw_file_bucket": str,
                    "raw_file_prefix": str,
                    "raw_file_name": str,
                    "raw_file_content_type": str,
                    "description": str,
                    "source_id": str,
                    "original_file_name": str,
                    "state": str,
                    "county_name": str,
                    "township_or_city": str,
                    "project_number": str,
                    "project_owner": str,
                    "zip_code": str,
                    "date_issued": str,
                    "pdf_type": str,
                    "blueprints_fragment_uuid": str,
                    "relevant_pages": str,
                    "geom_source": str,   # fragment | manual | automated | metadata | utility_owners
                    "automated_geotagging_level": str,
                    "blueprint_type": str,
                    "existing_utilities": str,    # translated names: Electricity, Water, ...
                    "drive_link": str,
                    "irrelevant_blueprint": bool,
                    "uo_geometry_uuid": str,
                    "uo_source_name": str,
                    "uo_source_ticket_id": str,
                    "uo_additional_files": str,
                }
            ],
            "count": int
        }

    DB: geo-ing
    Tables:
        public_records.blueprints          (alias b)
        public_records.blueprint_fragments (alias bf, LEFT JOIN on b.uuid = bf.blueprint_uuid)
        utility_owners.utility_owners_geometry (optional UO join)

    TODO: Port SQL from get_blueprints_intersecting_polygon() in pdf_prioritizer_plugin_utils.py.
          Use db.connections.get_geoing_engine() for the connection.
          Remove all QGIS/DBHandler/QgsMessageLog imports — use logging + SQLAlchemy only.
    """
    logger.warning("[Prioritizer] Not yet implemented — returning empty stub")
    return {"status": "not_implemented", "records": [], "count": 0}


def run_downloader(prioritizer_results: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    """Download S3 files from Prioritizer output to local outputs/ directory.

    Args:
        prioritizer_results: Output of run_prioritizer().
        project_id: Used to build local output path:
                    outputs/{project_id}/downloads/{source_table}/

    Returns:
        {
            "status": "success" | "error" | "not_implemented",
            "files": [
                {
                    "file_name": str,
                    "source_table": str,      # e.g. "public_records"
                    "file_type": str,          # e.g. "pdf", "dwg", "shp"
                    "local_path": str,         # absolute path to downloaded file
                    "size_mb": float,
                    "s3_bucket": str,
                    "s3_prefix": str,
                }
            ],
            "summary_by_source": {
                "<source_name>": {"count": int, "total_size_mb": float}
            }
        }

    TODO: Confirm download mechanism.
          Plugin uses DownloadS3FileTask from fourm_plugins_common.download_from_s3_task
          which calls the internal storage-service-grpc API.
          Determine if boto3 direct S3 access is available, or if the gRPC service is required.
          Fields needed from each prioritizer record: raw_file_bucket, raw_file_prefix,
          raw_file_name, raw_file_content_type, source_id.
    """
    logger.warning("[Downloader] Not yet implemented — returning empty stub")
    return {"status": "not_implemented", "files": [], "summary_by_source": {}}


def run_utility_owners(geom_wkt: str) -> Dict[str, Any]:
    """Query utility owners intersecting the project polygon.

    Replicates the intersection query from utility_owner_plugin_utils.py.

    Args:
        geom_wkt: Project polygon as WKT string (SRID 4326).

    Returns:
        {
            "status": "success" | "error" | "not_implemented",
            "owners": [
                {
                    "ticket_id": str,
                    "utility_code": str,
                    "sector": list,
                    "subsector": list,
                    "ticket_revision": str,
                    "organization_name": str,
                    "organization_phone": str,
                    "last_owner_response": str,     # located | clear | no_response
                    "last_response_creation_ts": str,
                    "ticket_creation_ts": str,
                    "utility_code_id": str,
                    "geom_wkt": str,
                }
            ],
            "count": int
        }

    DB: utility-owners (separate from analysis-operation and geo-ing)
    Tables:
        utility_owners.utility_owners_geometry  (spatial intersection)
        utility_owners.utility_owners_data      (INNER JOIN on utility_owners_geometry_uuid)

    SQL template (from utility_owner_plugin_utils.py):
        SELECT geom_table.source_ticket_id AS ticket_id,
               geom_table.ticket_revision,
               bucket, prefix, file_name,
               ticket_creation_ts, contained_infrastructure,
               ST_AsText(geom) AS geom_wkt
        FROM utility_owners.utility_owners_geometry geom_table
        INNER JOIN utility_owners.utility_owners_data data_table
            ON data_table.utility_owners_geometry_uuid = geom_table.uuid
        WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromText(<wkt>), 4326))

    TODO: Add DB_UO_* credentials (.env.example already includes them via existing
          geoint-toolbox polygon_query tool's .env pattern).
          Add get_utility_owners_engine() to db/connections.py.
    """
    logger.warning("[Owners] Not yet implemented — returning empty stub")
    return {"status": "not_implemented", "owners": [], "count": 0}


def run_fcc(geom_wkt: str) -> Dict[str, Any]:
    """Query FCC dataset intersecting the project polygon.

    Args:
        geom_wkt: Project polygon as WKT string (SRID 4326).

    Returns:
        {
            "status": "success" | "error" | "not_implemented",
            "points": [
                {
                    "owner_name": str,
                    "latitude": float,
                    "longitude": float,
                    "license_type": str,
                    "frequency_band": str,
                }
            ],
            "count": int,
            "gpkg_path": str | None    # local path to downloaded .gpkg file
        }

    TODO: Identify FCC source DB/table and set QGIS_FCC_SCRIPT in .env.
          Confirm whether this is a DB query or a file-based dataset.
    """
    logger.warning("[FCC] Not yet implemented — returning empty stub")
    return {"status": "not_implemented", "points": [], "count": 0, "gpkg_path": None}