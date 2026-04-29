# Invariants

Architectural and security constraints that **must** hold across all tools. If a change would violate an invariant here, the change does not ship — fix the invariant or fix the change first.

## Security Invariants

1. **No credential value ever appears in stdout, stderr, logs, or PR diffs.** Connection failures emit a sanitized message ("Could not connect to the database.") and exit. Stack traces from `SQLAlchemyError`, `mysql.connector.Error`, etc. are caught at `shared/` and replaced.

2. **All DB access goes through `shared/db.py`.** Tools never duplicate `create_engine(...)` or `psycopg2.connect(...)` calls. The single chokepoint is the only place we maintain credential-handling and error-sanitization logic.

3. **`pd.read_sql()` is forbidden in tool code.** Use `safe_read_sql()` from `shared/db.py`. Direct `pd.read_sql` lets SQLAlchemy errors (which include the connection URL) reach stdout.

4. **`.env` files are never read by Claude or by debugging code.** This includes `cat .env`, `grep TOKEN`, `printenv`, `os.environ` dumps. `.env.example` is the only env file that may be read — it contains placeholders only.

5. **Credentials pasted into chat are treated as compromised.** If a user pastes a connection string or password, the response must be: stop, tell the user to rotate it, do not use the leaked value.

## Architectural Invariants

6. **One folder per tool under `tools/`.** No loose scripts at the repo root. No multi-tool folders.

7. **Every tool has `capability.yaml` and `README.md`.** Without these, the tool is invisible to the routing logic and undiscoverable to humans — it does not exist.

8. **Tools are general, not single-use.** A tool solves a category of problems. If something only works for one specific polygon or one specific query, generalize it before merging.

9. **Extend before creating.** If an existing tool covers 70%+ of a need, modify it (new flag, new mode) rather than scaffold a new tool. New tools are the last resort.

10. **No hardcoded credentials, hostnames, or API keys in code.** Everything goes through `.env` (gitignored) with `.env.example` (committed, placeholders).

## Process Invariants

11. **All changes go through PR.** No direct commits to `main` or `dev`. Approval required from a GEOINT team member (CODEOWNERS) before merging.

12. **Feature PRs target `dev`. Promotion PRs target `main`.** Never PR a feature branch directly to `main`.

13. **Update `health.last_tested` and `health.tested_by` whenever you modify or verify a tool.** The capability.yaml is the source of truth for which tools are still working.
