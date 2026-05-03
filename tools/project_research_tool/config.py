"""All settings loaded from .env for project_research_tool."""
import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


class Config:
    # analysis-operation DB (project_request table)
    DB_ANALYSIS_OPERATIONS_HOST: str = os.environ.get("DB_ANALYSIS_OPERATIONS_HOST", "")
    DB_ANALYSIS_OPERATIONS_PORT: int = int(os.environ.get("DB_ANALYSIS_OPERATIONS_PORT", "5432"))
    DB_ANALYSIS_OPERATIONS_NAME: str = os.environ.get("DB_ANALYSIS_OPERATIONS_NAME", "")
    DB_ANALYSIS_OPERATIONS_USER: str = os.environ.get("DB_ANALYSIS_OPERATIONS_USER", "")
    DB_ANALYSIS_OPERATIONS_PASSWORD: str = os.environ.get("DB_ANALYSIS_OPERATIONS_PASSWORD", "")

    # geo-ing DB (municipalities_new + blueprints tables)
    DB_GEOING_HOST: str = os.environ.get("DB_GEOING_HOST", "")
    DB_GEOING_PORT: int = int(os.environ.get("DB_GEOING_PORT", "5432"))
    DB_GEOING_NAME: str = os.environ.get("DB_GEOING_NAME", "")
    DB_GEOING_USER: str = os.environ.get("DB_GEOING_USER", "")
    DB_GEOING_PASSWORD: str = os.environ.get("DB_GEOING_PASSWORD", "")

    # Google Drive
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_DRIVE_PARENT_FOLDER_ID: str = os.environ.get(
        "GOOGLE_DRIVE_PARENT_FOLDER_ID", "1a1K8BMbmzhxVK01bkQ4wHuQZQQ5VfFZH"
    )

    # Anthropic
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

    # Plugin paths (filled in when QGIS plugin integration is wired)
    QGIS_PRIORITIZER_SCRIPT: str = os.environ.get("QGIS_PRIORITIZER_SCRIPT", "")
    QGIS_DOWNLOADER_SCRIPT: str = os.environ.get("QGIS_DOWNLOADER_SCRIPT", "")
    QGIS_UTILITY_OWNERS_SCRIPT: str = os.environ.get("QGIS_UTILITY_OWNERS_SCRIPT", "")
    QGIS_FCC_SCRIPT: str = os.environ.get("QGIS_FCC_SCRIPT", "")

    # Gemini classifier
    GEMINI_CLASSIFIER_SCRIPT: str = os.environ.get("GEMINI_CLASSIFIER_SCRIPT", "")
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

    # Server
    PORT: int = int(os.environ.get("PORT", "5001"))
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"


config = Config()