"""GeoPackage creation and classifier attribute merging for pipeline output.

Creates a .gpkg from prioritizer records after the spatial query runs.
After the classifier runs, merges classification attributes back into the same layer.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def create_prioritizer_gpkg(records: List[Dict[str, Any]], project_id: str) -> Optional[str]:
    """Create a GeoPackage from prioritizer blueprint records.

    Args:
        records: Output of qgis_runner.run_prioritizer()["records"].
                 Each record must have a "geom" field (WKB hex from PostGIS)
                 or a "geom_wkt" field.
        project_id: Used to name the output file and directory.

    Returns:
        Absolute path to the created .gpkg, or None if creation failed.
    """
    try:
        import geopandas as gpd
        import pandas as pd
        from shapely import wkb as shapely_wkb
        from shapely import wkt as shapely_wkt
    except ImportError:
        logger.error("[GPKG] geopandas is not installed — cannot create GeoPackage")
        return None

    if not records:
        logger.warning("[GPKG] No records — skipping GeoPackage creation")
        return None

    geometries = []
    for r in records:
        raw = r.get("geom") or r.get("geom_wkt") or ""
        try:
            if raw and (raw[:2] in ("00", "01") or raw.startswith("0")):
                geometries.append(shapely_wkb.loads(bytes.fromhex(raw)))
            elif raw:
                geometries.append(shapely_wkt.loads(raw))
            else:
                geometries.append(None)
        except Exception:
            geometries.append(None)

    df = pd.DataFrame(records)
    for col in ("geom", "geom_wkt"):
        if col in df.columns:
            df = df.drop(columns=[col])

    gdf = gpd.GeoDataFrame(df, geometry=geometries, crs="EPSG:4326")

    output_dir = Path("outputs") / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    gpkg_path = output_dir / f"prioritizer_{project_id}.gpkg"

    gdf.to_file(str(gpkg_path), driver="GPKG", layer="blueprints")
    logger.info(f"[GPKG] Created: {gpkg_path} ({len(gdf)} features)")
    return str(gpkg_path.resolve())


def merge_classifier_attributes(gpkg_path: str, classifier_files: List[Dict[str, Any]]) -> bool:
    """Add classification results as attributes to an existing GeoPackage.

    Joins on file_name → raw_file_name / original_file_name.
    Adds columns: utility_owners, key_insights, relevance_score.

    Args:
        gpkg_path: Path to the existing prioritizer .gpkg.
        classifier_files: Output of classifier.run()["files"].

    Returns:
        True on success, False on failure.
    """
    try:
        import geopandas as gpd
        import pandas as pd
    except ImportError:
        logger.error("[GPKG] geopandas is not installed")
        return False

    if not os.path.exists(gpkg_path) or not classifier_files:
        return False

    try:
        gdf = gpd.read_file(gpkg_path, layer="blueprints")

        cls_df = pd.DataFrame(classifier_files)[
            ["file_name", "utility_owners", "key_insights", "relevance_score"]
        ].copy()
        cls_df["utility_owners"] = cls_df["utility_owners"].apply(
            lambda v: ", ".join(v) if isinstance(v, list) else str(v or "")
        )
        cls_df = cls_df.rename(columns={"file_name": "_join_key"})
        cls_df["_join_key"] = cls_df["_join_key"].str.strip()

        # Try joining on the most likely file name column
        join_col = next(
            (c for c in ("raw_file_name", "original_file_name") if c in gdf.columns), None
        )
        if not join_col:
            logger.warning("[GPKG] No file name column found for classifier join")
            return False

        gdf["_join_key"] = gdf[join_col].astype(str).str.strip()
        merged = gdf.merge(cls_df, on="_join_key", how="left").drop(columns=["_join_key"])
        merged.to_file(gpkg_path, driver="GPKG", layer="blueprints")
        logger.info(f"[GPKG] Merged classifier attributes into {gpkg_path}")
        return True

    except Exception as e:
        logger.error(f"[GPKG] ERROR merging classifier attributes: {e}")
        return False