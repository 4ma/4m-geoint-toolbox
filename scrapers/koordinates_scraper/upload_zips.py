#!/usr/bin/env python3
"""
Upload pre-downloaded koordinates ZIP files to S3.

Use this when you already have layer_<id>.gpkg.zip files on disk
(e.g. from a previous partial run) and want to extract GPKGs and
upload them to S3 without re-requesting exports from the API.

Usage:
  python upload_zips.py --zip-folder ./downloads/
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

GPKG_MIME = "application/geopackage+sqlite3"


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------

def load_uploaded_ids(log_path: Path) -> set:
    if not log_path.exists():
        return set()
    return {line.strip() for line in log_path.read_text().splitlines() if line.strip()}


def append_uploaded_id(log_path: Path, layer_id: str) -> None:
    with log_path.open("a") as f:
        f.write(f"{layer_id}\n")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def extract_first_gpkg(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".gpkg")]
        if not members:
            return None, None
        name = members[0]
        return name, io.BytesIO(zf.read(name))


async def upload_gpkg(s3_bucket: str, s3_prefix: str, layer_id: str, gpkg_name: str, gpkg_bytes: io.BytesIO) -> Dict:
    from aws_utils_4ma.s3_storage_strategy import S3StorageStrategy
    file_name = f"{Path(gpkg_name).stem}.gpkg"
    s3_key = f"{s3_prefix.rstrip('/')}/{file_name}"
    async with S3StorageStrategy(bucket_name=s3_bucket, prefix="") as s3:
        result = await s3.upload_file(file=gpkg_bytes, location=s3_key, content_type=GPKG_MIME)
    if not result or not result.is_valid:
        raise RuntimeError(f"S3 upload failed for {layer_id}")
    return {
        "layer_id": layer_id,
        "file_name": file_name,
        "s3_url": f"s3://{s3_bucket}/{s3_key}",
        "checksum": result.md5_checksum.hex(),
        "file_size": result.file_size,
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def process_zip(zip_path: Path, sem: asyncio.Semaphore, uploaded_before: set, s3_bucket: str, s3_prefix: str, log_path: Path) -> Optional[Dict]:
    layer_id = zip_path.stem.replace("layer_", "", 1)

    if layer_id in uploaded_before:
        print(f"Skipping already uploaded: {layer_id}")
        return None

    gpkg_name, gpkg_bytes = extract_first_gpkg(zip_path)
    if not gpkg_name:
        print(f"Warning: no .gpkg found in {zip_path.name} — skipping")
        return None

    try:
        async with sem:
            rec = await upload_gpkg(s3_bucket, s3_prefix, layer_id, gpkg_name, gpkg_bytes)
        append_uploaded_id(log_path, layer_id)
        print(f"Uploaded {layer_id} -> {rec['s3_url']}")
        return rec
    except Exception as e:
        print(f"Error uploading {zip_path.name}: {e}")
        return None


async def upload_all(zip_folder: Path, s3_bucket: str, s3_prefix: str, concurrency: int, log_path: Path) -> pd.DataFrame:
    uploaded_before = load_uploaded_ids(log_path)
    print(f"Previously uploaded: {len(uploaded_before)} layer(s)")

    zips = sorted(zip_folder.glob("layer_*.zip"))
    if not zips:
        print(f"No ZIP files found in {zip_folder}")
        return pd.DataFrame()

    sem = asyncio.Semaphore(concurrency)
    results = [
        r for r in await asyncio.gather(*[
            process_zip(z, sem, uploaded_before, s3_bucket, s3_prefix, log_path)
            for z in zips
        ])
        if r
    ]
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Upload pre-downloaded koordinates ZIPs to S3.")
    p.add_argument("--zip-folder", type=Path, required=True, help="Folder containing layer_<id>.gpkg.zip files")
    p.add_argument("--s3-bucket", default="4m-geo-intelligence")
    p.add_argument("--s3-prefix", default="local_layers_to_fetch/Koordinates")
    p.add_argument("--concurrency", type=int, default=10)
    p.add_argument("--uploaded-log", type=Path, default=Path("uploaded_layers.log"))
    p.add_argument("--out-summary-csv", type=Path, default=None, help="Optional: write upload summary to CSV")
    return p


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()

    if not args.zip_folder.exists():
        print(f"ERROR: zip-folder does not exist: {args.zip_folder}")
        sys.exit(1)

    start = datetime.now()
    df = asyncio.run(upload_all(args.zip_folder, args.s3_bucket, args.s3_prefix, args.concurrency, args.uploaded_log))
    duration = (datetime.now() - start).total_seconds()

    print(f"\nDone in {duration:.1f}s — {len(df)} new layers uploaded.")

    if not df.empty and args.out_summary_csv:
        args.out_summary_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out_summary_csv, index=False)
        print(f"Summary saved to {args.out_summary_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
