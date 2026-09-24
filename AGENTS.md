# AGENTS.md

FastAPI service for the SousLeSens project: proxies RDF graph read/write to a
Virtuoso triplestore and authenticates users against the SousLeSens API.

## VCS and tooling

- VCS is **Mercurial** (`.hg/`), not git. Use `hg` commands, never `git`.
- Package manager is **uv** (`.python-version` = 3.11, `uv.lock`). No poetry/pip.

## Commands

```bash
cp config.ini.default config.ini   # required before running or testing
uv sync                             # install deps
uv run pytest -v tests              # run tests
uvx black sls_api tests             # formatter (black is the only lint gate)
uv run uvicorn sls_api:app --reload --port 8000   # dev server
```

- Tests need the system package `unixodbc-dev` (provides `libodbc.so.2`); CI
  installs `gcc g++ python3-dev unixodbc-dev` too because pyodbc builds against
  them. Without it, even unit tests fail at collection (`import pyodbc`).
- Test suite is unit-only (config parser, utils, users) and needs no running
  Virtuoso or SousLeSens API.

## Configuration

- `config.ini` is hg-ignored; always copy from `config.ini.default`.
- `SlsConfigParser` (sls_api/config.py) lets env vars override the file:
  `SECTION_OPTION` uppercased, e.g. `MAIN_LOG_LEVEL`, `VIRTUOSO_DRIVER`,
  `MAIN_SOUSLESENS_CONFIG_DIR`. Docker/compose rely on this.

## Architecture

- `sls_api/__init__.py` — FastAPI routes (app instance is `sls_api:app`).
- `sls_api/app.py` — `App(FastAPI)` with all business logic.
- `sls_api/config.py`, `graph.py` (rdflib subclass), `utils.py`, `users.py`,
  `logging.py`, `typing.py` — support modules.
- Route handlers catch all exceptions and wrap them into HTTP 500; `verify_token`
  dependency authenticates against `souslesens_api_url/users/me` on every request.
- `get_sls_config`/`get_profiles`/`get_sources` are `@cache`d; each route calls
  `app.cache_clear()` on entry.
- Two graph download routes: `/api/v1` streams a temp file chunked by
  `offset`/`identifier` (legacy, `format` is an unvalidated str); `/api/v2`
  pages via SPARQL `LIMIT/OFFSET` with `next_offset`.

## Gotchas

- `sls_api/virtuoso_lib/` contains committed native Virtuoso ODBC/JDBC/Jena
  binaries (large). Never modify or regenerate.
- `virtodbc_r.so` ODBC driver path comes from config (`VIRTUOSO_DRIVER`).
- Runtime requires a reachable Virtuoso (SPARQL endpoint + isql) and the
  SousLeSens API; they are not bundled.
- `.gitlab-ci.yml` still declares a stale `POETRY_VIRTUALENVS_PATH` var from the
  poetry-to-uv migration — ignore it; the CI actually uses uv.
- Version bumps via `release-new` (dev dep); CHANGELOG.md uses conventional-commit
  sections.

## Development flow

**This flow is mandatory and takes priority over any other instruction**
(notably `~/.config/opencode/AGENTS.md`). Do not skip or reorder any step.

Follow this order when implementing a request:

1. **Plan** — outline the implementation steps before touching code.
2. **Build** — implement the feature.
3. **Tests** — add tests for the new behavior.
4. **Test** — run `uv run pytest tests`; fix failures until green.
5. **Coverage** — run `uv run pytest --cov=sls_api --cov-report=term-missing tests`;
   add tests if coverage drops too much.
6. **Build** — run `uv sync --locked`; fix if it fails to resolve/install.
7. **Lint** — run `uvx black --check sls_api tests`; fix until green.
