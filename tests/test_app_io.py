import importlib

from unittest.mock import Mock

import pytest
from rdflib import Graph, URIRef, Literal, XSD
from rdflib.namespace import OWL, RDF

from sls_api.users import User

app_module = importlib.import_module("sls_api.app")


def make_response(status_code=200, json_data=None, ok=True):
    response = Mock()
    response.status_code = status_code
    response.ok = ok
    response.json.return_value = json_data or {}
    response.content = b"error"
    return response


def test_get_user_from_token(app, monkeypatch):
    user_data = {"groups": [], "id": "1", "login": "alice"}
    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(return_value=make_response(json_data=user_data)),
    )
    user = app.get_user_from_token("token")
    assert isinstance(user, User)
    assert user.login == "alice"


def test_get_sls_config(app, monkeypatch):
    config = {"sparqlDownloadLimit": 100}
    monkeypatch.setattr(
        app_module.requests, "get", Mock(return_value=make_response(json_data=config))
    )
    assert app.get_sls_config("token") == config


def test_get_profiles(app, monkeypatch):
    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(return_value=make_response(json_data={"resources": {"p": {}}})),
    )
    assert app.get_profiles("token") == {"p": {}}


def test_get_sources(app, monkeypatch):
    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(return_value=make_response(json_data={"resources": {"s": {}}})),
    )
    assert app.get_sources("token") == {"s": {}}


def test_cache_clear(app, monkeypatch):
    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(return_value=make_response(json_data={"resources": {}})),
    )
    app.get_sls_config("token")
    app.get_profiles("token")
    app.get_sources("token")
    app.cache_clear()
    app.get_sls_config("token")
    app.get_profiles("token")
    app.get_sources("token")


def test_get_source_uri(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    assert app.get_source_uri(Mock(), "test_rw") == sources["test_rw"]["graphUri"]


def test_get_imports(app, monkeypatch, sources):
    sources["test_rw"]["imports"] = ["test_ro"]
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    assert app.get_imports(Mock(), "test_rw") == ["test_ro"]


def test_get_source_owner(app, monkeypatch, sources):
    sources["test_rw"]["owner"] = "alice"
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    assert app.get_source_owner(Mock(), "test_rw") == "alice"


def test_get_imports_string(app, monkeypatch, sources):
    sources["test_rw"]["imports"] = ["test_ro"]
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    result = app._get_imports_string(Mock(), "test_rw", ["test_ro"])
    assert result == f"FROM <{sources['test_ro']['graphUri']}>"


def test_get_graph_size(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    monkeypatch.setattr(
        app_module,
        "sparql_query",
        Mock(return_value={"results": {"bindings": [{"total": {"value": "42"}}]}}),
    )
    assert app._get_graph_size(Mock(), "test_rw") == 42


def test_get_subgraph_from_endpoint(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    sparql = Mock(return_value=Graph())
    monkeypatch.setattr(app_module, "sparql_query", sparql)
    app.get_subgraph_from_endpoint(Mock(), "test_rw", limit=10, offset=20)
    query = sparql.call_args[0][3]
    assert "LIMIT 10" in query
    assert "OFFSET 20" in query
    assert sources["test_rw"]["graphUri"] in query


def test_get_subgraph_from_endpoint_with_imports(app, monkeypatch, sources):
    sources["test_rw"]["imports"] = ["test_ro"]
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    sparql = Mock(return_value=Graph())
    monkeypatch.setattr(app_module, "sparql_query", sparql)
    app.get_subgraph_from_endpoint(
        Mock(), "test_rw", limit=10, offset=0, add_imports=True
    )
    query = sparql.call_args[0][3]
    assert sources["test_ro"]["graphUri"] in query


def test_ask(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    monkeypatch.setattr(
        app_module, "sparql_query", Mock(return_value={"boolean": True})
    )
    triple = (
        URIRef("http://example.org/graph/rw"),
        URIRef("http://example.org/p"),
        Literal("x"),
    )
    assert app.ask(Mock(), "test_rw", triple) is True


def test_get_rdf_graph_api(app, monkeypatch, user, tmp_path, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/s"),
            URIRef("http://example.org/p"),
            URIRef("http://example.org/o"),
        )
    )
    monkeypatch.setattr(
        app, "_get_rdf_graph_from_virtuoso_api", Mock(return_value=graph)
    )
    target = tmp_path / "out.nt"
    result = app.get_rdf_graph(user, target, "test_rw", format="nt", method="api")
    assert result == target
    assert len(Graph().parse(target, format="nt")) == 1


def test_get_rdf_graph_skip_named_individuals(app, monkeypatch, user, tmp_path):
    graph = Graph()
    s = URIRef("http://example.org/s")
    graph.add((s, RDF.type, OWL.NamedIndividual))
    graph.add((s, URIRef("http://example.org/p"), Literal("x")))
    monkeypatch.setattr(
        app, "_get_rdf_graph_from_virtuoso_api", Mock(return_value=graph)
    )
    target = tmp_path / "out.nt"
    app.get_rdf_graph(
        user, target, "test_rw", format="nt", skip_named_individuals=True, method="api"
    )
    assert len(Graph().parse(target, format="nt")) == 1


def test_get_rdf_graph_unknown_method(app, user, tmp_path):
    with pytest.raises(NotImplementedError):
        app.get_rdf_graph(user, tmp_path / "out.nt", "test_rw", method="unknown")


def test_get_rdf_graph_from_virtuoso_api(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    payload = {
        "http://example.org/s": {
            "http://example.org/p": [
                {"type": "uri", "value": "http://example.org/o"},
                {"type": "literal", "value": "hello", "lang": "en"},
            ]
        }
    }
    monkeypatch.setattr(
        app_module.requests, "get", Mock(return_value=make_response(json_data=payload))
    )
    graph = app._get_rdf_graph_from_virtuoso_api(Mock(), "test_rw")
    assert (
        URIRef("http://example.org/s"),
        URIRef("http://example.org/p"),
        URIRef("http://example.org/o"),
    ) in graph
    assert (
        URIRef("http://example.org/s"),
        URIRef("http://example.org/p"),
        Literal("hello", lang="en"),
    ) in graph


def test_get_rdf_graph_from_isql(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    rows = [
        (
            "http://example.org/s",
            "http://example.org/p",
            "http://example.org/o",
            True,
            False,
            None,
            None,
        ),
        (
            "http://example.org/s",
            "http://example.org/p",
            "hello",
            False,
            False,
            None,
            "en",
        ),
        (
            "http://example.org/s",
            "http://example.org/p",
            "2025-02-27T12:16:00.000",
            False,
            False,
            "http://www.w3.org/2001/XMLSchema#dateTime",
            None,
        ),
    ]
    cursor = Mock()
    cursor.execute.return_value.fetchall.return_value = rows
    monkeypatch.setattr(app_module, "get_isql_connection", Mock(return_value=cursor))
    graph = app._get_rdf_graph_from_isql(Mock(), "test_rw")
    assert (
        URIRef("http://example.org/s"),
        URIRef("http://example.org/p"),
        URIRef("http://example.org/o"),
    ) in graph
    assert (
        URIRef("http://example.org/s"),
        URIRef("http://example.org/p"),
        Literal("hello", lang="en"),
    ) in graph
    assert (
        URIRef("http://example.org/s"),
        URIRef("http://example.org/p"),
        Literal("2025-02-27T12:16:00", datatype=XSD.dateTime),
    ) in graph


def test_delete_graph_dispatch_api(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    delete_api = Mock()
    monkeypatch.setattr(app, "_delete_graph_with_api", delete_api)
    app.delete_graph(Mock(), "test_rw", method="api")
    delete_api.assert_called_once_with(sources["test_rw"]["graphUri"])


def test_delete_graph_dispatch_isql(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    delete_isql = Mock()
    monkeypatch.setattr(app, "_delete_graph_with_isql", delete_isql)
    app.delete_graph(Mock(), "test_rw", method="isql")
    delete_isql.assert_called_once_with(sources["test_rw"]["graphUri"])


def test_delete_graph_unknown_method(app, sources, monkeypatch):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    with pytest.raises(NotImplementedError):
        app.delete_graph(Mock(), "test_rw", method="unknown")


def test_delete_graph_with_api(app, monkeypatch, sources):
    monkeypatch.setattr(app_module, "sleep", Mock())
    monkeypatch.setattr(
        app_module.requests,
        "delete",
        Mock(return_value=make_response(status_code=200)),
    )
    app._delete_graph_with_api(sources["test_rw"]["graphUri"])


def test_delete_graph_with_api_non_ok(app, monkeypatch, sources):
    monkeypatch.setattr(app_module, "sleep", Mock())
    monkeypatch.setattr(
        app_module.requests,
        "delete",
        Mock(return_value=make_response(status_code=500)),
    )
    app._delete_graph_with_api(sources["test_rw"]["graphUri"])


def test_delete_graph_with_isql(app, monkeypatch):
    cursor = Mock()
    monkeypatch.setattr(app_module, "get_isql_connection", Mock(return_value=cursor))
    app._delete_graph_with_isql("http://example.org/graph")
    assert cursor.execute.call_count == 2


def test_upload_rdf_graph_from_url(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    sparql = Mock()
    monkeypatch.setattr(app_module, "sparql_query", sparql)
    app._upload_rdf_graph_from_url(Mock(), "http://server/files/x", "test_rw")
    query = sparql.call_args[0][3]
    assert query == (
        f"LOAD <http://server/files/x> INTO GRAPH <{sources['test_rw']['graphUri']}>"
    )


def test_upload_rdf_graph_with_virtuoso_api(app, monkeypatch, sources, tmp_path):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    monkeypatch.setattr(
        app_module.requests,
        "post",
        Mock(return_value=make_response(status_code=201)),
    )
    graph_path = tmp_path / "graph.nt"
    graph_path.write_text(
        "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
    )
    app._upload_rdf_graph_with_virtuoso_api(Mock(), graph_path, "test_rw")


def test_upload_rdf_graph_with_virtuoso_api_error(app, monkeypatch, sources, tmp_path):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    monkeypatch.setattr(
        app_module.requests,
        "post",
        Mock(return_value=make_response(status_code=500, ok=False)),
    )
    graph_path = tmp_path / "graph.nt"
    graph_path.write_text(
        "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
    )
    with pytest.raises(BaseException):
        app._upload_rdf_graph_with_virtuoso_api(Mock(), graph_path, "test_rw")
