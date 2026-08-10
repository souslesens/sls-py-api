import random
import shutil
import tempfile
import json
import mimetypes
from datetime import datetime
from functools import cache
from pathlib import Path
from re import compile as re_compile
from string import ascii_lowercase
from tempfile import gettempdir
from time import sleep
from typing import List

import requests
import dateparser
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rdflib import Graph, URIRef, Literal, XSD, BNode
from rdflib.namespace import OWL, DC
from requests.auth import HTTPDigestAuth

from sls_api.config import SlsConfigParser
from sls_api.graph import RdfGraph
from sls_api.logging import log
from sls_api.typing import Triple
from sls_api.users import User
from sls_api.utils import (
    batched,
    get_isql_connection,
    get_uri_from_str,
    guess_triple_type,
    has_blank_nodes,
    replace_blank_nodes_with_uris,
    sparql_query,
)


class App(FastAPI):
    def __init__(self, config_path: str = "config.ini", openapi_tags=[]):
        super().__init__(openapi_tags=openapi_tags)

        self.config_path = Path(config_path)
        self.config = self._get_config()

        self.log = log(self.config.get("main", "log_level"))

        self.regexp = {
            "authorization_pattern": re_compile(
                r"^(?P<scheme>[^\s]+)\s+(?P<token>[^$]+)"
            ),
        }

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

    def get_user_from_token(self, token: str) -> User:
        api_base_url = self.config.get("main", "souslesens_api_url")
        url = f"{api_base_url}/users/me"
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(url, headers=headers)
        user = response.json()
        return User(**user)

    @cache
    def get_sls_config(self, token: str) -> None:
        api_base_url = self.config.get("main", "souslesens_api_url")
        url = f"{api_base_url}/config"
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(url, headers=headers)
        config = response.json()
        return config

    @cache
    def get_profiles(self, token: str) -> dict:
        api_base_url = self.config.get("main", "souslesens_api_url")
        url = f"{api_base_url}/profiles"
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(url, headers=headers)
        profiles = response.json()["resources"]
        return profiles

    @cache
    def get_sources(self, token: str) -> dict:
        api_base_url = self.config.get("main", "souslesens_api_url")
        url = f"{api_base_url}/sources"
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(url, headers=headers)
        sources = response.json()["resources"]
        return sources

    def cache_clear(self):
        self.get_sls_config.cache_clear()
        self.get_profiles.cache_clear()
        self.get_sources.cache_clear()

    def add_sources_for_user(self, user: User) -> User:
        user.set_sources(self._get_user_sources(user))
        return user

    def _get_user_sources(self, user: User) -> dict | None:
        profiles = self.get_profiles(user.token)
        sources = self.get_sources(user.token)

        all_access_control = {}
        for identifier, source in sources.items():
            name = source.get("name")

            group = source.get("group", "")
            if len(group.strip()) == 0:
                group = "DEFAULT"

            permission = self._get_permission_from_profile(
                profiles,
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
        final_permission = "forbidden"
        for profile in user_profiles.values():
            permissions = []
            sources_access_control = profile["sourcesAccessControl"]
            for key, value in sources_access_control.items():
                if source_tree.startswith(key):
                    permissions.append((key, value))

            permissions = sorted(permissions, key=lambda k: len(k[1]), reverse=True)
            if len(permissions) > 0:
                final_permission = self.get_updated_permission(
                    final_permission, permissions[0][1]
                )

        return final_permission

    @staticmethod
    def get_updated_permission(existing_perm, new_perm):
        if existing_perm == "forbidden":
            return new_perm

        if existing_perm == "read" and new_perm == "forbidden":
            return "read"

        return "readwrite"

    def _get_graph_size(self, user: User, source_name: str, add_imports: bool = False):
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        sparql_url = self.config.get("virtuoso", "sparql_url")

        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        from_str = ""
        if add_imports:
            from_str = self._get_imports_string(
                user, source_name, sources[source_name]["imports"]
            )

        query = f"""SELECT count(*) as ?total
        FROM <{graph_uri}>
        {from_str}
        WHERE {{
            ?s ?p ?o
        }}"""

        result = int(
            sparql_query(sparql_url, virtuoso_user, virtuoso_password, query)[
                "results"
            ]["bindings"][0]["total"]["value"]
        )
        return result

    def delete_graph(self, user: User, source_name: str, method: str = "api"):
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        self.log.info(f"Removing graph {graph_uri} with method {method}")
        if method == "api":
            return self._delete_graph_with_api(graph_uri)
        if method == "isql":
            return self._delete_graph_with_isql(graph_uri)
        else:
            raise NotImplementedError(f"Method {method} is not implemented")

    def _delete_graph_with_isql(self, graph_uri: str):
        cursor = get_isql_connection(
            self.config.get("virtuoso", "host"),
            self.config.get("virtuoso", "isql_port"),
            self.config.get("virtuoso", "user"),
            self.config.get("virtuoso", "password"),
            Path(self.config.get("virtuoso", "driver")),
        )

        query = f"SPARQL DROP SILENT GRAPH <{graph_uri}>"
        cursor.execute(query)
        cursor.execute("exec('checkpoint')")

    def _delete_graph_with_api(self, graph_uri: str):
        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_url = sparql_url.removesuffix("/sparql")

        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        self.log.info(f"removing {graph_uri}…")

        response = requests.delete(
            f"{virtuoso_url}/sparql-graph-crud-auth",
            auth=HTTPDigestAuth(virtuoso_user, virtuoso_password),
            params={"graph-uri": graph_uri},
        )
        if response.status_code not in (200, 201, 404):
            self.log.info(f"Got {response.status_code} while deleting graph")
        sleep(3)  # give virtuoso enough time to delete the graph

    @staticmethod
    def remove_named_individuals_from_graph(graph):
        namedIndividual = URIRef(OWL["NamedIndividual"])
        new_graph = Graph()
        for s, p, o in graph:
            if o != namedIndividual:
                new_graph.add((s, p, o))
        return new_graph

    def get_rdf_graph(
        self,
        user: User,
        graph_path: Path,
        source_name: str,
        format: str = "nt",
        skip_named_individuals: bool = False,
        method: str = "sparql",
    ):
        self.log.info(f"Getting rdf graph with {method}")
        if method == "api":
            graph = self._get_rdf_graph_from_virtuoso_api(user, source_name)
        elif method == "sparql":
            graph = self._get_rdf_graph_from_endpoint(user, source_name)
        elif method == "isql":
            graph = self._get_rdf_graph_from_isql(user, source_name)
        else:
            raise NotImplementedError(f"Method {method} is not implemented")

        if skip_named_individuals:
            graph = self.remove_named_individuals_from_graph(graph)

        # write graph to tmpfile
        graph.serialize(destination=graph_path, format=format, encoding="utf-8")
        self.log.info(f"{source_name} writed to {graph_path}")

        return graph_path

    def _get_rdf_graph_from_isql(self, user: User, source_name: str):
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        cursor = get_isql_connection(
            self.config.get("virtuoso", "host"),
            self.config.get("virtuoso", "isql_port"),
            self.config.get("virtuoso", "user"),
            self.config.get("virtuoso", "password"),
            Path(self.config.get("virtuoso", "driver")),
        )

        query = (
            "SPARQL SELECT ?s ?p ?o ?is_uri ?is_blank ?datatype ?lang "
            f"FROM <{graph_uri}> "
            "WHERE { "
            "?s ?p ?o "
            "BIND(isUri(?o) AS ?is_uri) "
            "BIND(isBlank(?o) AS ?is_blank) "
            "BIND(datatype(?o) AS ?datatype) "
            "BIND(lang(?o) AS ?lang) "
            "}"
        )

        results = cursor.execute(query).fetchall()
        graph = Graph()

        for subj, pred, obj, is_uri, is_blank, datatype, lang in results:
            s = URIRef(subj)
            p = URIRef(pred)
            if is_uri or is_blank:
                o = URIRef(obj)
            else:
                if datatype == "http://www.w3.org/2001/XMLSchema#dateTime":
                    parsed_obj = dateparser.parse(obj)
                    if parsed_obj:
                        obj = parsed_obj.strftime("%Y-%m-%dT%H:%M:%S")
                o = Literal(obj, datatype=datatype, lang=lang)
            graph.add((s, p, o))

        return graph

    def _get_rdf_graph_from_virtuoso_api(
        self,
        user: User,
        source_name: str,
    ):
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        virtuoso_url = sparql_url.removesuffix("/sparql")

        params = {"graph": graph_uri, "format": "application/rdf+json"}
        response = requests.get(
            f"{virtuoso_url}/sparql-graph-crud",
            params=params,
            auth=HTTPDigestAuth(virtuoso_user, virtuoso_password),
        )
        json = response.json()

        graph = Graph()

        for subj, pred_obj in json.items():
            for pred, objs in pred_obj.items():
                for obj in objs:
                    s = URIRef(subj)
                    p = URIRef(pred)
                    if obj["type"] == "uri":
                        o = URIRef(obj["value"])
                    else:
                        obj.pop("type")
                        o = Literal(obj.pop("value"), **obj)
                    graph.add((s, p, o))
        return graph

    def get_source_uri(self, user: User, import_name: str) -> str:
        sources = self.get_sources(user.token)
        return sources[import_name]["graphUri"]

    def get_imports(self, user: User, source_name: str) -> list[str]:
        sources = self.get_sources(user.token)
        return sources[source_name].get("imports", [])

    def get_source_owner(self, user: User, source_name: str) -> str:
        sources = self.get_sources(user.token)
        return sources[source_name].get("owner", "")

    def _get_imports_string(
        self, user: User, source_name: str, imports: List[str]
    ) -> str:
        sources = self.get_sources(user.token)
        imports = sources[source_name]["imports"]
        import_graphs = [f"FROM <{sources[imp]['graphUri']}>" for imp in imports]
        return "\n".join(import_graphs)

    def get_subgraph_from_endpoint(
        self,
        user: User,
        source_name: str,
        limit: int,
        offset: int,
        add_imports: bool = False,
    ):
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        from_str = ""
        if add_imports:
            from_str = self._get_imports_string(
                user, source_name, sources[source_name]["imports"]
            )

        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        # get a subgraph
        query = f"""CONSTRUCT {{ ?s ?p ?o . }}
        FROM <{graph_uri}>
        {from_str}
        WHERE {{
            ?s ?p ?o .
        }}
        LIMIT {limit}
        OFFSET {offset}"""

        return sparql_query(sparql_url, virtuoso_user, virtuoso_password, query, "xml")

    def _get_rdf_graph_from_endpoint(
        self,
        user: User,
        source_name: str,
    ):
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        limit = self.config.getint("rdf", "batch_size")
        graph_size = self._get_graph_size(user, source_name)
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

        return graph

    def _clean_published_graph(self, tmp_graph_name):
        tmp_dir = Path(tempfile.gettempdir())
        tmp_graph_dir = tmp_dir / Path("sls_api")
        tmp_graph_path = tmp_graph_dir / Path(tmp_graph_name)

        tmp_graph_path.unlink(missing_ok=True)

    def _publish_graph(self, graph_path: Path) -> str:
        tmp_dir = Path(tempfile.gettempdir())
        tmp_graph_dir = tmp_dir / Path("sls_api")
        tmp_graph_name = "".join(random.choice(ascii_lowercase) for _ in range(20))
        tmp_graph_path = tmp_graph_dir / Path(tmp_graph_name)

        shutil.copy(graph_path, tmp_graph_path)

        return tmp_graph_name

    def convert_blank_nodes_to_uris(self, graph_path: Path) -> bool:
        graph = RdfGraph(graph_path)
        had_blank_nodes = has_blank_nodes(graph)
        if had_blank_nodes:
            self.log.info(f"Converting blank nodes to URIs in {graph_path}")
            graph = replace_blank_nodes_with_uris(graph)

            EXTENSION_TO_FORMAT = {
                ".nt": "nt",
                ".ttl": "turtle",
                ".rdf": "xml",
                ".owl": "xml",
                ".n3": "n3",
                ".trig": "trig",
            }
            fmt = EXTENSION_TO_FORMAT.get(graph_path.suffix, "nt")
            graph.serialize(destination=str(graph_path), format=fmt, encoding="utf-8")
        return had_blank_nodes

    def upload_rdf_graph(
        self,
        user: User,
        graph_path: Path,
        source_name: str,
        remove_graph: bool = False,
        upload_method: str = "sparql",
        delete_method: str = "api",
    ) -> tuple[bool, bool]:
        if remove_graph:
            self.delete_graph(user, source_name, delete_method)

        had_blank_nodes = False
        blank_nodes_converted = False
        if self.config.getboolean("rdf", "convert_blank_nodes_to_uris", fallback=True):
            had_blank_nodes = self.convert_blank_nodes_to_uris(graph_path)
            blank_nodes_converted = had_blank_nodes

        self.log.info(f"Uploading rdf graph with method {upload_method}")
        if upload_method == "api":
            self._upload_rdf_graph_with_virtuoso_api(user, graph_path, source_name)
        elif upload_method == "api_batched":
            self._upload_rdf_graph_with_virtuoso_api_batched(
                user, graph_path, source_name
            )
        elif upload_method == "sparql_load":
            tmp_graph_name = self._publish_graph(graph_path)
            base_url = self.config.get("main", "api_url_for_virtuoso")
            graph_url = f"{base_url}/files/{tmp_graph_name}"
            self._upload_rdf_graph_from_url(user, graph_url, source_name)
            self._clean_published_graph(tmp_graph_name)
        else:
            raise NotImplementedError(
                f"upload_method {upload_method} is not implemented"
            )

        return had_blank_nodes, blank_nodes_converted

    def _upload_rdf_graph_from_url(self, user: User, graph_url: str, source_name: str):
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        query = f"LOAD <{graph_url}> INTO GRAPH <{graph_uri}>"

        sparql_query(sparql_url, virtuoso_user, virtuoso_password, query)

    def _upload_rdf_graph_with_virtuoso_api(
        self, user: User, graph_path: Path, source_name: str
    ) -> bool:
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_url = sparql_url.removesuffix("/sparql")
        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        response = requests.post(
            f"{virtuoso_url}/sparql-graph-crud-auth",
            params={"graph-uri": graph_uri},
            headers={"Content-type": "text/plain"},
            data=graph_path.open("rb"),
            auth=HTTPDigestAuth(virtuoso_user, virtuoso_password),
        )
        if not response.ok:
            raise (
                BaseException(
                    f"Got {response.status_code} while posting graph {graph_uri}.\n{response.content}"
                )
            )
        return

    def _upload_rdf_graph_with_virtuoso_api_batched(
        self, user: User, graph_path: Path, source_name: str
    ) -> bool:
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        # parse uploaded file into rdfilb graph
        self.log.info(f"Parse graph {graph_uri}")
        graph = RdfGraph(graph_path)
        self.log.info(f"Graph {graph_uri} parsed!")

        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_url = sparql_url.removesuffix("/sparql")
        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

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
        return

    def _check_blank_nodes(self, graph_path: Path) -> bool:
        graph = RdfGraph(graph_path)
        return has_blank_nodes(graph)

    def _feed_graph_with_sls_data(self, data: list, graph: RdfGraph) -> None:
        for elem in data:
            graph.add(
                (
                    get_uri_from_str(elem["subject"], graph),
                    get_uri_from_str(elem["predicate"], graph),
                    guess_triple_type(elem["object"], graph),
                )
            )

    def convert_rdf_format(self, raw_data, input_format, output_format) -> str:
        graph = RdfGraph()

        if input_format == "sls":
            # create a rdf graph from sls custom format
            json_data = json.loads(raw_data)
            prefixes = json_data["prefixes"]
            for prefix, uri in prefixes.items():
                graph.bind(prefix, URIRef(uri))
            data = json_data["data"]
            self._feed_graph_with_sls_data(data, graph)
        else:
            graph.parse(raw_data, format=input_format)

        result = graph.serialize(format=output_format, encoding="utf-8").decode()
        return result

    def ask(self, user: User, source_name: str, triple: Triple) -> bool:
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        sparql_url = self.config.get("virtuoso", "sparql_url")
        virtuoso_user = self.config.get("virtuoso", "user")
        virtuoso_password = self.config.get("virtuoso", "password")

        s, p, o = triple

        query = f"ASK FROM <{graph_uri}> {{ {s.n3()} {p.n3()} {o.n3()} . }}"
        result = sparql_query(sparql_url, virtuoso_user, virtuoso_password, query)
        return result["boolean"]

    def gen_contributor_triple(
        self, user: User, source_name: str, contributor: str
    ) -> Triple:
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]

        s = URIRef(graph_uri)
        p = DC.contributor
        o = Literal(contributor, datatype=XSD.string)

        return (s, p, o)

    def gen_import_triples(
        self, user: User, source_name: str, import_uris: list[str]
    ) -> list[Triple]:
        sources = self.get_sources(user.token)
        graph_uri = sources[source_name]["graphUri"]
        results = []
        for uri in import_uris:
            s = URIRef(graph_uri)
            p = OWL.imports
            o = URIRef(uri)
            results.append(
                (s, p, o),
            )

        return results
