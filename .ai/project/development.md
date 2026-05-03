# Development

## Setup

```bash
git clone https://github.com/4ma/4m-geoint-toolbox.git
cd 4m-geoint-toolbox
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r dev-requirements.txt -r 4ma-requirements.txt
```

`4ma-requirements.txt` pulls from the 4m Nexus index — set `NEXUS_USERNAME` and `NEXUS_PASSWORD` in your shell first. Sister-repo CI uses org-level GitHub secrets; locally you read them from your dev environment.

## Running a Tool

Each tool runs from its own working directory:

```bash
cd tools/<tool_name>
cp .env.example .env  # fill in credentials
pip install -r requirements.txt  # tool-specific deps if any
python <main_script>.py [args]
```

Never `cd` into a tool dir to "test" without a real `.env` — every tool fails with a sanitized error (no credentials leaked) and asks you to fill it in. That is by design (see `invariants.md`).

## Testing

```bash
python coverage_run.py
```

Runs pytest under `coverage`, sourcing `shared/` and `tools/`, prints a report and writes `coverage.xml` + `htmlcov/`. CI runs the same command.

Markers:
- `slow` — opt-in via `python coverage_run.py -s`
- `external_resources` — opt-in via `python coverage_run.py -e`

## Adding a New Tool

1. **First, look for an existing tool to extend.** The `CLAUDE.md` rule is "fewer tools that do more." A new flag or output mode on an existing tool is almost always preferable to a new tool.
2. If extension genuinely doesn't fit:
   - Copy `templates/capability_template.yaml` into `tools/<new_tool>/capability.yaml`
   - Add `README.md`, `requirements.txt`, `.env.example`
   - Update the "Available Tools" table in the root `README.md`
3. Reuse `shared/db.py` for any DB access. Never duplicate the credential-loading.

## Library Notes (Gotchas)

- **psycopg2** — use `psycopg2-binary` in deps. Don't switch to `psycopg2` (source build) without a reason; CI runs on the standard runner image where the binary wheel is faster.
- **SQLAlchemy errors** — never call `pd.read_sql` directly. Use `safe_read_sql` from `shared/db.py`, which catches `SQLAlchemyError` (which can include the connection URL) and replaces with a generic message.
- **Anthropic SDK** — `anthropic>=0.39`. AI-enhanced output features (where supported) write to a separate `*_ai_report.md` file that is gitignored.
- **WKT inputs** — when the user pastes a polygon as text, save to a temp `.wkt` file in the tool dir and pass the path. Don't shove a multi-megabyte WKT into a CLI arg.

## CI

`tests-ci.yml` runs on every push, on the `4ma` self-hosted runner. It installs the three requirements files (incl. Nexus index) and runs `coverage_run.py`. If the runner is queueing forever, the org-level runner pool may not have access — talk to whoever manages it.

## Branching Convention

- `main` — release branch. Promotion-only.
- `dev` — integration branch. Feature PRs target this.
- `feature/<short-desc>` or `fix/<short-desc>` — feature/fix branches off `dev`.

Never PR directly to `main`. Promote from `dev` to `main` via a separate PR when ready.
