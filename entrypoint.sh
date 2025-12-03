#!/bin/sh

exec uv run uvicorn sls_api:app --reload --host 0.0.0.0
