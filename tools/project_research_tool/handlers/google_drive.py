"""Google Drive operations for project_research_tool.

Uses a Google Service Account (JSON key file) — no OAuth flow.
Credentials path set via GOOGLE_SERVICE_ACCOUNT_JSON in .env.
"""
import logging
import os
from typing import Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import config

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive"]

# Sub-folders created per project. Extended when new plugins are wired in.
_DEFAULT_SOURCE_FOLDERS = ["plans", "utility_owners","layers"]


def _get_service():
    creds = service_account.Credentials.from_service_account_file(
        config.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=_SCOPES
    )
    return build("drive", "v3", credentials=creds)


def _find_folder(service, name: str, parent_id: str) -> Optional[str]:
    """Return the ID of an existing folder with this name under parent, or None."""
    q = (
        f"name = '{name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"trashed = false"
    )
    results = service.files().list(q=q, fields="files(id)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: str) -> str:
    """Create a Drive folder under parent and return its ID."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def create_project_folder(project_name: str, project_id: str) -> Dict:
    """Resolve or create the project Drive folder and its source sub-folders.

    Args:
        project_name: Human-readable project name.
        project_id: Project UUID — included in the folder name to avoid collisions.

    Returns:
        {
            "folder_id": str,
            "folder_url": str,
            "subfolder_map": {source_name: folder_id, ...}
        }
    """
    logger.info(f"[Drive] Resolving folder: '{project_name}' ({project_id})")
    service = _get_service()
    parent_id = config.GOOGLE_DRIVE_PARENT_FOLDER_ID
    folder_name = f"{project_name} — {project_id}"

    folder_id = _find_folder(service, folder_name, parent_id)
    if folder_id:
        logger.info(f"[Drive] Existing folder: {folder_id}")
    else:
        folder_id = _create_folder(service, folder_name, parent_id)
        logger.info(f"[Drive] Created folder: {folder_id}")

    subfolder_map: Dict[str, str] = {}
    for source in _DEFAULT_SOURCE_FOLDERS:
        sub_id = _find_folder(service, source, folder_id)
        if not sub_id:
            sub_id = _create_folder(service, source, folder_id)
        subfolder_map[source] = sub_id

    return {
        "folder_id": folder_id,
        "folder_url": f"https://drive.google.com/drive/folders/{folder_id}",
        "subfolder_map": subfolder_map,
    }


def upload_files(drive_info: Dict, downloader_results: Dict) -> None:
    """Upload downloaded files to their matching Drive sub-folders.

    Args:
        drive_info: Output of create_project_folder().
        downloader_results: Output of qgis_runner.run_downloader().
            Expected shape: {"files": [{"file_name", "source_table", "local_path"}, ...]}
    """
    if downloader_results.get("status") in ("error", "not_implemented"):
        logger.info("[Drive] Skipping upload — downloader step not available")
        return

    service = _get_service()
    subfolder_map = drive_info.get("subfolder_map", {})

    for file_info in downloader_results.get("files", []):
        local_path = file_info.get("local_path")
        file_name = file_info.get("file_name")
        source = file_info.get("source_table", "public_records")

        if not local_path or not os.path.exists(local_path):
            logger.warning(f"[Drive] File not found, skipping: {local_path}")
            continue

        parent_folder_id = subfolder_map.get(source, drive_info["folder_id"])
        media = MediaFileUpload(local_path, resumable=True)
        metadata = {"name": file_name, "parents": [parent_folder_id]}
        service.files().create(body=metadata, media_body=media, fields="id").execute()
        logger.info(f"[Drive] Uploaded: {file_name} → {source}/")


def upload_file(folder_id: str, local_path: str, file_name: str) -> str:
    """Upload a single local file to a Drive folder.

    Args:
        folder_id: Drive folder ID to upload into.
        local_path: Absolute path to the local file.
        file_name: Name the file should have in Drive.

    Returns:
        Drive file URL.
    """
    if not os.path.exists(local_path):
        logger.warning(f"[Drive] File not found, skipping upload: {local_path}")
        return ""

    service = _get_service()
    media = MediaFileUpload(local_path, resumable=True)
    metadata = {"name": file_name, "parents": [folder_id]}
    created = service.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = created["id"]
    logger.info(f"[Drive] Uploaded {file_name} → {folder_id}")
    return f"https://drive.google.com/file/d/{file_id}/view"


def save_html_to_drive(drive_info: Dict, project_id: str, html_content: str) -> str:
    """Save an HTML results page as a file in the project's Drive folder.

    Args:
        drive_info: Output of create_project_folder().
        project_id: Used to name the saved file.
        html_content: Full HTML string of the results page.

    Returns:
        Drive file URL.
    """
    import tempfile

    service = _get_service()
    folder_id = drive_info.get("folder_id", config.GOOGLE_DRIVE_PARENT_FOLDER_ID)
    file_name = f"results_{project_id}.html"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp:
        tmp.write(html_content)
        tmp_path = tmp.name

    try:
        media = MediaFileUpload(tmp_path, mimetype="text/html", resumable=False)
        metadata = {"name": file_name, "parents": [folder_id]}
        created = service.files().create(body=metadata, media_body=media, fields="id").execute()
        file_id = created["id"]
        logger.info(f"[Drive] Saved results HTML: {file_name} ({file_id})")
        return f"https://drive.google.com/file/d/{file_id}/view"
    finally:
        os.unlink(tmp_path)