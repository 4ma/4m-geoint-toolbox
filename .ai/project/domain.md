# Domain

## Who Uses This

The GEOINT team at 4map. Day-to-day requests come from:
- Field teams asking "what utility owners are inside this project polygon?"
- Analysts validating whether road-mark detection results correlate with known underground utilities
- Internal Slack threads that need a quick CSV or text summary, not a full pipeline run

## Data the Team Works With

- **811 ticket data** — utility-owner tickets from US state One-Call systems (California, Texas, Florida, Pennsylvania, …) stored in PostgreSQL/PostGIS. Each ticket has a polygon, a sector code, and an owner identity.
- **Polygon geometries** — project boundaries, typically supplied as WKT (from QGIS or PostGIS) or GeoJSON.
- **Road-mark detections** — outputs of ML models that identify painted utility marks; correlated against tickets/owners.
- **Organization taxonomies** — owner-name normalization across sources (`amiggi4mdb` etc.).

## Sector Codes (Memorize)

| Code  | Sector              |
|-------|---------------------|
| 10001 | Electricity         |
| 10002 | Communication       |
| 10003 | Energy (Gas/Oil/Steam) |
| 10004 | Water               |
| 10005 | Undetermined        |
| 10006 | Sewage              |
| 10007 | Reclaimed Water     |

When a user says "water companies", "gas companies", etc., run the underlying tool to get *all* results and filter to the sector in the response — don't push the filter into the SQL prematurely, because users often want to see what else is nearby.

## Common Outputs

- **CSV** — for further analysis in QGIS or Excel
- **Text report** — paste-into-Slack summaries
- **AI-enhanced analysis** — Claude-written narrative on top of the raw data, for non-GIS stakeholders
- **GeoPackage (.gpkg)** — when the result needs to be reopened in QGIS

## Common Operations

| Operation | Tool |
|-----------|------|
| Polygon → utility owners (PostGIS intersection) | `polygon_query` |
| Org-name extraction from `amiggi4mdb` | `taxonomy_organization_names` |

## Vocabulary Cheat Sheet

- **Ticket** — a single 811 work-area record (polygon + metadata + owner list)
- **Owner / Utility owner** — the company responsible for the underground asset
- **Sector** — top-level category of utility (one of the codes above)
- **Project polygon** — the construction/excavation area we're querying against
- **Sanitized error** — a generic error message emitted instead of a stack trace, to keep credentials out of logs (see `invariants.md`)
