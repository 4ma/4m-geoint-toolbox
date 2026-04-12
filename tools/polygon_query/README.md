# Polygon Query Tool — Utility Owners

Query the utility owners production database for all tickets whose geometries
intersect with one or more input polygons. Outputs a CSV (raw data), a
deterministic text report, and optionally an AI-enhanced analysis.

---

## What This Tool Does

**Problem it solves:** Someone gives you a project polygon (WKT) and asks
"which utility owners are in this area?", "is there gas/electricity located?",
"how far back do tickets go?", or "could these road marks be false positives?".

**What it produces:**
1. **CSV** — full raw data per polygon (geometry, infrastructure JSON, timestamps)
2. **Text report** — deterministic breakdown of every ticket and company response
3. **AI report** (optional `--ai` flag) — Claude analyzes the data, classifies
   companies by what they actually do (not just sector codes), assesses risk,
   and writes a Slack-ready summary

**What it queries:**
- `utility_owners.utility_owners_geometry` — spatial intersection via PostGIS
- `utility_owners.utility_owners_data` — infrastructure details, company responses
- Searches across ALL sources (California, Texas, Florida, etc.) — not limited
  to a specific state

**Typical use cases:**
- "Find all utility tickets in this Caltrans project boundary"
- "Is there gas/electricity located in this polygon?"
- "How far back do tickets go for this area?"
- "Are detected road marks in this area likely false positives?"
- "Give me a CSV of all utility data for these project polygons"
- "Who responded 'located' in this region?"

---

## Quick Start

```bash
cd polygon_query_tool

# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up credentials
cp .env.example .env
# Edit .env — fill in DB_USER and DB_PASSWORD
# (Optional: add ANTHROPIC_API_KEY for --ai reports)

# 3. Run with a .wkt file
python query_polygon.py examples/CA-Caltrans-00376_D11-IMP-008.wkt

# 4. Run with AI analysis
python query_polygon.py examples/CA-Caltrans-00376_D11-IMP-008.wkt --ai

# 5. Run multiple polygons at once
python query_polygon.py examples/*.wkt --output-dir ./results
```

---

## Usage

```
python query_polygon.py [OPTIONS] [WKT_FILES...]
```

### Arguments

| Option | Description |
|--------|-------------|
| `WKT_FILES` | One or more `.wkt` files containing polygon WKT geometry |
| `--wkt "..."` | Inline WKT string (can be repeated for multiple polygons) |
| `--name NAME` | Friendly name for each polygon (used in output filenames) |
| `--output-dir DIR` | Directory for output files (default: current directory) |
| `--ai` | Enable AI-enhanced report via Claude API |

### Examples

**Single file:**
```bash
python query_polygon.py my_polygon.wkt
```

**Multiple files with custom names:**
```bash
python query_polygon.py site_a.wkt site_b.wkt \
  --name "Site-A-Highway101" \
  --name "Site-B-Interstate5" \
  --output-dir ./results
```

**Inline WKT (no file needed):**
```bash
python query_polygon.py --wkt "MultiPolygon (((-116.03 32.72, -116.02 32.72, -116.02 32.73, -116.03 32.73, -116.03 32.72)))"
```

**With AI analysis:**
```bash
python query_polygon.py polygon.wkt --ai
```

---

## Output Files

For each polygon the tool generates:

| File | Format | Contents |
|------|--------|----------|
| `<name>.csv` | CSV | Full data: geometry_uuid, source_name, ticket_id, revision, area_sqm, contained_infrastructure (JSON), ticket_creation_ts, geom_wkt, etc. |
| `<name>_report.txt` | Text | Deterministic report: ticket list, company responses, located summary, gas/electricity summary, all companies |
| `<name>_ai_report.md` | Markdown | (Only with `--ai`) AI-generated analysis with sector classification, risk assessment, and Slack-ready summary |

---

## AI-Enhanced Reports (`--ai`)

When you pass the `--ai` flag, the tool sends the structured ticket data to
the Claude API and gets back an analysis that goes beyond raw sector codes.

**What Claude adds:**
- **Smart sector classification** — uses company name recognition (e.g. "PG&E"
  is gas+electricity even if coded as just one; "SDG&E" is gas+electric even if
  coded "undetermined")
- **Risk assessment** — flags no_response companies (unknown risk), old tickets
  (stale data), and large vs small area implications
- **Road mark relevance** — evaluates whether detected road marks could be false
  positives based on the utility history
- **Slack-ready summary** — copy-paste block for team communication

**Requirements:**
- `anthropic` Python package (included in requirements.txt)
- `ANTHROPIC_API_KEY` in your `.env` file

The AI report is saved as a `.md` file alongside the other outputs.

---

## Credentials

Credentials are loaded from a `.env` file. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill in:
```
DB_USER=your_username
DB_PASSWORD=your_password
ANTHROPIC_API_KEY=sk-ant-...   # only needed for --ai
```

The `.env` file is git-ignored. You can also set environment variables directly.

---

## WKT File Format

A `.wkt` file is plain text containing a WKT geometry. Supported formats:

```
MultiPolygon (((-116.03 32.72, -116.02 32.72, ...)))
```
```
Polygon ((-116.03 32.72, -116.02 32.72, ...))
```
```
SRID=4326;MultiPolygon (((-116.03 32.72, ...)))
```

Copy WKT directly from QGIS, PostGIS, or any GIS tool. Save as `.wkt` file.

---

## Report Interpretation

### Company Responses

| Response | Meaning |
|----------|---------|
| `located` | Company marked their infrastructure in the area |
| `clear` | Company confirmed NO infrastructure here |
| `no_response` | Company did not respond (unknown risk) |
| `no_markings_requested` | No markings were requested |
| `undetermined` | Response unclear |

### Sector Codes

| Code | Sector | Includes |
|------|--------|----------|
| 10001 | Electricity | Power lines, conduit, lighting |
| 10002 | Communication | Telecom, fiber, cable, alarm lines |
| 10003 | Energy | Gas, oil, steam, hazardous liquid |
| 10004 | Water | Drinking, storm, irrigation, reclaimed |
| 10005 | Undetermined | Not classified |
| 10006 | Sewage | Sewer, drain lines |
| 10007 | Reclaimed Water | Reclaimed, irrigation |

Note: sector codes can be unreliable. The `--ai` flag uses Claude's knowledge
of utility company names to provide more accurate classification.
