from pathlib import Path
from json import loads
from time import sleep

import requests
from fastapi import FastAPI
from rdflib import Graph
from requests.auth import HTTPDigestAuth

from sls_api.config import SlsConfigParser
from sls_api.graph import RdfGraph
from sls_api.logging import log
from sls_api.users import User
from sls_api.utils import batched


class SlsConfig:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

        self.mainconfig = self._get_sls_config("mainConfig.json")
        self.sources = self._get_sls_config("sources.json")
        self.profiles = self._get_sls_config("profiles.json")
        self.users = self._get_sls_config("users/users.json")

    def _get_sls_config(self, file_name: str) -> dict:
        config_path = self.config_dir.joinpath(file_name)

        if not config_path.exists():
            raise FileNotFoundError(f"{file_name} connot be found in {config_path}")

        return loads(config_path.read_text())


class App(FastAPI):
    def __init__(self, config_path: str = "config.ini") -> None:
        super().__init__()
        self.config_path = Path(config_path)
        self.config = self._get_config()

        # logging
        self.log = log(self.config.get("main", "log_level"))

    def _get_config(self) -> SlsConfigParser:
        parser = SlsConfigParser()
        parser.read_file(self.config_path.open())
        return parser

    @property
    def sls_config(self):
        path = Path(self.config.get("main", "souslesens_config_dir")).expanduser()
        return SlsConfig(path)

    @property
    def _admin_user(self):
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

        for user in self.sls_config.users:
            if user.get("token", None) == token:
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