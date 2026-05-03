"""Gemini-based document classifier stub.

Wraps the Gemini classifier script via subprocess.
Script path configured via GEMINI_CLASSIFIER_SCRIPT in .env.
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict

from config import config

logger = logging.getLogger(__name__)


def run(project_id: str) -> Dict[str, Any]:
    """Run the Gemini classifier on downloaded files for a project.

    Args:
        project_id: Locates downloaded files at outputs/{project_id}/downloads/.

    Returns:
        {
            "status": "success" | "error" | "not_implemented",
            "files": [
                {
                    "file_name": str,
                    "source_table": str,
                    "file_type": str,
                    "utility_owners": list,
                    "key_insights": str,
                    "relevance_score": float,   # 0.0 – 1.0
                    "drive_link": str,
                }
            ],
            "count": int
        }

    TODO: Fill in once GEMINI_CLASSIFIER_SCRIPT path is confirmed.
          Expected CLI: python <script> --project-id <id> --input-dir <path> --output-json
          Script must write JSON matching the schema above to stdout.
    """
    script_path = config.GEMINI_CLASSIFIER_SCRIPT
    if not script_path:
        logger.warning("[Classifier] GEMINI_CLASSIFIER_SCRIPT not set — skipping")
        return {"status": "not_implemented", "files": [], "count": 0}

    input_dir = Path("outputs") / project_id / "downloads"
    if not input_dir.exists():
        logger.warning(f"[Classifier] No downloads found at {input_dir}")
        return {"status": "error", "message": f"No downloads for {project_id}", "files": [], "count": 0}

    try:
        result = subprocess.run(
            ["python", script_path, "--project-id", project_id, "--input-dir", str(input_dir), "--output-json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.error(f"[Classifier] ERROR: {result.stderr}")
            return {"status": "error", "message": result.stderr, "files": [], "count": 0}

        output = json.loads(result.stdout)
        logger.info(f"[Classifier] Classified {len(output.get('files', []))} files")
        return output

    except subprocess.TimeoutExpired:
        logger.error("[Classifier] ERROR: Script timed out")
        return {"status": "error", "message": "Classifier timed out", "files": [], "count": 0}
    except json.JSONDecodeError as e:
        logger.error(f"[Classifier] ERROR: Could not parse output: {e}")
        return {"status": "error", "message": "Invalid classifier output format", "files": [], "count": 0}