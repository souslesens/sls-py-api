FROM docker.io/library/python:3.11-alpine

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=askomics/virtuoso:7.2.9 /usr/local/virtuoso-opensource/lib /usr/local/virtuoso-opensource/lib

RUN apk add --no-cache gcc g++ python3-dev unixodbc-dev

WORKDIR /src

COPY . /src/
RUN uv sync --locked
COPY config.ini.default /src/config.ini

EXPOSE 8000

COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
