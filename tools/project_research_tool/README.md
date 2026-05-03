# Project Research Tool

A local Flask web tool that runs a full research pipeline for a 4map project.

## What it does

1. **Project search** — type a project name or ID, select from live dropdown (queries `analysis-operation`)
2. **Municipality resolution** — intersects the project polygon with `geo-ing` to get state/county/municipality
3. **Google Drive** — creates (or finds) a project folder with source sub-folders
4. **Blueprint Prioritizer** — spatial query against `public_records.blueprints` *(stub — see below)*
5. **Downloader** — downloads S3 files from Prioritizer output *(stub)*
6. **Gemini Classifier** — classifies downloaded documents *(stub)*
7. **Utility Owners** — spatial query against `utility_owners` tables *(stub)*
8. **FCC Data** — FCC dataset intersection *(stub)*
9. **Web Research** — Claude-powered web research with `web_search` tool *(fully implemented)*

Results render on a single page with a fixed sidebar nav and a "Save to Drive" button.

## Setup

```bash
cd tools/project_research_tool
pip install -r requirements.txt
cp .env.example .env       # fill in credentials
python main.py
```

Open [http://localhost:5000](http://localhost:5000).

## Credentials needed

| Variable | What it's for |
|---|---|
| `DB_ANALYSIS_*` | analysis-operation DB — `on_demand.project_request` |
| `DB_GEOING_*` | geo-ing DB — `db4data.municipalities_new`, `public_records.blueprints` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to Drive service account JSON key |
| `GOOGLE_DRIVE_PARENT_FOLDER_ID` | Parent Drive folder for project folders |
| `ANTHROPIC_API_KEY` | Web research step |
| `GEMINI_API_KEY` + `GEMINI_CLASSIFIER_SCRIPT` | Classifier step (TBD) |

## Plugin stubs

The QGIS plugins (`pdf_prioritizer_plugin`, `utility_owners_qgis_plugin`, etc.) are **GUI plugins** — they cannot be called via subprocess. When wiring up each step, extract the SQL from the plugin source and run it directly via SQLAlchemy. See `handlers/qgis_runner.py` for the exact output schemas and SQL templates for each step.

Plugin source: `4ma-qgis-plugins/` (read-only reference)

## File structure

```
tools/project_research_tool/
├── main.py                    # Flask app + routes
├── config.py                  # Settings from .env
├── pipeline.py                # Orchestrator (7 steps)
├── db/
│   ├── connections.py         # Multi-DB SQLAlchemy engines
│   ├── project_query.py       # analysis-operation → project_request
│   └── municipality_query.py  # geo-ing → municipalities_new
├── handlers/
│   ├── google_drive.py        # Drive folder + upload (fully implemented)
│   ├── qgis_runner.py         # Plugin stubs (4 functions)
│   ├── classifier.py          # Gemini classifier stub
│   └── research_agent.py      # Claude web research (fully implemented)
├── prompts/
│   └── research_templates.py  # Prompt templates
├── static/
│   ├── style.css              # Claude dark design system
│   └── app.js                 # Live search, sidebar, results rendering
├── templates/
│   ├── index.html             # Search + filters form
│   └── results.html           # Results page (7 sections)
├── scripts/                   # Reserved for future scripts
└── outputs/                   # Pipeline outputs — gitignored
```