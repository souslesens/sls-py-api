# SousLeSens - Python FastAPI

## Install

```bash
poetry install
```

## Configure

Create a `config.ini` file from the template

```bash
cp config.ini.default config.ini
```

Edit it according to your environment

## Run (dev)

```bash
poetry run uvicorn sls_api:app --reload --port 8000
```

API will be available at [localhost:8000](http://localhost:8000)

## Deploy using docker (prod)

create a `compose.yml` file

```yaml
# this is an example, adapt it to your needs
services:
  sls-api:
    image: registry.logilab.fr/totalenergies/sls-api:<version>
    ports:
      - 8000:8000
    environment:
      MAIN_SOUSLESENS_CONFIG_DIR: /souslesens_config
      MAIN_LOG_LEVEL: debug
      CORS_ORIGINS: "*"
      RDF_BATCH_SIZE: 100000
    volumes:
      - /path/to/souslesens/config:/souslesens_config:ro
```

and start it with `docker compose up -d`.

Alternatively, with `docker` command:

```bash
docker run -d -p 8000:8000 -e MAIN_SOUSLESENS_CONFIG_DIR=/souslesens_config -e MAIN_LOG_LEVEL=debug -e CORS_ORIGINS="*" -e RDF_BATCH_SIZE=100000 -v /path/to/souslesens/config:/souslesens_config:ro registry.logilab.fr/totalenergies/sls-api:<version>
```
