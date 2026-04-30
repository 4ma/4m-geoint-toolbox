"""Flask application entry point for project_research_tool.

Routes:
    GET  /               — serve index.html (project search + form)
    GET  /results        — serve results.html (pipeline output page)
    POST /search         — live project search → project_request table
    POST /run            — run full pipeline, return results JSON
    POST /save-to-drive  — upload HTML results page to Drive folder
    GET  /health         — liveness check
"""
import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# Ensure tool root is on sys.path when running as `python main.py`
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from db.municipality_query import get_municipality
from db.project_query import get_project_by_id, search_projects
from handlers import google_drive
import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_ENV_PATH = Path(__file__).parent / ".env"


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/results")
def results():
    return render_template("results.html", results=None)


@app.post("/search")
def search():
    """Live project search — returns up to 20 matching projects."""
    body = request.get_json(silent=True) or {}
    query = body.get("query", "").strip()
    if len(query) < 2:
        return jsonify([])

    projects = search_projects(query, env_path=_ENV_PATH)
    # Strip geom_wkt from dropdown results (sent only after project selection)
    for p in projects:
        p.pop("geom_wkt", None)
    return jsonify(projects)


@app.post("/run")
def run():
    """Run the full pipeline for a confirmed project."""
    body = request.get_json(silent=True) or {}
    project_id = body.get("project_id", "").strip()
    filters = body.get("filters", {})

    if not project_id:
        return jsonify({"error": "project_id is required"}), 400

    project = get_project_by_id(project_id, env_path=_ENV_PATH)
    if not project:
        return jsonify({"error": f"Project not found: {project_id}"}), 404

    location = get_municipality(project.get("geom_wkt", ""), env_path=_ENV_PATH)
    project.update(location)

    results = pipeline.run(project, filters)
    return jsonify(results)


@app.post("/save-to-drive")
def save_to_drive():
    """Save the rendered HTML results page to the project's Drive folder."""
    body = request.get_json(silent=True) or {}
    project_id = body.get("project_id", "").strip()
    html_content = body.get("html", "")

    if not project_id:
        return jsonify({"error": "project_id is required"}), 400

    try:
        project = get_project_by_id(project_id, env_path=_ENV_PATH)
        if not project:
            return jsonify({"error": f"Project not found: {project_id}"}), 404

        drive_info = google_drive.create_project_folder(
            project["project_name"], project_id
        )
        file_url = google_drive.save_html_to_drive(drive_info, project_id, html_content)
        return jsonify({"status": "ok", "url": file_url})
    except Exception as e:
        logger.error(f"[Drive] save-to-drive error: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=config.DEBUG, port=config.PORT)