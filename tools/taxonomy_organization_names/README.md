# Organization Names Extraction Tool

Extract all unique organization names from any MySQL ticket table in `amiggi4mdb`.
Outputs a single-column CSV ready for taxonomy building, deduplication, or classification.

---

## What This Tool Does

**Problem it solves:** You need a clean list of every organization name that appears
in a state's 811 ticket data (Ohio, California, Texas, Florida, etc.) — for building
a taxonomy, populating a lookup table, or normalizing org names across states.

**What it produces:**
- A CSV with one column (`organization_name`) containing every unique name found

**What it queries:**
- Any table in `amiggi4mdb` that has an `F_ID` integer primary key and a JSON column
  containing an array of names at a configurable path
- Defaults: table column `F_DETAILS`, JSON path `$.responses[*].name`

**Typical use cases:**
- "Give me all org names from the Ohio ticket data"
- "Build a taxonomy CSV from T_CA_TICKET"
- "What organizations appear in the Texas data?"
- "Extract all unique names from T_FL_TICKET for deduplication"

---

## Quick Start

```bash
cd tools/taxonomy_organization_names

# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up credentials
cp .env.example .env
# Edit .env — fill in DB_HOST, DB_USER, DB_PASSWORD

# 3. Run for Ohio
python extract_org_names.py --table T_OH_TICKET

# 4. Run for California with a custom output filename
python extract_org_names.py --table T_CA_TICKET --output ca_orgs.csv
```

---

## Usage

```
python extract_org_names.py --table <TABLE_NAME> [OPTIONS]
```

### Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--table` | `-t` | **required** | MySQL table in `amiggi4mdb` (e.g. `T_OH_TICKET`) |
| `--json-path` | `-j` | `$.responses[*].name` | JSON path to extract names from |
| `--field` | `-f` | `F_DETAILS` | JSON column in the table |
| `--min-id` | | `1` | Starting `F_ID` |
| `--max-id` | | auto | Ending `F_ID` — auto-detected via `MAX(F_ID)` |
| `--chunk-size` | | `50000` | Number of IDs to process per batch |
| `--output` | `-o` | `<table>_organizations.csv` | Output CSV filename |

### Examples

**Ohio (defaults):**
```bash
python extract_org_names.py --table T_OH_TICKET
# Output: t_oh_ticket_organizations.csv
```

**California with custom output:**
```bash
python extract_org_names.py --table T_CA_TICKET --output ca_orgs.csv
```

**Texas, bounded ID range:**
```bash
python extract_org_names.py --table T_TX_TICKET --min-id 1 --max-id 5000000
```

**Florida, smaller batches (for slower connections):**
```bash
python extract_org_names.py --table T_FL_TICKET --chunk-size 25000
```

**Custom JSON path or field:**
```bash
python extract_org_names.py --table T_OH_TICKET \
  --field F_DETAILS \
  --json-path '$.responses[*].name'
```

---

## Output

A CSV file with a single column:

```
organization_name
ATMOS ENERGY
CenterPoint Energy
City of Houston Water
...
```

One row per unique name, preserving first-seen order. Duplicates are dropped.

---

## Credentials

Credentials are loaded from a `.env` file. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill in:
```
DB_HOST=your_mysql_host
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=amiggi4mdb        # optional, this is the default
```

The `.env` file is git-ignored and never committed.

---

## Checkpoint / Resume

For large tables (millions of rows) the tool saves a checkpoint every 10 batches.
If the run is interrupted, simply re-run the same command — it will pick up from
the last saved checkpoint automatically.

Checkpoint files are named `<TABLE>_checkpoint.txt` and are automatically deleted
on successful completion.

---

## Known Tables

| Table | State |
|-------|-------|
| `T_OH_TICKET` | Ohio |
| `T_CA_TICKET` | California |
| `T_TX_TICKET` | Texas |
| `T_FL_TICKET` | Florida |

Any table with an `F_ID` integer primary key and a JSON column works — use
`--field` and `--json-path` to point to the right data.
