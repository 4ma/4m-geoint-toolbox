"""Pipeline orchestrator for project_research_tool.

Each step is individually selectable via filters["steps_to_run"].
Steps run sequentially; each has its own try/except so a failure never blocks others.

Selectable steps:
  "drive"          — Google Drive folder creation
  "prioritizer"    — Blueprints Prioritizer (spatial query + GeoPackage export)
  "internal_layers"— Internal Layers / Query Plugin (stub, future)
  "classifier"     — Gemini document classifier
  "research"       — Claude web research

The downloader always runs when the prioritizer runs (they are coupled).
Classifier attribute merge into GeoPackage also runs automatically after classifier
if a GeoPackage was produced by the prioritizer.
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

from handlers import classifier, google_drive, gpkg_handler, qgis_runner, research_agent

logger = logging.getLogger(__name__)

_ALL_STEPS = {"drive", "prioritizer", "internal_layers", "classifier", "research"}


def run(project_data: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the research pipeline for a confirmed project.

    Args:
        project_data: Merged project + location dict (project_id, project_name,
                      company_name, request_ts, geom_wkt, municipality, county, state).
        filters: User-supplied options including:
                 - steps_to_run: list of step names to execute (default: all except research)
                 - buffer_m, source_ids, blueprint_types, sectors, min_file_size_mb

    Returns:
        Full results dict with step outputs and runtime metadata.
    """
    start = datetime.now()
    project_id = project_data["project_id"]
    project_name = project_data["project_name"]
    geom = project_data.get("geom_wkt", "")

    steps_to_run: Set[str] = set(
        filters.get("steps_to_run") or list(_ALL_STEPS - {"research"})
    )

    results: Dict[str, Any] = {
        "project": project_data,
        "run_at": start.isoformat(),
        "steps": {},
        "drive": None,
        "steps_run": sorted(steps_to_run),
    }

    gpkg_path: Optional[str] = None

    # ── Step 1: Google Drive folder ──────────────────────────────────────────
    if "drive" in steps_to_run:
        try:
            logger.info(f"[Drive] Step 1: Resolve folder for '{project_name}'")
            results["drive"] = google_drive.create_project_folder(project_name, project_id)
        except Exception as e:
            logger.error(f"[Drive] ERROR: {e}")
            results["drive"] = {"status": "error", "message": str(e)}
    else:
        results["drive"] = {"status": "skipped"}

    # ── Step 2: Blueprints Prioritizer ───────────────────────────────────────
    if "prioritizer" in steps_to_run:
        try:
            logger.info("[Prioritizer] Step 2: Blueprint prioritizer")
            prioritizer_result = qgis_runner.run_prioritizer(geom, filters)
            results["steps"]["prioritizer"] = prioritizer_result

            # Create GeoPackage from prioritizer records if data is available
            if prioritizer_result.get("status") == "success" and prioritizer_result.get("records"):
                gpkg_path = gpkg_handler.create_prioritizer_gpkg(
                    prioritizer_result["records"], project_id
                )
                results["steps"]["prioritizer"]["gpkg_path"] = gpkg_path

                # Upload GeoPackage to Drive
                if gpkg_path and results["drive"] and results["drive"].get("folder_id"):
                    gpkg_url = google_drive.upload_file(
                        results["drive"]["folder_id"],
                        gpkg_path,
                        f"prioritizer_{project_id}.gpkg",
                    )
                    results["steps"]["prioritizer"]["gpkg_drive_url"] = gpkg_url

        except Exception as e:
            logger.error(f"[Prioritizer] ERROR: {e}")
            results["steps"]["prioritizer"] = {"status": "error", "message": str(e)}

        # ── Step 2b: Downloader (coupled to prioritizer) ─────────────────────
        try:
            logger.info("[Downloader] Step 2b: Download prioritizer files")
            downloader_result = qgis_runner.run_downloader(
                results["steps"].get("prioritizer", {}), project_id
            )
            results["steps"]["downloader"] = downloader_result

            if results["drive"] and results["drive"].get("folder_id"):
                google_drive.upload_files(results["drive"], downloader_result)
        except Exception as e:
            logger.error(f"[Downloader] ERROR: {e}")
            results["steps"]["downloader"] = {"status": "error", "message": str(e)}
    else:
        results["steps"]["prioritizer"] = {"status": "skipped"}
        results["steps"]["downloader"] = {"status": "skipped"}

    # ── Step 3: Internal Layers (query_plugin — stub) ────────────────────────
    if "internal_layers" in steps_to_run:
        results["steps"]["internal_layers"] = {
            "status": "not_implemented",
            "message": "Internal Layers / Query Plugin not yet wired up.",
        }
        logger.warning("[InternalLayers] Step 3: Not yet implemented — stub")
    else:
        results["steps"]["internal_layers"] = {"status": "skipped"}

    # ── Step 4: Gemini Classifier ────────────────────────────────────────────
    if "classifier" in steps_to_run:
        try:
            logger.info("[Classifier] Step 4: Gemini classifier")
            classifier_result = classifier.run(project_id)
            results["steps"]["classifier"] = classifier_result

            # Merge classification attributes into the GeoPackage if one was created
            if gpkg_path and classifier_result.get("status") == "success":
                gpkg_handler.merge_classifier_attributes(
                    gpkg_path, classifier_result.get("files", [])
                )
        except Exception as e:
            logger.error(f"[Classifier] ERROR: {e}")
            results["steps"]["classifier"] = {"status": "error", "message": str(e)}
    else:
        results["steps"]["classifier"] = {"status": "skipped"}

    # ── Step 5: Web Research ─────────────────────────────────────────────────
    if "research" in steps_to_run:
        try:
            logger.info("[Research] Step 5: Web research")
            results["steps"]["research"] = research_agent.run(
                project_name,
                project_id,
                project_data.get("municipality", ""),
                project_data.get("state", ""),
            )
        except Exception as e:
            logger.error(f"[Research] ERROR: {e}")
            results["steps"]["research"] = {"status": "error", "message": str(e)}
    else:
        results["steps"]["research"] = {"status": "skipped"}

    results["runtime_seconds"] = round((datetime.now() - start).total_seconds(), 1)
    logger.info(f"Pipeline complete in {results['runtime_seconds']}s — steps: {sorted(steps_to_run)}")
    return results