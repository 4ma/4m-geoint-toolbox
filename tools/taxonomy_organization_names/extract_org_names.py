#!/usr/bin/env python3
"""
extract_org_names.py — Extract unique organization names from any MySQL ticket table in amiggi4mdb.

Usage:
    python extract_org_names.py --table T_OH_TICKET
    python extract_org_names.py --table T_CA_TICKET --output ca_orgs.csv
    python extract_org_names.py --table T_TX_TICKET --json-path '$.responses[*].name' --max-id 5000000
"""
import argparse
import json
import csv
import re
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CHUNK_SIZE = 50_000
DEFAULT_JSON_PATH = "$.responses[*].name"
DEFAULT_JSON_FIELD = "F_DETAILS"

# Allowed characters in table/field names — prevent SQL injection
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


# ============================================================================
# HELPERS
# ============================================================================

def log(message):
    """Print a timestamped message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def validate_identifier(name, label):
    """Raise if name contains characters that could be used for SQL injection."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Invalid {label} '{name}' — only letters, digits, and underscores are allowed.")


def get_db_config():
    """Load DB credentials from environment / .env file."""
    missing = [k for k in ("DB_HOST", "DB_USER", "DB_PASSWORD") if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your credentials."
        )
    return {
        "host": os.environ["DB_HOST"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "database": os.getenv("DB_NAME", "amiggi4mdb"),
    }


def get_max_id(conn, table):
    """Query MAX(F_ID) from the target table."""
    cur = conn.cursor()
    cur.execute(f"SELECT MAX(F_ID) FROM `{table}`")
    row = cur.fetchone()
    cur.close()
    return row[0] if row and row[0] else 0


def extract_names_from_json(json_list_str):
    """Parse a MySQL JSON_EXTRACT result (a JSON array of strings) into a flat list."""
    try:
        names = json.loads(json_list_str)
        if isinstance(names, list):
            return [str(n).strip() for n in names if n]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


# ============================================================================
# CHECKPOINT (resume interrupted runs)
# ============================================================================

def _checkpoint_path(table):
    return f"{table}_checkpoint.txt"


def load_checkpoint(table):
    path = _checkpoint_path(table)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                lines = f.readlines()
                return int(lines[0].strip()), int(lines[1].strip())
        except Exception:
            pass
    return None, 0


def save_checkpoint(table, last_id, org_count):
    with open(_checkpoint_path(table), "w") as f:
        f.write(f"{last_id}\n{org_count}\n")


def remove_checkpoint(table):
    path = _checkpoint_path(table)
    if os.path.exists(path):
        os.remove(path)


# ============================================================================
# EXTRACTION
# ============================================================================

def extract_org_names(conn, table, json_field, json_path, min_id, max_id, chunk_size):
    """
    Iterate over the table in F_ID batches, extract names from the JSON column,
    and return a deduplicated list preserving first-seen order.
    """
    try:
        cur = conn.cursor()
        cur.execute("SET SESSION MAX_EXECUTION_TIME = 0")
        cur.close()
    except Exception:
        pass

    checkpoint_id, _ = load_checkpoint(table)
    seen = set()
    unique_orgs = []
    current = (checkpoint_id + 1) if checkpoint_id is not None else min_id
    batch_num = 0

    log(f"Starting extraction from {table} (F_ID {current} → {max_id})")

    while current <= max_id:
        batch_num += 1
        batch_end = current + chunk_size - 1

        cur = conn.cursor()
        # json_path is passed as a parameter — table/field names are validated above
        cur.execute(
            f"""
            SELECT `{json_field}` -> %s
            FROM `{table}`
            WHERE F_ID BETWEEN %s AND %s
              AND JSON_VALID(`{json_field}`)
              AND `{json_field}` -> %s IS NOT NULL
            """,
            (json_path, current, batch_end, json_path),
        )
        rows = cur.fetchall()
        cur.close()

        batch_new = 0
        for (json_list_str,) in rows:
            if not json_list_str:
                continue
            for name in extract_names_from_json(json_list_str):
                if name not in seen:
                    seen.add(name)
                    unique_orgs.append(name)
                    batch_new += 1

        log(
            f"Batch {batch_num}: ID {current}-{batch_end} | "
            f"Rows: {len(rows)} | New: {batch_new} | Total unique: {len(unique_orgs)}"
        )

        if batch_num % 10 == 0:
            save_checkpoint(table, batch_end, len(unique_orgs))

        current = batch_end + 1

    return unique_orgs


# ============================================================================
# OUTPUT
# ============================================================================

def write_csv(org_names, filename):
    log(f"Writing {len(org_names)} unique names to {filename}")
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["organization_name"])
        for name in org_names:
            writer.writerow([name])


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract unique organization names from a MySQL ticket table in amiggi4mdb.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extract_org_names.py --table T_OH_TICKET
  python extract_org_names.py --table T_CA_TICKET --output ca_orgs.csv
  python extract_org_names.py --table T_TX_TICKET --json-path '$.responses[*].name' --max-id 5000000
  python extract_org_names.py --table T_FL_TICKET --chunk-size 25000
        """,
    )
    parser.add_argument(
        "--table", "-t", required=True,
        help="MySQL table to query in amiggi4mdb (e.g. T_OH_TICKET, T_CA_TICKET, T_TX_TICKET)",
    )
    parser.add_argument(
        "--json-path", "-j", default=DEFAULT_JSON_PATH,
        help=f"JSON path expression to extract names from (default: {DEFAULT_JSON_PATH})",
    )
    parser.add_argument(
        "--field", "-f", default=DEFAULT_JSON_FIELD,
        help=f"JSON column in the table (default: {DEFAULT_JSON_FIELD})",
    )
    parser.add_argument(
        "--min-id", type=int, default=1,
        help="Starting F_ID (default: 1)",
    )
    parser.add_argument(
        "--max-id", type=int, default=None,
        help="Ending F_ID — auto-detected via MAX(F_ID) if not provided",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
        help=f"Number of IDs to process per batch (default: {DEFAULT_CHUNK_SIZE})",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output CSV filename (default: <table>_organizations.csv)",
    )
    args = parser.parse_args()

    # Validate identifiers before they ever touch a query
    validate_identifier(args.table, "table")
    validate_identifier(args.field, "field")

    output_file = args.output or f"{args.table.lower()}_organizations.csv"

    log(f"Connecting to database...")
    conn = mysql.connector.connect(**get_db_config())

    max_id = args.max_id
    if max_id is None:
        log(f"Auto-detecting MAX(F_ID) for {args.table}...")
        max_id = get_max_id(conn, args.table)
        log(f"MAX(F_ID) = {max_id:,}")

    log(f"Table: {args.table} | Field: {args.field} | JSON path: {args.json_path}")
    log(f"ID range: {args.min_id:,} → {max_id:,} | Chunk size: {args.chunk_size:,}")

    try:
        orgs = extract_org_names(
            conn,
            table=args.table,
            json_field=args.field,
            json_path=args.json_path,
            min_id=args.min_id,
            max_id=max_id,
            chunk_size=args.chunk_size,
        )
    finally:
        conn.close()

    write_csv(orgs, output_file)
    remove_checkpoint(args.table)
    log(f"COMPLETE — {len(orgs):,} unique organization names written to {output_file}")


if __name__ == "__main__":
    main()
