FROM docker.io/library/python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=askomics/virtuoso:7.2.9 /usr/local/virtuoso-opensource/lib /usr/local/virtuoso-opensource/lib

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ python3-dev unixodbc-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY . /src/
RUN uv sync --locked
COPY config.ini.default /src/config.ini

EXPOSE 8000

COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
