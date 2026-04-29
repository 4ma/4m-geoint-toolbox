# Infrastructure

## Deployment

There is no deployment. Tools run on the user's machine (or in Claude Code's sandbox). They are CLIs invoked on-demand against shared backend systems.

If a specific tool ever needs to ship as a service, that tool grows its own `Dockerfile` inside `tools/<tool_name>/`. The repo deliberately does not ship a single root `Dockerfile` — there is no single artifact.

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/tests-ci.yml` | every push | installs deps from `requirements.txt` + `dev-requirements.txt` + `4ma-requirements.txt` (Nexus), runs `python coverage_run.py`, uploads to Codecov (currently non-blocking; may be removed entirely) |

CI runs on the `4ma` self-hosted runner pool. New repos in the org need to be granted access to the runner pool.

## Backend Systems Tools Touch

- **PostGIS** — utility-owner ticket database. Read-only from this repo's tools. Connection details in each tool's `.env` (gitignored). Connection helper: `shared/db.py`.
- **MySQL (`amiggi4mdb`)** — taxonomy / organization-name source. Used by `taxonomy_organization_names`.
- **Anthropic API** — when a tool offers an "AI-enhanced report" mode. Key in tool-level `.env`.

## Secrets

- **Local development** — `.env` per tool, populated from `.env.example`. Never committed.
- **CI** — Nexus credentials (`NEXUS_USERNAME`, `NEXUS_PASSWORD_ENCODED`) are inherited from org-level GitHub secrets. Tool-specific secrets (DB host, Anthropic key) are not currently in CI because no tool has automated tests against live backends yet.
- **Vault** — production credentials live in the team Vault, not in code or any README.

## Observability

Tools are interactive CLIs and log to stdout/stderr. There is no centralized logging or alerting because there is no long-running process. If a tool starts running on a schedule, it gains its own DAG / monitor at that point — that is out of scope for the toolbox today.
