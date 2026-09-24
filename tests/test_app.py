import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from rdflib import Graph, URIRef, Literal, BNode, XSD
from rdflib.namespace import DC, OWL, RDF

from sls_api.app import App

PRED = URIRef("http://example.org/p")
OBJ = URIRef("http://example.org/o")
SUBJ = URIRef("http://example.org/s")


def make_nt_file(tmp_path: Path, content: str = None) -> Path:
    path = tmp_path / "graph.nt"
    path.write_text(content or f"{SUBJ.n3()} {PRED.n3()} {OBJ.n3()} .")
    return path


def test_get_updated_permission_matrix(app):
    cases = [
        ("forbidden", "read", "read"),
        ("forbidden", "readwrite", "readwrite"),
        ("read", "forbidden", "read"),
        ("read", "read", "readwrite"),
        ("read", "readwrite", "readwrite"),
        ("readwrite", "forbidden", "readwrite"),
    ]
    for existing, new, expected in cases:
        assert app.get_updated_permission(existing, new) == expected


def test_get_permission_from_profile_no_match(app):
    profiles = {"default": {"sourcesAccessControl": {"sls:other": "readwrite"}}}
    assert app._get_permission_from_profile(profiles, "sls:test") == "forbidden"


def test_get_permission_from_profile_simple_match(app):
    profiles = {"default": {"sourcesAccessControl": {"sls:": "read"}}}
    assert app._get_permission_from_profile(profiles, "sls:test_ro") == "read"


def test_get_permission_from_profile_longest_prefix_wins(app):
    profiles = {
        "default": {
            "sourcesAccessControl": {
                "sls:": "read",
                "sls:test": "readwrite",
            }
        }
    }
    assert app._get_permission_from_profile(profiles, "sls:test_ro") == "readwrite"


def test_get_permission_from_profile_aggregates_profiles(app):
    profiles = {
        "p1": {"sourcesAccessControl": {"sls:": "read"}},
        "p2": {"sourcesAccessControl": {"sls:": "readwrite"}},
    }
    assert app._get_permission_from_profile(profiles, "sls:test_ro") == "readwrite"


def test_get_user_sources_sets_access_control(app, monkeypatch, sources, profiles):
    monkeypatch.setattr(app, "get_profiles", Mock(return_value=profiles))
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))

    user_sources = app._get_user_sources(Mock(token="token"))

    assert user_sources["test_ro"]["accessControl"] == "read"
    assert user_sources["test_rw"]["accessControl"] == "readwrite"


def test_get_user_sources_default_group(app, monkeypatch):
    sources = {
        "id1": {"name": "test_ro", "group": "  ", "schemaType": "sls"},
    }
    profiles = {"default": {"sourcesAccessControl": {"sls/DEFAULT/test_ro": "read"}}}
    monkeypatch.setattr(app, "get_profiles", Mock(return_value=profiles))
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))

    user_sources = app._get_user_sources(Mock(token="token"))

    assert user_sources["id1"]["accessControl"] == "read"


def test_remove_named_individuals_from_graph():
    g = Graph()
    s = URIRef("http://example.org/s")
    g.add((s, RDF.type, OWL.NamedIndividual))
    g.add((s, PRED, Literal("x")))
    result = App.remove_named_individuals_from_graph(g)
    assert len(result) == 1
    assert (s, PRED, Literal("x")) in result


def test_gen_contributor_triple(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    triple = app.gen_contributor_triple(Mock(), "test_rw", "Alice")
    assert triple == (
        URIRef(sources["test_rw"]["graphUri"]),
        DC.contributor,
        Literal("Alice", datatype=XSD.string),
    )


def test_gen_import_triples(app, monkeypatch, sources):
    monkeypatch.setattr(app, "get_sources", Mock(return_value=sources))
    triples = app.gen_import_triples(Mock(), "test_rw", ["http://example.org/imp1"])
    assert triples == [
        (
            URIRef(sources["test_rw"]["graphUri"]),
            OWL.imports,
            URIRef("http://example.org/imp1"),
        )
    ]


def test_feed_graph_with_sls_data(app):
    graph = Graph()
    graph.bind("", "http://example.org/")
    graph.bind("toto", "http://example.org/toto#")
    data = [
        {"subject": ":x", "predicate": "toto:valeur", "object": 1.2},
        {"subject": "_:b", "predicate": "toto:autre", "object": "hi"},
    ]
    app._feed_graph_with_sls_data(data, graph)
    assert len(graph) == 2
    assert (
        URIRef("http://example.org/x"),
        URIRef("http://example.org/toto#valeur"),
        Literal(1.2, datatype=XSD.float),
    ) in graph
    assert (
        BNode("b"),
        URIRef("http://example.org/toto#autre"),
        Literal("hi"),
    ) in graph


def test_convert_rdf_format_from_sls(app, sls_data):
    raw = sls_data.read_bytes()
    result = app.convert_rdf_format(raw, "sls", "turtle")
    graph = Graph().parse(data=result, format="turtle")
    assert (
        URIRef("http://example.org/xavier"),
        URIRef("http://example.org/toto#valeur"),
        Literal(1.2, datatype=XSD.float),
    ) in graph


def test_convert_rdf_format_from_nt(app, graph_without_blank_nodes):
    raw = graph_without_blank_nodes.read_bytes()
    result = app.convert_rdf_format(raw, "nt", "turtle")
    graph = Graph().parse(data=result, format="turtle")
    assert len(graph) == len(Graph().parse(graph_without_blank_nodes, format="nt"))


def test_convert_blank_nodes_to_uris_rewrites_file(
    app, tmp_path, graph_with_blank_nodes
):
    target = tmp_path / "with_blank.nt"
    target.write_text(graph_with_blank_nodes.read_text())
    assert app.convert_blank_nodes_to_uris(target) is True
    result = Graph().parse(target, format="nt")
    assert all(not isinstance(node, BNode) for node in list(result.all_nodes()))


def test_convert_blank_nodes_to_uris_noop(app, tmp_path, graph_without_blank_nodes):
    target = tmp_path / "no_blank.nt"
    target.write_text(graph_without_blank_nodes.read_text())
    assert app.convert_blank_nodes_to_uris(target) is False


def test_check_blank_nodes(app, graph_with_blank_nodes, graph_without_blank_nodes):
    assert app._check_blank_nodes(graph_with_blank_nodes) is True
    assert app._check_blank_nodes(graph_without_blank_nodes) is False


def test_publish_and_clean_graph(app, tmp_path):
    import tempfile

    graph_path = make_nt_file(tmp_path)
    tmp_name = app._publish_graph(graph_path)
    published_dir = Path(tempfile.gettempdir()) / "sls_api"
    assert (published_dir / tmp_name).exists()
    app._clean_published_graph(tmp_name)
    assert not (published_dir / tmp_name).exists()


def test_upload_rdf_graph_api_dispatch(app, monkeypatch, user, tmp_path):
    upload = Mock(return_value=None)
    monkeypatch.setattr(app, "_upload_rdf_graph_with_virtuoso_api", upload)
    graph_path = make_nt_file(tmp_path)
    result = app.upload_rdf_graph(user, graph_path, "test_rw", upload_method="api")
    upload.assert_called_once_with(user, graph_path, "test_rw")
    assert result == (False, False)


def test_upload_rdf_graph_blank_nodes_flags(
    app, monkeypatch, user, tmp_path, graph_with_blank_nodes
):
    monkeypatch.setattr(app, "_upload_rdf_graph_with_virtuoso_api", Mock())
    target = tmp_path / "with_blank.nt"
    target.write_text(graph_with_blank_nodes.read_text())
    result = app.upload_rdf_graph(user, target, "test_rw", upload_method="api")
    assert result == (True, True)


def test_upload_rdf_graph_sparql_load_dispatch(app, monkeypatch, user, tmp_path):
    monkeypatch.setattr(app, "_publish_graph", Mock(return_value="tmpname"))
    monkeypatch.setattr(app, "_upload_rdf_graph_from_url", Mock())
    monkeypatch.setattr(app, "_clean_published_graph", Mock())
    graph_path = make_nt_file(tmp_path)
    app.upload_rdf_graph(user, graph_path, "test_rw", upload_method="sparql_load")
    base_url = app.config.get("main", "api_url_for_virtuoso")
    app._upload_rdf_graph_from_url.assert_called_once_with(
        user, f"{base_url}/files/tmpname", "test_rw"
    )
    app._clean_published_graph.assert_called_once_with("tmpname")


def test_upload_rdf_graph_remove_graph(app, monkeypatch, user, tmp_path):
    delete = Mock()
    monkeypatch.setattr(app, "delete_graph", delete)
    monkeypatch.setattr(app, "_upload_rdf_graph_with_virtuoso_api", Mock())
    graph_path = make_nt_file(tmp_path)
    app.upload_rdf_graph(
        user, graph_path, "test_rw", remove_graph=True, upload_method="api"
    )
    delete.assert_called_once_with(user, "test_rw", "api")


def test_upload_rdf_graph_unknown_method(app, user, tmp_path):
    with pytest.raises(NotImplementedError):
        app.upload_rdf_graph(
            user, make_nt_file(tmp_path), "test_rw", upload_method="unknown"
        )
