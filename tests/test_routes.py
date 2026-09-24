from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import DC

import sls_api
from sls_api.users import User

client = TestClient(sls_api.app)

AUTH = {"Authorization": "Bearer token"}

SOURCE = "test_rw"


def make_user(readwrite: bool = True):
    user = User(groups=[], id="1", login="alice")
    access = "readwrite" if readwrite else "read"
    user.set_sources({SOURCE: {"accessControl": access}})
    return user


@pytest.fixture(autouse=True)
def mock_sls(monkeypatch):
    user = make_user()
    monkeypatch.setattr(sls_api.app, "get_user_from_token", Mock(return_value=user))
    monkeypatch.setattr(
        sls_api.app, "add_sources_for_user", Mock(side_effect=lambda u: u)
    )
    return user


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"health": "ok"}


def test_verify_token_invalid_format():
    resp = client.get(
        "/api/v1/rdf/graph",
        params={"source": SOURCE},
        headers={"Authorization": "not-a-header"},
    )
    assert resp.status_code == 400


def test_verify_token_wrong_scheme():
    resp = client.get(
        "/api/v1/rdf/graph",
        params={"source": SOURCE},
        headers={"Authorization": "Basic token"},
    )
    assert resp.status_code == 405


def test_verify_token_unauthorized(monkeypatch):
    monkeypatch.setattr(sls_api.app, "get_user_from_token", Mock(return_value=None))
    resp = client.get("/api/v1/rdf/graph", params={"source": SOURCE}, headers=AUTH)
    assert resp.status_code == 401


def test_convert_rdf_format(monkeypatch):
    monkeypatch.setattr(
        sls_api.app, "convert_rdf_format", Mock(return_value="<a> <b> <c> .")
    )
    resp = client.post(
        "/api/v1/rdf/convert",
        headers=AUTH,
        files={"data": ("graph.nt", b"<a> <b> <c> .", "application/n-triples")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"data": "<a> <b> <c> ."}


def test_post_rdf_graph(monkeypatch):
    monkeypatch.setattr(
        sls_api.app,
        "upload_rdf_graph",
        Mock(return_value=(True, True)),
    )
    resp = client.post(
        "/api/v1/rdf/graph",
        headers=AUTH,
        data={"last": "true", "clean": "false", "source": SOURCE},
        files={"data": ("graph.nt", b"<a> <b> <c> .", "application/n-triples")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_blank_nodes"] is True
    assert body["blank_nodes_converted"] is True


def test_post_rdf_graph_forbidden(monkeypatch):
    forbidden_user = make_user(readwrite=False)
    monkeypatch.setattr(
        sls_api.app, "add_sources_for_user", Mock(side_effect=lambda u: forbidden_user)
    )
    resp = client.post(
        "/api/v1/rdf/graph",
        headers=AUTH,
        data={"last": "true", "clean": "false", "source": SOURCE},
        files={"data": ("graph.nt", b"<a> <b> <c> .", "application/n-triples")},
    )
    assert resp.status_code == 401


def test_delete_rdf_graph(monkeypatch):
    monkeypatch.setattr(sls_api.app, "delete_graph", Mock())
    resp = client.delete("/api/v1/rdf/graph", headers=AUTH, params={"source": SOURCE})
    assert resp.status_code == 200
    assert resp.json() == {"message": f"{SOURCE} deleted"}


def test_get_rdf_graph_v1(monkeypatch):
    def fake_get_rdf_graph(user, tmpfile, source, **kwargs):
        tmpfile.write_text("hello world")

    monkeypatch.setattr(sls_api.app, "get_rdf_graph", fake_get_rdf_graph)
    resp = client.get("/api/v1/rdf/graph", headers=AUTH, params={"source": SOURCE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == "hello world"
    assert body["next_offset"] is None


def test_get_rdf_graph_v2(monkeypatch):
    graph = Graph()
    graph.add(
        (URIRef("http://example.org/s1"), URIRef("http://example.org/p"), Literal("a"))
    )
    graph.add(
        (URIRef("http://example.org/s2"), URIRef("http://example.org/p"), Literal("b"))
    )
    monkeypatch.setattr(
        sls_api.app, "get_sls_config", Mock(return_value={"sparqlDownloadLimit": 100})
    )
    monkeypatch.setattr(sls_api.app, "_get_graph_size", Mock(return_value=2))
    monkeypatch.setattr(
        sls_api.app, "get_subgraph_from_endpoint", Mock(return_value=graph)
    )
    monkeypatch.setattr(sls_api.app, "get_source_owner", Mock(return_value="owner"))
    monkeypatch.setattr(
        sls_api.app,
        "gen_contributor_triple",
        Mock(
            return_value=(
                URIRef("http://example.org/graph"),
                DC.contributor,
                Literal("owner"),
            )
        ),
    )
    monkeypatch.setattr(sls_api.app, "ask", Mock(return_value=False))
    resp = client.get("/api/v2/rdf/graph", headers=AUTH, params={"source": SOURCE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["graph_size"] == 2
    assert body["next_offset"] is None
    assert "http://example.org/s1" in body["data"]
