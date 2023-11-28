#!/bin/sh

exec poetry run uvicorn sls_api:app --reload --host 0.0.0.0
