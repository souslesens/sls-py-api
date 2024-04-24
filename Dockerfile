FROM askomics/virtuoso:7.2.9 AS virtuoso
FROM docker.io/library/python:3.11-alpine

COPY --from=virtuoso /usr/local/virtuoso-opensource/lib /usr/local/virtuoso-opensource/lib

RUN apk add --no-cache poetry gcc g++ python3-dev unixodbc-dev

WORKDIR /src
COPY poetry.lock pyproject.toml README.md /src/
RUN poetry install

COPY sls_api /src/sls_api
RUN poetry install

COPY config.ini.default /src/config.ini

EXPOSE 8000

COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENTRYPOINT /entrypoint.sh
