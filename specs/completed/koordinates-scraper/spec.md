---
status: approved
---

# Feature: koordinates-scraper

## Problem

The existing koordinates code in `tools/koordinates/` is a working prototype but
not production-ready: credentials are hardcoded in source files, paths are
hardcoded to a developer's local machine, and the code is scattered across
multiple overlapping scripts with no company-standard structure.

We need a clean, repo-standard tool at `scrapers/koordinates_scraper/` that the
whole GEOINT team can run safely.

## Scenarios

### Run the full pipeline [MVP]

A team member runs the koordinates pipeline end-to-end:
scrape layer metadata for a given ID range → filter to US-only layers →
request GPKG exports → download ZIPs → extract GeoPackages → upload to
`s3://4m-geo-intelligence/local_layers_to_fetch/Koordinates/`.

They set credentials in `.env` (copied from `.env.example`), then run:
```
python pipeline.py all --start-id 101290 --end-id 102290 --out-csv output.csv
```

### Scrape only

A team member only wants the metadata CSV (no export/upload), to review and
filter layers manually before committing to downloads.

```
python pipeline.py scrape --start-id 101290 --end-id 102290 --out-csv output.csv
```

### Export and upload from an existing CSV

A team member already has a filtered CSV and wants to download + upload to S3
without re-scraping.

```
python pipeline.py export-upload --in-csv filtered.csv
```

### Upload from local ZIPs

A team member has ZIPs already downloaded to disk (from a previous partial run)
and only wants to extract GPKGs and upload to S3 — without re-requesting exports.

```
python upload_zips.py --zip-folder ./downloads/
```

## Behaviors

**Works:**
- Pipeline runs all three steps in sequence; skips already-processed layer IDs
  via log files (JSON for scraped, TXT for uploaded)
- Credentials loaded from `.env`; clear error if missing
- US bounding box filter applied automatically before any export request
- Concurrent scraping (threads) and concurrent upload (async + semaphore)

**Edges:**
- Layer ID not found on koordinates → skip silently, log as "no data"
- Export times out after N polls → log warning, continue to next layer
- GPKG ZIP contains no `.gpkg` member → log warning, skip
- Layer already in upload log → skip without re-uploading

**Fails:**
- Missing `.env` / missing credential → print clear error message, exit
- S3 upload fails → log error, continue; report failed count at end
- Invalid extent in CSV → skip layer, log warning

## Boundaries

**In:**
- `scrapers/koordinates_scraper/pipeline.py` — unified CLI (scrape / export-upload / all subcommands)
- `scrapers/koordinates_scraper/upload_zips.py` — standalone: upload local ZIPs to S3
- `scrapers/koordinates_scraper/capability.yaml`
- `scrapers/koordinates_scraper/README.md`
- `scrapers/koordinates_scraper/requirements.txt`
- `scrapers/koordinates_scraper/.env.example`
- New top-level `scrapers/` folder in the repo

**Out:**
- Sector keyword filtering (`koordinates_filterng.py` logic) — kept in `tools/koordinates/` for now, may be integrated later
- Municipality spatial intersection SQL — kept in `tools/koordinates/`
- GPKG FID column removal — kept in `tools/koordinates/`
- Any PostGIS writes
- Non-US layers

## Invariants

**Preserve:**
- No credentials in source code — ever. `.env` only.
- No hardcoded local paths — all paths via CLI args or defaults relative to CWD.
- Existing `tools/koordinates/` folder is untouched by this feature.

**Verify:**
- Running `grep -r "Cookie\|sessionid\|csrftoken" scrapers/koordinates_scraper/` returns nothing.
- `.env` is in `.gitignore`.

## Open Questions

- [x] Where do log files (scraper_log.json, uploaded.log) default to? → CWD, overridable via CLI args.
- [x] S3 bucket and prefix — hardcode defaults or require via args? → Keep same defaults as pipeline (`4m-geo-intelligence` / `local_layers_to_fetch/Koordinates`), overridable via args.
- [x] `upload_zips.py` — keep as separate script or subcommand of pipeline? → Separate script; it's a different entry point (local ZIPs vs API export flow).
