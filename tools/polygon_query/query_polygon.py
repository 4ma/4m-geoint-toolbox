#!/usr/bin/env python3
"""
Utility Owners Polygon Query Tool
==================================
Given one or more polygon WKT geometries, finds all utility owner tickets
whose geometries intersect with the input polygons. Produces:
  - A CSV file per polygon with full ticket + infrastructure data
  - A summary report (printed to console and saved as .txt)
  - (Optional) An AI-enhanced analysis via the Claude API (--ai flag)

Usage:
  python query_polygon.py polygon.wkt
  python query_polygon.py polygon1.wkt polygon2.wkt
  python query_polygon.py --wkt "MultiPolygon(((...)))"
  python query_polygon.py polygon.wkt --ai

The .wkt files should contain raw WKT text (MultiPolygon or Polygon).
"""
import argparse
import ast
import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path
from urllib import parse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ─── Sector / subsector lookups ────────────────────────────────────────────────
SECTOR_NAMES = {
    "00000": "Unknown",
    "10001": "Electricity",
    "10002": "Communication",
    "10003": "Energy (Gas/Oil/Steam)",
    "10004": "Water",
    "10005": "Undetermined",
    "10006": "Sewage",
    "10007": "Reclaimed Water",
}

SUBSECTOR_NAMES = {
    "00000": "Unknown",
    "10101": "Power Lines",
    "10102": "Electricity Conduit",
    "10103": "Lighting Cables",
    "10104": "Electricity Undetermined",
    "10201": "Communication Lines",
    "10202": "Alarm & Signal Lines",
    "10203": "Conduit",
    "10204": "Communication Undetermined",
    "10205": "Telecom",
    "10206": "Fiber",
    "10301": "Gas",
    "10302": "Crude Oil",
    "10303": "Steam",
    "10304": "Hazardous Liquid",
    "10305": "Gaseous Materials",
    "10306": "Oil",
    "10307": "Energy Undetermined",
    "10401": "Drinking Water",
    "10402": "Reclaimed Water",
    "10403": "Sewage",
    "10404": "Storm Water",
    "10405": "Irrigation",
    "10406": "Slurry Lines",
    "10407": "Course",
    "10408": "Brackish Water",
    "10409": "Water Undetermined",
    "10410": "Culvert",
    "10501": "Undetermined",
    "10601": "Sewage",
    "10602": "Drain Lines",
    "10701": "Reclaimed Water",
    "10702": "Reclaimed Water Irrigation",
    "10703": "Slurry",
}

# Sectors considered gas/electricity for the summary
GAS_ELECTRIC_SECTORS = {"10001", "10003"}

# ─── Database ──────────────────────────────────────────────────────────────────
QUERY = text("""
    SELECT
        g.uuid            AS geometry_uuid,
        g.source_name,
        g.source_type,
        g.source_ticket_id,
        g.partition,
        g.subpartition,
        g.ticket_revision,
        g.area_sqm,
        g.longest_geom_line_m,
        g.is_contains_located,
        g.server_created_ts  AS geometry_created_ts,
        g.server_updated_ts  AS geometry_updated_ts,
        ST_AsText(g.geom)    AS geom_wkt,
        d.uuid               AS data_uuid,
        d.contained_infrastructure,
        d.ticket_creation_ts,
        d.ticket_location,
        d.receiving_system
    FROM utility_owners.utility_owners_geometry g
    LEFT JOIN utility_owners.utility_owners_data d
        ON d.utility_owners_geometry_uuid = g.uuid
    WHERE ST_Intersects(g.geom, ST_GeomFromEWKT(:polygon_ewkt))
""")


def load_config():
    """Load DB credentials from .env file or environment variables."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    host = os.environ.get("DB_HOST")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "utility_owners")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")

    if not host or not user or not password:
        print("ERROR: DB_HOST, DB_USER, and DB_PASSWORD must be set in .env or environment.")
        print("       Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    encoded_pw = parse.quote(password)
    url = f"postgresql+psycopg2://{user}:{encoded_pw}@{host}:{port}/{name}"
    return create_engine(url)


def normalize_wkt(raw: str) -> str:
    """
    Accept various WKT inputs and return a valid EWKT string with SRID=4326.
    Handles: raw WKT, EWKT with SRID, extra whitespace, etc.
    """
    raw = raw.strip()
    # Already has SRID prefix
    if raw.upper().startswith("SRID="):
        return raw
    return f"SRID=4326;{raw}"


def safe_name(wkt: str, index: int) -> str:
    """Generate a filesystem-safe name from WKT or fall back to index."""
    # Try to extract a bounding-box-ish hint from the first coordinate
    nums = re.findall(r"-?\d+\.\d+", wkt[:200])
    if len(nums) >= 2:
        lon, lat = nums[0][:8], nums[1][:6]
        return f"polygon_{index + 1}_lon{lon}_lat{lat}"
    return f"polygon_{index + 1}"


def parse_infrastructure(raw_ci):
    """Parse the contained_infrastructure field.

    From the DB it comes as a dict; from CSV it comes as a string repr of a dict.
    """
    if raw_ci is None:
        return {}
    if isinstance(raw_ci, dict):
        return raw_ci
    if isinstance(raw_ci, str):
        try:
            return ast.literal_eval(raw_ci)
        except (ValueError, SyntaxError):
            return {}
    # pandas NaN etc.
    try:
        if pd.isna(raw_ci):
            return {}
    except (TypeError, ValueError):
        pass
    return {}


def resolve_sector(info):
    """Extract human-readable sector/subsector from an infrastructure entry."""
    raw_sector = info.get("sector", "00000")
    raw_subsector = info.get("subsector", "00000")
    sector_id = raw_sector[0] if isinstance(raw_sector, list) else str(raw_sector)
    subsector_id = raw_subsector[0] if isinstance(raw_subsector, list) else str(raw_subsector)
    sector = SECTOR_NAMES.get(sector_id, sector_id)
    subsector = SUBSECTOR_NAMES.get(subsector_id, subsector_id)
    return sector_id, subsector_id, sector, subsector


# ─── Structured data extraction (shared by both reports) ─────────────────────

def extract_structured_data(df: pd.DataFrame):
    """
    Walk every row in the DataFrame and return structured ticket + company data.
    Used by both the deterministic report and the AI report.
    """
    tickets = []
    all_companies = {}  # code -> {name, sectors, responses}
    located_entries = []

    for _, row in df.iterrows():
        ticket_id = row["source_ticket_id"]
        revision = row["ticket_revision"]
        created = str(row["ticket_creation_ts"] or "N/A")
        area = row["area_sqm"]
        has_located = row["is_contains_located"]

        infra = parse_infrastructure(row["contained_infrastructure"])
        companies = []

        for code, info in infra.items():
            org = str(info.get("organization_name") or "N/A")
            resp = str(info.get("last_owner_response") or "N/A")
            resp_ts = str(info.get("last_response_creation_ts") or "—")
            sector_id, subsector_id, sector, subsector = resolve_sector(info)

            companies.append({
                "code": code,
                "organization_name": org,
                "response": resp,
                "response_ts": resp_ts,
                "sector_id": sector_id,
                "subsector_id": subsector_id,
                "sector": sector,
                "subsector": subsector,
            })

            if code not in all_companies:
                all_companies[code] = {"name": org, "sectors": set(), "responses": []}
            all_companies[code]["sectors"].add(sector)
            all_companies[code]["responses"].append(resp)

            if resp == "located":
                located_entries.append({
                    "ticket": ticket_id,
                    "company_code": code,
                    "company_name": org,
                    "response_ts": resp_ts,
                    "sector": sector,
                    "subsector": subsector,
                })

        tickets.append({
            "ticket_id": ticket_id,
            "revision": revision,
            "created": created,
            "area_sqm": float(area) if pd.notna(area) else None,
            "is_contains_located": bool(has_located) if pd.notna(has_located) else False,
            "source_name": row["source_name"],
            "companies": companies,
        })

    return tickets, all_companies, located_entries


# ─── Deterministic report ────────────────────────────────────────────────────

def generate_report(df: pd.DataFrame, polygon_label: str) -> str:
    """Generate a human-readable summary report for one polygon query."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"  UTILITY OWNERS REPORT — {polygon_label}")
    lines.append(f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 70)

    if df.empty:
        lines.append("\n  No tickets found intersecting this polygon.\n")
        return "\n".join(lines)

    tickets, all_companies, located_entries = extract_structured_data(df)

    # ── Overview
    lines.append(f"\n  Total tickets found: {len(df)}")
    sources = df["source_name"].unique()
    lines.append(f"  Sources matched:     {', '.join(sources)}")

    dates = pd.to_datetime(df["ticket_creation_ts"], errors="coerce").dropna()
    if not dates.empty:
        lines.append(f"  Earliest ticket:     {dates.min().strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"  Latest ticket:       {dates.max().strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"  Time span:           {(dates.max() - dates.min()).days} days")

    # ── Per-ticket detail
    lines.append("\n" + "-" * 70)
    lines.append("  TICKET DETAILS")
    lines.append("-" * 70)

    for t in tickets:
        lines.append(f"\n  Ticket: {t['ticket_id']}  (rev {t['revision']})")
        lines.append(f"    Created:          {t['created']}")
        lines.append(f"    Area:             {t['area_sqm']:,.1f} sqm" if t["area_sqm"] else "    Area:             N/A")
        lines.append(f"    Contains located: {t['is_contains_located']}")
        lines.append(f"    Source:           {t['source_name']}")
        lines.append("")

        if not t["companies"]:
            lines.append("    (no infrastructure data)")
            continue

        lines.append(f"    {'Code':<20s} {'Organization':<35s} {'Response':<16s} {'Response Time':<28s} {'Sector':<25s} {'Subsector'}")
        lines.append(f"    {'─' * 20} {'─' * 35} {'─' * 16} {'─' * 28} {'─' * 25} {'─' * 20}")

        for c in t["companies"]:
            lines.append(f"    {c['code']:<20s} {c['organization_name']:<35s} {c['response']:<16s} {c['response_ts']:<28s} {c['sector']:<25s} {c['subsector']}")

    # ── Summary: located responses
    lines.append("\n" + "=" * 70)
    lines.append("  SUMMARY — LOCATED RESPONSES")
    lines.append("=" * 70)

    if not located_entries:
        lines.append("\n  No companies responded 'located' for any ticket in this polygon.")
    else:
        lines.append(f"\n  {len(located_entries)} 'located' response(s) found:\n")
        for e in located_entries:
            lines.append(f"    Ticket {e['ticket']}:")
            lines.append(f"      Company:   {e['company_name']} ({e['company_code']})")
            lines.append(f"      Sector:    {e['sector']} / {e['subsector']}")
            lines.append(f"      Responded: {e['response_ts']}")
            lines.append("")

    # ── Summary: gas / electricity
    lines.append("=" * 70)
    lines.append("  SUMMARY — GAS / ELECTRICITY")
    lines.append("=" * 70)

    gas_elec_sector_names = {SECTOR_NAMES.get(s, s) for s in GAS_ELECTRIC_SECTORS}
    gas_elec_located = [e for e in located_entries if e["sector"] in gas_elec_sector_names]

    if gas_elec_located:
        lines.append(f"\n  {len(gas_elec_located)} gas/electricity company responded 'located':\n")
        for e in gas_elec_located:
            lines.append(f"    - {e['company_name']} on ticket {e['ticket']} at {e['response_ts']}")
    else:
        lines.append("\n  No gas/electricity companies responded 'located' in this polygon.")

    # ── All unique companies
    lines.append("\n" + "=" * 70)
    lines.append("  ALL UTILITY COMPANIES IN THIS AREA")
    lines.append("=" * 70)
    lines.append(f"\n  {'Code':<20s} {'Organization':<35s} {'Sector(s)':<30s} {'Responses'}")
    lines.append(f"  {'─' * 20} {'─' * 35} {'─' * 30} {'─' * 30}")
    for code, info in sorted(all_companies.items()):
        resp_counts = {}
        for r in info["responses"]:
            resp_counts[r] = resp_counts.get(r, 0) + 1
        resp_str = ", ".join(f"{r}({c})" for r, c in sorted(resp_counts.items()))
        sectors_str = ", ".join(sorted(info["sectors"]))
        lines.append(f"  {code:<20s} {info['name']:<35s} {sectors_str:<30s} {resp_str}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


# ─── AI-enhanced report (Claude API) ─────────────────────────────────────────

AI_SYSTEM_PROMPT = """\
You are an infrastructure analyst working for a geospatial data company (4map).
You help field teams understand utility-owner ticket data for project polygons.

You will receive structured data about utility-owner tickets that intersect with
a geographic polygon. Each ticket contains a list of utility companies, their
sector codes, and their responses (located / clear / no_response / etc.).

Your job is to produce a clear, actionable Markdown report. Use your knowledge
of US utility companies to go BEYOND the raw sector codes — for example:
- "Imperial Irrigation" is an electric + water utility even if coded as just electric
- "Pacific Gas & Electric" (PG&E) handles both gas and electricity
- "SDG&E" (San Diego Gas & Electric) is gas + electricity even if coded "undetermined"
- "ATT Transmission" is fiber/telecom, not gas or electricity
- "Comcast" is cable/communication

Structure your report as follows:

## Summary
2-3 sentence overview: how many tickets, date range, key finding.

## Sector Breakdown
Group companies by what they ACTUALLY do (use your judgment, not just the codes):
- **Electricity**: ...
- **Gas / Energy**: ...
- **Telecom / Fiber / Cable**: ...
- **Water / Irrigation**: ...
- **Sewage / Drainage**: ...
- **Other / Undetermined**: ...

For each company, state: name, response across tickets, and response timestamps.

## Located Infrastructure
Which companies confirmed they have infrastructure here? When did they respond?
If none, say so clearly.

## Risk Assessment
- Are there gas or electricity companies with "located" responses? (high relevance for road marks)
- Are there companies with "no_response"? (unknown risk — infrastructure may exist but wasn't confirmed)
- How old are the tickets? Could the situation have changed?
- Are there large-area tickets vs small-area tickets? What might that imply?

## Road Mark Relevance
Given the hypothesis that road marks correlate with utility tickets:
- Is there evidence of gas/electric utility work that would leave road marks?
- Could detected marks be false positives given the ticket history?
- What would you recommend investigating further?

## Slack-Ready Summary
A short (5-8 lines) copy-pasteable block for sharing on Slack, with the key facts.
Use plain text, no markdown. Keep it punchy.
"""


def generate_ai_report(df: pd.DataFrame, polygon_label: str) -> str:
    """Call the Claude API to produce an AI-enhanced analysis of the ticket data."""
    try:
        import anthropic
    except ImportError:
        return (
            "ERROR: The 'anthropic' package is required for --ai reports.\n"
            "Install it with: pip install anthropic\n"
            "And set ANTHROPIC_API_KEY in your .env file."
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "ERROR: ANTHROPIC_API_KEY not set.\n"
            "Add it to your .env file or set it as an environment variable."
        )

    if df.empty:
        return f"# AI Report — {polygon_label}\n\nNo tickets found. Nothing to analyze."

    tickets, all_companies, located_entries = extract_structured_data(df)

    # Build a clean JSON payload for Claude (no WKT blobs, just the useful bits)
    dates = pd.to_datetime(df["ticket_creation_ts"], errors="coerce").dropna()
    payload = {
        "polygon_label": polygon_label,
        "total_tickets": len(tickets),
        "sources": list(df["source_name"].unique()),
        "date_range": {
            "earliest": dates.min().isoformat() if not dates.empty else None,
            "latest": dates.max().isoformat() if not dates.empty else None,
            "span_days": int((dates.max() - dates.min()).days) if not dates.empty else None,
        },
        "tickets": [
            {
                "ticket_id": t["ticket_id"],
                "revision": t["revision"],
                "created": t["created"],
                "area_sqm": t["area_sqm"],
                "is_contains_located": t["is_contains_located"],
                "source": t["source_name"],
                "companies": [
                    {
                        "code": c["code"],
                        "name": c["organization_name"],
                        "response": c["response"],
                        "response_ts": c["response_ts"],
                        "sector_code": c["sector_id"],
                        "sector_label": c["sector"],
                        "subsector_code": c["subsector_id"],
                        "subsector_label": c["subsector"],
                    }
                    for c in t["companies"]
                ],
            }
            for t in tickets
        ],
        "located_entries": located_entries,
        "unique_companies": {
            code: {
                "name": info["name"],
                "sectors": sorted(info["sectors"]),
                "response_distribution": dict(
                    sorted(
                        {r: info["responses"].count(r) for r in set(info["responses"])}.items()
                    )
                ),
            }
            for code, info in sorted(all_companies.items())
        },
    }

    print("  Calling Claude API for AI analysis...")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=AI_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Analyze this utility-owner ticket data for polygon **{polygon_label}** "
                    f"and produce your report.\n\n"
                    f"```json\n{json.dumps(payload, indent=2, default=str)}\n```"
                ),
            }
        ],
    )

    ai_text = message.content[0].text
    header = (
        f"# AI-Enhanced Report — {polygon_label}\n"
        f"_Generated by Claude ({message.model}) "
        f"on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_\n\n"
    )
    return header + ai_text


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Query utility owners tickets intersecting with polygon(s).",
        epilog="Examples:\n"
               "  python query_polygon.py polygon.wkt\n"
               "  python query_polygon.py --wkt \"MultiPolygon(((...)))\"\n"
               "  python query_polygon.py p1.wkt p2.wkt --output-dir ./results\n"
               "  python query_polygon.py polygon.wkt --ai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "wkt_files", nargs="*",
        help="Path(s) to .wkt file(s) containing polygon WKT geometry",
    )
    parser.add_argument(
        "--wkt", action="append", default=[],
        help="Inline WKT string (can be used multiple times)",
    )
    parser.add_argument(
        "--output-dir", "-o", default=".",
        help="Directory to write CSV and report files (default: current dir)",
    )
    parser.add_argument(
        "--name", action="append", default=[],
        help="Friendly name for each polygon (in same order as inputs)",
    )
    parser.add_argument(
        "--ai", action="store_true",
        help="Generate an AI-enhanced report using the Claude API (requires ANTHROPIC_API_KEY)",
    )
    args = parser.parse_args()

    # Collect all polygon WKTs
    polygons = []  # list of (label, ewkt)

    for i, fpath in enumerate(args.wkt_files):
        p = Path(fpath)
        if not p.exists():
            print(f"ERROR: File not found: {fpath}")
            sys.exit(1)
        raw = p.read_text()
        label = args.name[i] if i < len(args.name) else p.stem
        polygons.append((label, normalize_wkt(raw)))

    for i, wkt_str in enumerate(args.wkt):
        idx = len(args.wkt_files) + i
        label = args.name[idx] if idx < len(args.name) else safe_name(wkt_str, idx)
        polygons.append((label, normalize_wkt(wkt_str)))

    if not polygons:
        parser.print_help()
        print("\nERROR: Provide at least one polygon (.wkt file or --wkt string).")
        sys.exit(1)

    # Ensure output dir exists
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Connect
    engine = load_config()
    print(f"Connected to database.\n")

    # Process each polygon
    for i, (label, ewkt) in enumerate(polygons):
        print(f"[{i + 1}/{len(polygons)}] Querying: {label} ...")
        df = pd.read_sql(QUERY, engine, params={"polygon_ewkt": ewkt})

        # Save CSV
        csv_path = out_dir / f"{label}.csv"
        df.to_csv(csv_path, index=False)
        print(f"  CSV: {csv_path}  ({len(df)} rows)")

        # Generate & save deterministic report
        report = generate_report(df, label)
        report_path = out_dir / f"{label}_report.txt"
        report_path.write_text(report)
        print(f"  Report: {report_path}")

        # Print report to console
        print(report)

        # AI-enhanced report
        if args.ai:
            ai_report = generate_ai_report(df, label)
            ai_path = out_dir / f"{label}_ai_report.md"
            ai_path.write_text(ai_report)
            print(f"  AI Report: {ai_path}")
            print(ai_report)

        print()

    print("All done.")


if __name__ == "__main__":
    main()
