import configparser
import shutil
from pathlib import Path

import pytest

from sls_api.app import App
from sls_api.users import User

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SOURCES = {
    "test_ro": {
        "graphUri": "http://example.org/graph/ro",
        "name": "test_ro",
        "group": "DEFAULT",
        "schemaType": "sls",
        "accessControl": "read",
    },
    "test_rw": {
        "graphUri": "http://example.org/graph/rw",
        "name": "test_rw",
        "group": "DEFAULT",
        "schemaType": "sls",
        "accessControl": "readwrite",
    },
}

DEFAULT_PROFILES = {
    "default": {
        "sourcesAccessControl": {
            "sls/DEFAULT/test_ro": "read",
            "sls/DEFAULT/test_rw": "readwrite",
        },
    },
}


def write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.ini"
    parser = configparser.ConfigParser()
    parser["main"] = {
        "api_path": "/sls-api",
        "api_url_for_virtuoso": "http://virtuoso:8000",
        "souslesens_api_url": "http://sls-api:3010/api/v1",
        "log_level": "info",
        "get_rdf_graph_method": "api",
        "post_rdf_graph_method": "api",
        "delete_rdf_graph_method": "api",
        "chunk_size": "1000000",
    }
    parser["virtuoso"] = {
        "driver": "/usr/lib/x86_64-linux-gnu/odbc/virtodbc_r.so",
        "sparql_url": "http://virtuoso:8890/sparql",
        "host": "virtuoso",
        "isql_port": "1111",
        "user": "dba",
        "password": "dba",
    }
    parser["cors"] = {
        "origins": "*",
        "allowed_methods": "*",
        "allowed_headers": "*",
        "allowed_credentials": "yes",
    }
    parser["rdf"] = {
        "batch_size": "1000",
        "convert_blank_nodes_to_uris": "true",
    }
    with config_path.open("w") as fp:
        parser.write(fp)
    return config_path


@pytest.fixture(scope="session", autouse=True)
def ensure_config_file():
    config_ini = PROJECT_ROOT / "config.ini"
    if not config_ini.exists():
        shutil.copy(PROJECT_ROOT / "config.ini.default", config_ini)


@pytest.fixture
def app(tmp_path) -> App:
    return App(config_path=str(write_config(tmp_path)))


@pytest.fixture
def user() -> User:
    user = User(groups=[], id="test", login="test")
    user.set_sources(DEFAULT_SOURCES)
    return user


@pytest.fixture
def sources() -> dict:
    return DEFAULT_SOURCES


@pytest.fixture
def profiles() -> dict:
    return DEFAULT_PROFILES


@pytest.fixture
def graph_with_blank_nodes() -> Path:
    return PROJECT_ROOT / "with_blank_nodes.nt"


@pytest.fixture
def graph_without_blank_nodes() -> Path:
    return PROJECT_ROOT / "without_blank_nodes.nt"


@pytest.fixture
def sls_data() -> Path:
    return PROJECT_ROOT / "data.json"
