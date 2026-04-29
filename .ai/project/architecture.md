# Architecture

## Repo Shape

This repo is a **toolbox** — a flat collection of independent tools, not a single application. Each tool is self-contained under `tools/<tool_name>/` and runs from its own working directory. There is no single deployable artifact; tools are run on-demand by team members or by Claude Code.

```
geoint_toolbox/
├── tools/                # one folder per tool, each a runnable CLI
│   ├── polygon_query/    # PostGIS polygon-intersection queries
│   └── taxonomy_organization_names/  # extract org names from amiggi4mdb
├── shared/               # cross-tool utilities (DB connections, etc.)
├── templates/            # capability.yaml template for new tools
├── .ai/project/          # project context for Claude (this dir)
└── CLAUDE.md             # routing playbook for Claude Code
```

## Core Pattern: capability.yaml

Each tool ships a `capability.yaml` describing:
- **triggers** — natural-language patterns that should match this tool
- **description** — what the tool does
- **out_of_scope** — what the tool explicitly does *not* do
- **run** — how to invoke (working directory, command)
- **health** — `active`/`deprecated`/`experimental`, `last_tested` date

When a user describes a task to Claude, the routing logic in `CLAUDE.md` says: scan all `capability.yaml` files, match against triggers/description, prefer extending an existing tool over creating a new one.

## Shared Code Boundary

`shared/` is the single chokepoint for cross-cutting concerns. Today it contains:
- `shared/db.py` — PostgreSQL/PostGIS connection helper with **sanitized errors**: connection failures emit a generic message and exit, never leaking host/user/password through stack traces. All DB access in tools must go through `get_engine()` and `safe_read_sql()`.

New shared utilities (output formatting, geometry parsing, AI-report generation) belong in `shared/` once they are used by 2+ tools — not duplicated per tool.

## Per-Tool Layout

```
tools/<tool_name>/
├── capability.yaml       # REQUIRED
├── README.md             # REQUIRED
├── requirements.txt      # tool-specific deps (in addition to root)
├── .env.example          # credential template (real .env is gitignored)
├── <main_script>.py
└── examples/             # sample inputs
```

## Why a Toolbox Instead of N Repos

GEOINT work is exploratory: a request like "find water companies inside this polygon" maps to one of a small set of repeatable operations against PostGIS or 811 systems. Spinning up a repo per tool produced too much overhead and too little reuse. The toolbox keeps each tool's blast radius small (its own deps, env, run command) while letting Claude pick the right one and giving us one place to enforce credential-handling rules.

## What This Repo Is NOT

- Not a deployable service. No Dockerfile, no DAGs, no published Python package.
- Not a single library. Tools are scripts, not importable APIs (except `shared/`).
- Not versioned monolithically. Each tool has its own `capability.yaml.version`.
