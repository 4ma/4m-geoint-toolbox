#!/usr/bin/env python3
"""
Koordinates pipeline: scrape layer metadata -> filter US-only -> export GPKG -> upload to S3

Subcommands:
  scrape         Fetch layer metadata by ID range, save to CSV
  export-upload  Export US layers from a CSV, download ZIPs, extract GPKGs, upload to S3
  all            Run scrape then export-upload in one shot

Usage:
  python pipeline.py scrape --start-id 101290 --end-id 102290 --out-csv output.csv
  python pipeline.py export-upload --in-csv output.csv
  python pipeline.py all --start-id 101290 --end-id 102290 --out-csv output.csv
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import io
import json
import logging
import os
import random
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

LAYER_API = "https://koordinates.com/services/api/v1.x/layers/{layer_id}/"
EXPORT_API = "https://koordinates.com/services/api/v1.x/exports/"
GPKG_MIME = "application/geopackage+sqlite3"
GPKG_FORMAT = "application/x-ogc-gpkg"
US_BBOX = (-125.0, 24.5, -66.9, 49.5)  # min_lon, min_lat, max_lon, max_lat

logger = logging.getLogger("koordinates_pipeline")


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        print(f"ERROR: {key} is not set. Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)
    return val


def build_headers() -> Dict[str, str]:
    return {
        "Cookie": _require_env("KOORDINATES_COOKIE"),
        "X-CSRFToken": _require_env("KOORDINATES_CSRF"),
        "Referer": "https://koordinates.com/",
    }


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(message)s")


# ---------------------------------------------------------------------------
# ID log helpers
# ---------------------------------------------------------------------------

def load_json_log(path: Path) -> Set[int]:
    if not path.exists():
        return set()
    return {int(x) for x in json.loads(path.read_text())}


def save_json_log(path: Path, ids: Set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(ids), indent=2))


def load_txt_log(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def append_txt_log(path: Path, layer_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(f"{layer_id}\n")


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _parse_extent(extent: Any) -> Optional[Dict]:
    if extent is None or (isinstance(extent, float) and pd.isna(extent)):
        return None
    if isinstance(extent, str):
        try:
            extent = ast.literal_eval(extent)
        except Exception:
            try:
                extent = json.loads(extent)
            except Exception:
                return None
    return extent if isinstance(extent, dict) and "type" in extent else None


def _iter_coords(geom: Dict) -> Iterable[Tuple[float, float]]:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return
    ring = coords[0] if gtype == "Polygon" else (coords[0][0] if gtype == "MultiPolygon" else [])
    for pt in ring:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            yield float(pt[0]), float(pt[1])


def extent_within_us(extent: Any) -> bool:
    geom = _parse_extent(extent)
    if not geom:
        return False
    min_lon, min_lat, max_lon, max_lat = US_BBOX
    try:
        pts = list(_iter_coords(geom))
        return bool(pts) and all(min_lon <= lon <= max_lon and min_lat <= lat <= max_lat for lon, lat in pts)
    except Exception:
        return False


def wrap_extent_for_export(extent: Any) -> Optional[Dict]:
    geom = _parse_extent(extent)
    if not geom:
        return None
    if geom["type"] == "MultiPolygon":
        return geom
    if geom["type"] == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geom.get("coordinates", [])]}
    return None


# ---------------------------------------------------------------------------
# Scrape step
# ---------------------------------------------------------------------------

def _scrape_one(layer_id: int, timeout: int = 20) -> Optional[Dict]:
    try:
        resp = requests.get(LAYER_API.format(layer_id=layer_id), timeout=timeout)
    except Exception as e:
        logger.debug("Layer %s request error: %s", layer_id, e)
        return None
    if resp.status_code != 200:
        return None
    try:
        layer = resp.json()
    except Exception:
        return None

    data = layer.get("data") or {}
    crs = data.get("crs") or {}
    return {
        "layerID": layer.get("id") or layer_id,
        "title": layer.get("title"),
        "type": layer.get("type"),
        "kind": layer.get("kind"),
        "published_at": layer.get("published_at"),
        "created_at": layer.get("created_at"),
        "geometry_type": data.get("geometry_type"),
        "feature_count": data.get("feature_count"),
        "description": layer.get("description"),
        "crs_name": crs.get("name"),
        "crs_id": crs.get("id"),
        "extent": data.get("extent"),
        "group_name": (layer.get("group") or {}).get("name"),
        "num_views": layer.get("num_views"),
        "num_downloads": layer.get("num_downloads"),
        "url": layer.get("url_html"),
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def scrape_layers(start_id: int, end_id: int, threads: int, log_json: Path, out_csv: Path) -> pd.DataFrame:
    logged = load_json_log(log_json)
    ids = [i for i in random.sample(range(start_id, end_id + 1), end_id - start_id + 1) if i not in logged]
    logger.info("Scraping %d ids (%d already logged).", len(ids), len(logged))

    results: List[Dict] = []
    new_logged: Set[int] = set()

    with ThreadPoolExecutor(max_workers=threads) as ex:
        futures = {ex.submit(_scrape_one, lid): lid for lid in ids}
        for fut in as_completed(futures):
            lid = futures[fut]
            new_logged.add(lid)
            try:
                rec = fut.result()
            except Exception as e:
                logger.debug("Layer %s failed: %s", lid, e)
                continue
            if rec:
                results.append(rec)
                logger.info("OK %s: %s", lid, rec.get("title", ""))
            else:
                logger.debug("Skip %s: no data", lid)

    logged |= new_logged
    save_json_log(log_json, logged)

    df = pd.DataFrame(results)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"Scrape complete: {len(df)} layers -> {out_csv}")
    return df


# ---------------------------------------------------------------------------
# Export + download + upload step
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayerTask:
    layer_id: str
    title: str
    extent: Any


def _download_zip(layer_id: str, extent: Any, headers: Dict, poll: int = 30, sleep: int = 5, timeout: int = 60) -> Optional[bytes]:
    export_extent = wrap_extent_for_export(extent)
    if not export_extent:
        logger.info("Skipping %s: invalid extent", layer_id)
        return None

    payload = {
        "crs": "EPSG:4326",
        "items": [{"item": LAYER_API.format(layer_id=layer_id)}],
        "formats": {"vector": GPKG_FORMAT},
        "extent": export_extent,
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        resp = session.post(EXPORT_API, json=payload, timeout=timeout)
    except Exception as e:
        logger.warning("Export POST failed for %s: %s", layer_id, e)
        return None

    if resp.status_code != 201:
        logger.warning("Export POST failed for %s: HTTP %s", layer_id, resp.status_code)
        return None

    export_id = (resp.json() or {}).get("id")
    if not export_id:
        logger.warning("No export id returned for %s", layer_id)
        return None

    for _ in range(poll):
        try:
            state = session.get(f"{EXPORT_API}{export_id}/", timeout=timeout).json().get("state")
        except Exception as e:
            logger.warning("Poll error for %s: %s", layer_id, e)
            time.sleep(sleep)
            continue
        if state == "complete":
            try:
                dl = session.get(f"{EXPORT_API}{export_id}/download/", timeout=timeout)
                return dl.content if dl.status_code == 200 else None
            except Exception as e:
                logger.warning("Download error for %s: %s", layer_id, e)
                return None
        if state == "failed":
            logger.warning("Export failed for %s", layer_id)
            return None
        time.sleep(sleep)

    logger.warning("Export timed out for %s", layer_id)
    return None


def extract_first_gpkg(zip_bytes: bytes) -> Optional[Tuple[str, io.BytesIO]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".gpkg")]
        if not members:
            return None
        name = members[0]
        return name, io.BytesIO(zf.read(name))


async def _upload_gpkg(s3_bucket: str, s3_prefix: str, layer_id: str, title: str, gpkg_name: str, gpkg_bytes: io.BytesIO) -> Dict:
    from aws_utils_4ma.s3_storage_strategy import S3StorageStrategy
    file_name = f"{Path(gpkg_name).stem}.gpkg"
    s3_key = f"{s3_prefix.rstrip('/')}/{file_name}"
    async with S3StorageStrategy(bucket_name=s3_bucket, prefix="") as s3:
        result = await s3.upload_file(file=gpkg_bytes, location=s3_key, content_type=GPKG_MIME)
    if not result or not result.is_valid:
        raise RuntimeError(f"S3 upload failed for {layer_id}")
    return {
        "layer_id": layer_id,
        "title": title,
        "file_name": file_name,
        "s3_url": f"s3://{s3_bucket}/{s3_key}",
        "checksum": result.md5_checksum.hex(),
        "file_size": result.file_size,
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def export_and_upload(
    df: pd.DataFrame,
    headers: Dict,
    uploaded_log: Path,
    s3_bucket: str,
    s3_prefix: str,
    concurrency: int,
    save_zips: Optional[Path] = None,
) -> pd.DataFrame:
    uploaded_before = load_txt_log(uploaded_log)
    sem = asyncio.Semaphore(concurrency)

    tasks = [
        LayerTask(
            layer_id=str(row.get("layerID", "")).strip(),
            title=str(row.get("title") or f"layer_{row.get('layerID', '')}"),
            extent=row.get("extent"),
        )
        for _, row in df.iterrows()
        if str(row.get("layerID", "")).strip()
        and str(row.get("layerID", "")).strip() not in uploaded_before
        and extent_within_us(row.get("extent"))
    ]
    print(f"Prepared {len(tasks)} US-only layers for export+upload.")

    async def _process(task: LayerTask) -> Optional[Dict]:
        async with sem:
            zip_bytes = await asyncio.to_thread(_download_zip, task.layer_id, task.extent, headers)
        if not zip_bytes:
            return None
        if save_zips:
            save_zips.mkdir(parents=True, exist_ok=True)
            (save_zips / f"layer_{task.layer_id}.gpkg.zip").write_bytes(zip_bytes)
        extracted = extract_first_gpkg(zip_bytes)
        if not extracted:
            logger.warning("No .gpkg in zip for %s", task.layer_id)
            return None
        gpkg_name, gpkg_bytes = extracted
        async with sem:
            try:
                rec = await _upload_gpkg(s3_bucket, s3_prefix, task.layer_id, task.title, gpkg_name, gpkg_bytes)
            except Exception as e:
                logger.warning("Upload failed for %s: %s", task.layer_id, e)
                return None
        append_txt_log(uploaded_log, task.layer_id)
        print(f"Uploaded {task.layer_id} -> {rec['s3_url']}")
        return rec

    results = [r for r in await asyncio.gather(*[_process(t) for t in tasks]) if r]
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Koordinates pipeline: scrape -> US filter -> export GPKG -> upload S3")
    p.add_argument("-v", "--verbose", action="count", default=0)

    sub = p.add_subparsers(dest="cmd", required=True)

    # scrape
    s = sub.add_parser("scrape", help="Scrape layer metadata to CSV.")
    s.add_argument("--start-id", type=int, required=True)
    s.add_argument("--end-id", type=int, required=True)
    s.add_argument("--threads", type=int, default=10)
    s.add_argument("--log-json", type=Path, default=Path("koordinates_scraper_log.json"))
    s.add_argument("--out-csv", type=Path, required=True)

    # export-upload
    eu = sub.add_parser("export-upload", help="Export US layers from CSV and upload to S3.")
    eu.add_argument("--in-csv", type=Path, required=True)
    eu.add_argument("--uploaded-log", type=Path, default=Path("uploaded_layers.log"))
    eu.add_argument("--concurrency", type=int, default=8)
    eu.add_argument("--s3-bucket", default="4m-geo-intelligence")
    eu.add_argument("--s3-prefix", default="local_layers_to_fetch/Koordinates")
    eu.add_argument("--save-zips", type=Path, default=None)
    eu.add_argument("--out-summary-csv", type=Path, default=None)

    # all
    a = sub.add_parser("all", help="Scrape then export-upload.")
    a.add_argument("--start-id", type=int, required=True)
    a.add_argument("--end-id", type=int, required=True)
    a.add_argument("--threads", type=int, default=10)
    a.add_argument("--log-json", type=Path, default=Path("koordinates_scraper_log.json"))
    a.add_argument("--out-csv", type=Path, required=True)
    a.add_argument("--uploaded-log", type=Path, default=Path("uploaded_layers.log"))
    a.add_argument("--concurrency", type=int, default=8)
    a.add_argument("--s3-bucket", default="4m-geo-intelligence")
    a.add_argument("--s3-prefix", default="local_layers_to_fetch/Koordinates")
    a.add_argument("--save-zips", type=Path, default=None)
    a.add_argument("--out-summary-csv", type=Path, default=None)

    return p


def main() -> int:
    load_dotenv(Path(__file__).parent / ".env")
    args = build_parser().parse_args()
    setup_logging(args.verbose)

    if args.cmd == "scrape":
        scrape_layers(args.start_id, args.end_id, args.threads, args.log_json, args.out_csv)
        return 0

    # export-upload and all require credentials
    headers = build_headers()

    if args.cmd == "export-upload":
        df = pd.read_csv(args.in_csv)
        summary = asyncio.run(export_and_upload(
            df, headers, args.uploaded_log, args.s3_bucket, args.s3_prefix,
            args.concurrency, args.save_zips,
        ))
        if args.out_summary_csv:
            summary.to_csv(args.out_summary_csv, index=False)
        print(f"Uploaded {len(summary)} layers.")
        return 0

    if args.cmd == "all":
        df = scrape_layers(args.start_id, args.end_id, args.threads, args.log_json, args.out_csv)
        summary = asyncio.run(export_and_upload(
            df, headers, args.uploaded_log, args.s3_bucket, args.s3_prefix,
            args.concurrency, args.save_zips,
        ))
        if args.out_summary_csv:
            summary.to_csv(args.out_summary_csv, index=False)
        print(f"Uploaded {len(summary)} layers.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
