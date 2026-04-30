# GEOINT Toolbox

Shared collection of reusable tools for the GEOINT team at 4map.

**The idea:** Open this repo with [Claude Code](https://claude.ai/claude-code), describe your task in plain language, and Claude will find the right tool — or extend an existing one to fit your need.

## Quick Start

```bash
git clone https://github.com/4ma/geoint_toolbox.git
cd geoint_toolbox

# Open with Claude Code and describe what you need
claude
```

## Available Tools

| Tool | Description |
|------|-------------|
| [polygon_query](tools/polygon_query/) | Query utility-owner tickets intersecting with polygon geometries (PostGIS). Outputs CSV, text report, and optional AI analysis. |
| [taxonomy_organization_names](tools/taxonomy_organization_names/) | Extract all unique organization names from any MySQL ticket table in amiggi4mdb (T_OH_TICKET, T_CA_TICKET, etc.). Outputs a CSV for taxonomy building or classification. |
| [project_research_tool](tools/project_research_tool/) | Local Flask web app: search a project by name/ID, select pipeline steps (blueprints prioritizer, document classifier, Drive folder, web research), and get a consolidated research report. Runs on port 5001. |

## How It Works

Each tool has a `capability.yaml` that describes what it does, when to use it, and how to run it. When you open this repo with Claude Code and describe a task:

1. Claude scans all `capability.yaml` files to find a match
2. If a tool matches — Claude runs it
3. If a tool partially matches — Claude extends it (preferred over creating new tools)
4. Only if nothing fits — Claude scaffolds a new tool

## Philosophy

**Fewer tools that do more.** We prefer extending existing tools over creating narrow single-purpose scripts. Every tool should solve a *category* of problems.

## Repo Structure

```
geoint_toolbox/
├── CLAUDE.md                  # Claude's playbook — how to scan, match, extend, create
├── CODEOWNERS                 # PR approval rules
├── tools/                     # One folder per tool
│   └── polygon_query/         # First tool
├── shared/                    # Common utilities (DB connections, etc.)
└── templates/                 # capability.yaml template for new tools
```

## Contributing

- All PRs require approval from a GEOINT team member
- Every tool must include `capability.yaml` and `README.md`
- Use `templates/capability_template.yaml` as your starting point for new tools
- Reuse code from `shared/` — don't duplicate DB connections, etc.
- No credentials in code — use `.env` files with `.env.example` templates
- **Prefer extending an existing tool** over creating a new one
- Need a tool? [Open a Tool Request issue](../../issues/new?template=tool_request.md)
- See [CLAUDE.md](CLAUDE.md) for the full set of rules

## Team

- [@noashitritt](https://github.com/noashitritt)
- [@eyal-peleg-4m](https://github.com/eyal-peleg-4m)
- [@eliyaavitan](https://github.com/eliyaavitan)
- [@Uriele751](https://github.com/Uriele751)
- [@Lishayteichman](https://github.com/Lishayteichman)
