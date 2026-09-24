from unittest.mock import Mock

import pytest
from rdflib import Graph, BNode, URIRef, Literal, XSD
from SPARQLWrapper import JSON, XML

from sls_api.utils import (
    get_isql_connection,
    get_uri_from_str,
    guess_triple_type,
    has_blank_nodes,
    replace_blank_nodes_with_uris,
    sparql_query,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (1, Literal(1, datatype=XSD.integer)),
        (1.2, Literal(1.2, datatype=XSD.float)),
        ("2025-02-27T12:16:00", Literal("2025-02-27T12:16:00", datatype=XSD.dateTime)),
        ("2025-02-27", Literal("2025-02-27", datatype=XSD.date)),
        ("toto", Literal("toto")),
    ],
)
def test_guess_triple_type(value, expected):
    assert guess_triple_type(value, Graph()) == expected


def test_guess_triple_type_uri():
    result = guess_triple_type("http://example.org/s", Graph())
    assert result == URIRef("http://example.org/s")


def test_get_uri_from_string_blanknode():
    bnode = get_uri_from_str("_:toto", Graph())
    assert isinstance(bnode, BNode)
    assert bnode == BNode("toto")


def test_get_uri_from_string_blanknode_with_empty_str():
    bnode = get_uri_from_str("_:", Graph())
    assert isinstance(bnode, BNode)
    assert len(bnode) == 33


def test_get_uri_from_string_uri():
    uri_str = "http://example.org/toto"
    assert get_uri_from_str(uri_str, Graph()) == URIRef(uri_str)


def test_get_uri_from_string_curie_standard():
    assert get_uri_from_str("owl:sameAs", Graph()) == URIRef(
        "http://www.w3.org/2002/07/owl#sameAs"
    )


def test_get_uri_from_string_curie_custom():
    g = Graph()
    g.bind("toto", "http://example.org/toto#")
    assert get_uri_from_str("toto:titi", g) == URIRef("http://example.org/toto#titi")


def test_get_uri_from_string_curie_custom_error():
    with pytest.raises(ValueError):
        get_uri_from_str("toto:titi", Graph())


def test_has_blank_nodes_with_blank_nodes():
    g = Graph()
    bnode = BNode("test1")
    g.add((bnode, URIRef("http://example.org/pred"), URIRef("http://example.org/obj")))
    assert has_blank_nodes(g) is True


def test_has_blank_nodes_without_blank_nodes():
    g = Graph()
    g.add(
        (
            URIRef("http://example.org/subj"),
            URIRef("http://example.org/pred"),
            URIRef("http://example.org/obj"),
        )
    )
    assert has_blank_nodes(g) is False


def test_bnode_in_subject_converted_to_uri():
    g = Graph()
    bnode = BNode("b1")
    g.add((bnode, URIRef("http://example.org/pred"), URIRef("http://example.org/obj")))
    result = replace_blank_nodes_with_uris(g)
    for s, p, o in result:
        assert isinstance(s, URIRef)
        assert str(s) == "_:b1"
        assert not isinstance(s, BNode)


def test_bnode_in_object_converted_to_uri():
    g = Graph()
    bnode = BNode("b2")
    g.add((URIRef("http://example.org/subj"), URIRef("http://example.org/pred"), bnode))
    result = replace_blank_nodes_with_uris(g)
    for s, p, o in result:
        assert isinstance(o, URIRef)
        assert str(o) == "_:b2"
        assert not isinstance(o, BNode)


def test_connected_bnodes_preserve_references():
    g = Graph()
    b1 = BNode("b1")
    b2 = BNode("b2")
    g.add((b1, URIRef("http://example.org/knows"), b2))
    result = replace_blank_nodes_with_uris(g)
    for s, p, o in result:
        assert str(s) == "_:b1"
        assert str(o) == "_:b2"


def test_same_bnode_references_map_to_same_uri():
    g = Graph()
    b1 = BNode("b1")
    g.add((b1, URIRef("http://example.org/name"), Literal("Alice")))
    g.add((b1, URIRef("http://example.org/age"), Literal("30")))
    result = replace_blank_nodes_with_uris(g)
    subjects = [s for s, p, o in result]
    assert len(subjects) == 2
    assert subjects[0] == subjects[1] == URIRef("_:b1")


def test_graph_without_bnodes_unchanged():
    g = Graph()
    g.add(
        (
            URIRef("http://example.org/s"),
            URIRef("http://example.org/p"),
            URIRef("http://example.org/o"),
        )
    )
    result = replace_blank_nodes_with_uris(g)
    assert len(result) == 1
    for s, p, o in result:
        assert s == URIRef("http://example.org/s")
        assert o == URIRef("http://example.org/o")


def test_empty_graph_returns_empty_graph():
    assert len(replace_blank_nodes_with_uris(Graph())) == 0


@pytest.mark.parametrize(
    "format,expected",
    [("json", JSON), ("xml", XML), ("unknown", "json")],
)
def test_sparql_query(monkeypatch, format, expected):
    mock_endpoint = Mock()
    monkeypatch.setattr("sls_api.utils.SPARQLWrapper", Mock(return_value=mock_endpoint))
    sparql_query("http://virtuoso/sparql", "user", "pass", "SELECT ?s", format)

    mock_endpoint.setReturnFormat.assert_called_once_with(expected)
    mock_endpoint.setQuery.assert_called_once_with("SELECT ?s")
    mock_endpoint.queryAndConvert.assert_called_once()


def test_get_isql_connection(monkeypatch):
    mock_cursor = Mock()
    mock_connection = Mock()
    mock_connection.cursor.return_value = mock_cursor
    monkeypatch.setattr(
        "sls_api.utils.pyodbc.connect", Mock(return_value=mock_connection)
    )

    cursor = get_isql_connection("host", "1111", "user", "pass", "/driver")

    assert cursor == mock_cursor
    mock_connection.setencoding.assert_called_once_with(encoding="utf-8")
    mock_connection.setdecoding.assert_called()
