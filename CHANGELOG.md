## Version 2.8.0 (2026-09-24)
### 🗜️ Refactoring

- remove unused upload and download methods *BREAKING CHANGE*

### 👷 Bug fixes

- return 401 when token has no matching user

### 🔧 Build process or tool changes

- add pytest-cov and pin httpx for coverage
- ignore venv and local dev artifacts

### 🤖 Continuous integration

- run pytest with coverage in gitlab

### 🧪 Tests

- add app logic and route tests
- migrate unit tests to pytest style
- move graph and sls data fixtures into tests/data

### 📝 Documentation

- add development workflow to AGENTS.md

## Version 2.7.0 (2026-08-10)
### 🎉 New features

- convert blank nodes to URIs before virtuoso upload
- return blank_nodes_converted flag in upload response *BREAKING CHANGE*

## Version 2.6.0 (2026-05-22)
### 🎉 New features

- add blank nodes detection on graph upload

## Version 2.5.1 (2026-04-03)
### 🔧 Build process or tool changes

- upgrade version number in uv.lock

## Version 2.5.0 (2026-03-26)
### 🎉 New features

- upload chunk directly if mimetype is nt

## Version 2.4.1 (2026-02-06)
### 👷 Bug fixes

- constributor is owner, not logged user

## Version 2.4.0 (2026-02-05)
### 🎉 New features

- add new /api/v2/rdf/graph route to get rdf graph
- add imports to download
- add import and contributor triples on first offset
- get sparqlDownloadLimit from sls config
- add cache

### 🔧 Build process or tool changes

- remove poetry.lock

## Version 2.3.0 (2025-12-11)
### 👷 Bug fixes

- delete method can't take a body, but a url params

## Version 2.2.0 (2025-12-04)
### 🎉 New features

- split n-triples RDF file and batch-upload them

## Version 2.1.0 (2025-12-04)

## Version 2.1.0 (2025-12-03)
### 🎉 New features

- add isql method to delete graphs

### 🗜️ Refactoring

- `delete_graph` method
- extract `get_isql_connection` method

### 🔧 Build process or tool changes

- migrate to uv

## Version 2.0.1 (2025-07-18)
### 👷 Bug fixes

- remove remaining sls config call

## Version 2.0.0 (2025-07-17)
### 🎉 New features

- add /api/v1/health route
- add token to User object
- get profiles from souslesens API
- get sources from souslesens API
- get user info from sls api
- remove unused root route

### 👷 Bug fixes

- _get_permission_from_profile method
- correctly raise HTTPException errors
- parse and format date using dateparser

### 🗜️ Refactoring

- don't use admin-specific code for disabled auth
- *BREAKING CHANGE* don't use mainConfig.json to get souslesens configuration
- remove useless _admin_user property

### 🧪 Tests

- remove TestSlsConfig
- remove useless test
- update tests

### 🔧 Build process or tool changes

- pkg: install dateparser

## Version 1.6.1 (2025-06-25)
### 👷 Bug fixes

- Dockerfile: add --no-root option for latest version of poetry

## Version 1.6.0 (2025-02-28)
### 🎉 New features

- improve convert route

### 🗜️ Refactoring

- store compiled regexp in an object

### 🧪 Tests

- test `get_uri_from_str` and `guess_triple_type`

## Version 1.5.0 (2025-02-18)
### 🎉 New features

- add /api/v1/rdf/convert route
- add `tags_metadata`

## Version 1.4.0 (2024-11-07)
### 🎉 New features

- add `sparql_load` method for posting graph

## Version 1.3.1 (2024-11-06)
### 🤖 Continuous integration

- base: install deps

## Version 1.3.0 (2024-11-06)
### 🎉 New features

- add method for posting graphs (api or `api_batched)`

## Version 1.2.0 (2024-10-16)
### 🎉 New features

- add try/except around all api routes

### 👷 Bug fixes

- set blank nodes as uris

## Version 1.1.0 (2024-05-21)
### 🎉 New features

- _get_rdf_graph_from_isql method
- configurable download `chunk_size`

### 📝 Documentation

- virtuoso installation

### 🤖 Continuous integration

- improve jobs
