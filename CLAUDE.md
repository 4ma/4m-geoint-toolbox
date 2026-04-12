# GEOINT Toolbox

A shared collection of reusable tools for the GEOINT team at 4map.
Open this repo with Claude Code, describe your task, and get matched to an existing tool — or extend one.

## Team Domain Context

4map is a geospatial data company. The GEOINT team works with:
- **Utility-owner data** — tickets from US state 811 systems (California, Texas, Florida, etc.) stored in PostGIS
- **Polygon geometries** — project boundaries in WKT format (from QGIS, PostGIS, or GIS tools)
- **Road mark detection** — identifying and validating road markings that may correlate with underground utilities
- **Spatial analysis** — intersections, containment, proximity queries against geospatial databases
- **Report generation** — CSV exports, text summaries, AI-enhanced analyses for field teams and Slack

Common data sources:
- PostgreSQL/PostGIS databases (utility owners, geometries)
- WKT/GeoJSON polygon files
- Sector codes (electricity, gas, telecom, water, sewage)

## How This Repo Works

Each tool lives in `tools/<tool_name>/` and has a `capability.yaml` that describes:
- What the tool does
- When to use it (trigger patterns)
- What it does NOT do (out of scope)
- How to run it
- Health status (active / deprecated / experimental, last tested date)

Shared code lives in `shared/` — common utilities like DB connections that multiple tools use.

Templates live in `templates/` — use `capability_template.yaml` when creating new tools.

## Your Job as Claude

When a user describes a task, follow this decision tree **in order**:

### Step 1 — Understand the request
Before scanning tools, make sure you understand:
- What data does the user have? (polygon, coordinates, ticket IDs, etc.)
- What output do they need? (CSV, report, quick answer, investigation)
- What system/database is involved?

If the request is ambiguous, **ask one clarifying question** before proceeding. Don't guess.

### Step 2 — Scan for a match
Read every `tools/*/capability.yaml` file. For each tool, check:
- `triggers` — does the user's intent match any pattern?
- `description` — does the tool cover this domain?
- `out_of_scope` — is the request explicitly excluded?
- `health.status` — is the tool active? If deprecated or experimental, warn the user.
- `health.last_tested` — if older than 90 days, mention it might need verification.

### Step 3 — If a tool matches → run it
- Check `health.status` is `active`
- Follow the `run` section in `capability.yaml`
- Make sure the user has the required credentials (check `.env.example`)
- Run the tool and present results

### Step 4 — If a tool partially matches → EXTEND it (preferred)
If a tool does 70-80% of what the user needs, **modify it** rather than creating a new tool.
- Add a new flag, output mode, or data source to the existing tool
- Update `capability.yaml`: add triggers, update description, bump version
- Update `README.md` to document the new capability
- Update `health.last_tested` to today
- **This is the preferred path.** Fewer tools that do more > many narrow tools

### Step 5 — Only if nothing is close → create a new tool
If no existing tool covers even part of the need:
- Use `templates/capability_template.yaml` as the starting point
- Check if `shared/` has utilities you can reuse (DB connections, etc.)
- Follow the structure and rules below

### Step 6 — After ANY change (extend or create)
- All changes must go through a PR (never commit directly to main)
- The PR requires approval from a GEOINT team member (CODEOWNERS)
- Update the "Available Tools" table in the root `README.md` if a new tool was added

## Rules for Extending Tools

- **Extend, don't fork.** If `polygon_query` handles PostGIS queries and someone needs a different kind of PostGIS query, add it to `polygon_query` — don't create `polygon_query_v2`.
- **Backward-compatible flags.** Existing usage must not break. Add new behavior behind new flags or arguments.
- **Update capability.yaml.** Every change to a tool's scope must be reflected in its `capability.yaml` — add triggers, update description, adjust out_of_scope. Bump the version.
- **Keep tools general.** A tool should solve a *category* of problems, not one specific instance. If you're building something that only works for one exact polygon or one exact query, generalize it.
- **Reuse shared/.** If your extension needs a DB connection or output formatting that already exists in `shared/`, import it — don't rewrite it.

## Rules for Creating New Tools

Only create a new tool when:
- No existing tool covers the domain (e.g., first tool that touches a new database, a new API, or a fundamentally different workflow)
- Extending an existing tool would make it incoherent (mixing unrelated responsibilities)

New tools must follow this structure:
```
tools/<tool_name>/
├── capability.yaml       # REQUIRED — use templates/capability_template.yaml
├── README.md             # REQUIRED — human-readable docs
├── requirements.txt      # Python dependencies (if applicable)
├── .env.example          # Credential template (if applicable)
├── <main_script>         # The tool itself
└── examples/             # Sample inputs (if applicable)
```

The `capability.yaml` must include all fields from the template, including the `health` section.

## Repo Organization Rules

- **One folder per tool** under `tools/`.
- **Shared code** goes in `shared/`, not duplicated across tools.
- **No loose scripts** in the repo root — everything goes inside a tool folder.
- **No credentials in code.** Use `.env` files (gitignored) with `.env.example` templates. Never hardcode hostnames, passwords, or API keys.
- **Every tool must have `capability.yaml` and `README.md`** — no exceptions.
- **All PRs require approval** from a GEOINT team member before merging (see CODEOWNERS).
- **Commit messages** should reference what tool was changed (e.g., "polygon_query: add --format json output flag").
- **Update health metadata** when you test or modify a tool — set `last_tested` to today and `tested_by` to your handle.

## Team Members (GEOINT)

- @noashitritt
- @eyal-peleg-4m
- @eliyaavitan
- @Uriele751
