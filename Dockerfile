FROM docker.io/library/python:3.11-alpine

RUN apk add --no-cache poetry

WORKDIR /src
COPY poetry.lock pyproject.toml README.md /src/
RUN poetry install

COPY sls_api /src/sls_api
RUN poetry install

COPY config.ini.default /src/config.ini

EXPOSE 8000

COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENTRYPOINT /entrypoint.sh
