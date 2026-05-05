# Koordinates Scraper

Scrapes layer metadata from koordinates.com, filters to US-only layers, exports GeoPackages, and uploads them to S3.

## Setup

```bash
cd scrapers/koordinates_scraper
pip install -r requirements.txt
cp .env.example .env   # fill in your Koordinates credentials
```

### Credentials

Get your credentials from koordinates.com:
1. Log in to koordinates.com in your browser
2. Open DevTools → Network → pick any request → copy the `Cookie` header value
3. Copy the `X-CSRFToken` header value from the same request
4. Paste both into `.env`

**Note:** Session cookies expire. If you get auth errors, refresh both values.

## Usage

### Full pipeline (scrape → filter → export → upload to S3)

```bash
python pipeline.py all \
  --start-id 101290 --end-id 102290 \
  --out-csv output.csv
```

### Scrape metadata only (no download, no S3)

```bash
python pipeline.py scrape \
  --start-id 101290 --end-id 102290 \
  --out-csv output.csv
```

### Export and upload from an existing CSV

```bash
python pipeline.py export-upload --in-csv output.csv
```

### Upload pre-downloaded local ZIPs to S3

Use this when you already have `.gpkg.zip` files on disk from a previous run:

```bash
python upload_zips.py --zip-folder ./downloads/
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--threads` | 10 | Scrape concurrency |
| `--concurrency` | 8 | Export/upload concurrency |
| `--s3-bucket` | `4m-geo-intelligence` | Target S3 bucket |
| `--s3-prefix` | `local_layers_to_fetch/Koordinates` | S3 key prefix |
| `--log-json` | `koordinates_scraper_log.json` | Tracks scraped IDs (avoids re-scraping) |
| `--uploaded-log` | `uploaded_layers.log` | Tracks uploaded IDs (avoids re-uploading) |
| `--out-csv` | *(required for scrape/all)* | Output CSV path |
| `--in-csv` | *(required for export-upload)* | Input CSV path |
| `--save-zips` | *(none)* | Optional folder to save downloaded ZIPs locally |

## Output

- **CSV** — layer metadata: `layerID`, `title`, `geometry_type`, `extent`, `feature_count`, etc.
- **S3** — GeoPackage files at `s3://4m-geo-intelligence/local_layers_to_fetch/Koordinates/`
- **Logs** — `koordinates_scraper_log.json` and `uploaded_layers.log` track progress so runs are resumable
