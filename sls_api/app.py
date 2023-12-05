from pathlib import Path
from time import sleep

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rdflib import Graph
from requests.auth import HTTPDigestAuth

from sls_api.config import SlsConfigParser, SlsConfig
from sls_api.graph import RdfGraph
from sls_api.logging import log
from sls_api.users import User
from sls_api.utils import batched, sparql_query


class App(FastAPI):
    def __init__(self, config_path: str = "config.ini"):
        super().__init__()

        self.config_path = Path(config_path)
        self.config = self._get_config()

        self.log = log(self.config.get("main", "log_level"))

        self.add_middleware(
            CORSMiddleware,
            allow_origins=[
                e.strip()
                for e in self.config.get(
                    "cors", "origins", fallback="localhost,127.0.0.1"
                ).split(",")
            ],
            allow_credentials=self.config.getboolean(
                "cors", "allowed_credentials", fallback=True
            ),
            allow_methods=[
                e.strip()
                for e in self.config.get(
                    "cors", "allowed_methods", fallback="GET,POST,DELETE"
                ).split(",")
            ],
            allow_headers=[
                e.strip()
                for e in self.config.get("cors", "allowed_headers", fallback="*").split(
                    ","
                )
            ],
        )

    def _get_config(self) -> SlsConfigParser:
        parser = SlsConfigParser()
        parser.read_file(self.config_path.open())
        return parser

    @property
    def sls_config(self) -> SlsConfig:
        path = Path(self.config.get("main", "souslesens_config_dir")).expanduser()
        return SlsConfig(path)

    @property
    def _admin_user(self) -> dict:
        return {
            "_type": "user",
            "groups": ["admin"],
            "id": "admin",
            "login": "admin",
            "name": "admin",
            "password": "admin",
            "source": "json",
            "token": "admin",
        }

    def get_user_from_token(self, token: str) -> User:
        if self.sls_config.mainconfig["auth"] == "disabled":
            return User(**self._admin_user)

        for user in self.sls_config.users.values():
            if user.get("token", None) == token:
                # sometimes, name is not present in users.json file
                if not "name" in user:
                    user["name"] = user["id"]
                return User(**user)

    def add_sources_for_user(self, user: User) -> User:
        user.set_sources(self._get_user_sources(user))
        return user

    def _get_admin_sources(self) -> dict:
        admin_sources = {}
        for identifier, source in self.sls_config.sources.items():
            source["accessControl"] = "readwrite"
            admin_sources[identifier] = source
        return admin_sources

    def _get_user_sources(self, user: User) -> dict | None:
        profiles = self.sls_config.profiles
        sources = self.sls_config.sources

        if user.is_admin():
            return self._get_admin_sources()

        user_profiles = {k: v for k, v in profiles.items() if k in user.groups}

        all_access_control = {}
        for identifier, source in sources.items():
            name = source.get("name")

            group = source.get("group", "")
            if len(group.strip()) == 0:
                group = "DEFAULT"

            permission = self._get_permission_from_profile(
                user_profiles,
                "/".join([source.get("schemaType"), group, name]),
            )

            current_permission = all_access_control.setdefault(name, "")
            if len(current_permission) < len(permission):
                all_access_control[name] = permission

        user_sources = {}
        for identifier, source in sources.items():
            name = source.get("name")

            if name in all_access_control:
                source["accessControl"] = all_access_control[name]
                user_sources[identifier] = source

        return user_sources

    def _get_permission_from_profile(
        self, user_profiles: dict, source_tree: str
    ) -> str:
        for profile in user_profiles.values():
            permissions = []

            sources_access_control = profile["sourcesAccessControl"]
            for key, value in sources_access_control.items():
                if source_tree.startswith(key):
                    permissions.append((key, value))

            formal_label = self.sls_config.mainconfig[
                "formalOntologySourceLabel"
            ].strip()
            if len(formal_label) > 0:
                permissions.append((formal_label, "read"))

            permissions = sorted(permissions, key=lambda k: len(k[1]), reverse=True)
            if len(permissions) > 0:
                return permissions[0][1]

        return ""

    def _get_graph_size(self, source_name: str):
        graph_uri = self.sls_config.sources[source_name]["graphUri"]

        sparql_server = self.sls_config.mainconfig["sparql_server"]
        sparql_url = sparql_server["url"]
        virtuoso_user = sparql_server["user"]
        virtuoso_password = sparql_server["user"]

        query = f"""SELECT count(*) as ?total
        FROM <{graph_uri}>
        WHERE {{
            ?s ?p ?o
        }}"""

        result = int(
            sparql_query(sparql_url, virtuoso_user, virtuoso_password, query)[
                "results"
            ]["bindings"][0]["total"]["value"]
        )
        return result

    def delete_graph_from_endpoint(self, source_name: str):
        graph_uri = self.sls_config.sources[source_name]["graphUri"]

        sparql_server = self.sls_config.mainconfig["sparql_server"]
        virtuoso_url = sparql_server["url"].removesuffix("/sparql")
        virtuoso_user = sparql_server["user"]
        virtuoso_password = sparql_server["user"]

        self.log.info(f"removing {graph_uri}…")

        response = requests.delete(
            f"{virtuoso_url}/sparql-graph-crud-auth",
            auth=HTTPDigestAuth(virtuoso_user, virtuoso_password),
            params={"graph-uri": graph_uri},
        )
        if response.status_code not in (200, 201, 404):
            self.log.info(f"Got {response.status_code} while deleting graph")
        sleep(3)  # give virtuoso enough time to delete the graph

    def get_rdf_graph_from_endpoint(
        self, graph_path: Path, source_name: str, format: str = "nt"
    ):
        graph_uri = self.sls_config.sources[source_name]["graphUri"]

        sparql_server = self.sls_config.mainconfig["sparql_server"]
        sparql_url = sparql_server["url"]
        virtuoso_user = sparql_server["user"]
        virtuoso_password = sparql_server["user"]

        limit = self.config.getint("rdf", "batch_size")
        graph_size = self._get_graph_size(source_name)
        offset = 0

        graph = Graph()

        while offset < graph_size:
            # get percent and number of triples for logging
            percent = min(int(((offset + limit) * 100 / graph_size)), 100)
            ntriples = limit if offset + limit < graph_size else graph_size - offset

            self.log.info(f"Downloading {graph_uri} ({ntriples} triples) ({percent}%)")

            # get a subgraph
            query = f"""CONSTRUCT {{ ?s ?p ?o . }}
            FROM <{graph_uri}>
            WHERE {{
                ?s ?p ?o .
            }}
            LIMIT {limit}
            OFFSET {offset}"""

            results = sparql_query(
                sparql_url, virtuoso_user, virtuoso_password, query, "xml"
            )

            # concat subgraph to final graph
            graph += results
            offset += limit

        # write graph to tmpfile
        graph.serialize(destination=graph_path, format=format, encoding="utf-8")
        self.log.info(f"{graph_uri} writed to {graph_path}")

        return graph_path

    def upload_rdf_graph_to_endpoint(
        self, graph_path: Path, source_name: str, remove_graph: bool = False
    ):
        graph_uri = self.sls_config.sources[source_name]["graphUri"]

        if remove_graph:
            self.delete_graph_from_endpoint(source_name)

        # parse uploaded file into rdfilb graph
        graph = RdfGraph(graph_path)

        sparql_server = self.sls_config.mainconfig["sparql_server"]
        virtuoso_url = sparql_server["url"].removesuffix("/sparql")
        virtuoso_user = sparql_server["user"]
        virtuoso_password = sparql_server["user"]

        # divide graph into subgraph of batch_size triples and upload them
        batch_size = self.config.getint("rdf", "batch_size")
        graph_size = len(graph)
        for i, batch in enumerate(batched(graph, batch_size)):
            subgraph = Graph()
            for triples in batch:
                subgraph.add(triples)

            ntriples = subgraph.serialize(format="nt", encoding="utf-8")

            response = requests.post(
                f"{virtuoso_url}/sparql-graph-crud-auth",
                auth=HTTPDigestAuth(virtuoso_user, virtuoso_password),
                params={"graph-uri": graph_uri},
                data=ntriples,
                headers={"Content-type": "text/plain"},
            )

            # get percent for logs
            percent = min(100, int((((i + 1) * batch_size) * 100) / graph_size))
            status = "ok" if response.ok else "ERROR"
            self.log.info(
                f"uploading {graph_uri} ({len(subgraph)} triples) ({percent}%) {status}"
            )

            if not response.ok:
                raise BaseException(
                    f"\nGot {response.status_code} while posting graph "
                    f"{graph_uri}:\n  {response.content}"
                )
