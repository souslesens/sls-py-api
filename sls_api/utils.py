from itertools import islice
from re import match as re_match
from typing import Iterator

from rdflib import URIRef, Literal, BNode, XSD, Graph
from SPARQLWrapper import DIGEST, JSON, SPARQLWrapper, XML


def batched(iterable: list, chunk_size: int) -> Iterator[list]:
    """Split an iterable in multiple chunks of a specific size

    Parameters
    ----------
    iterable : list
        The iterable to split
    chunk_size : int
        The maximal size of each chunk

    Yields
    ------
    iter(list)
        A chunk of the iterable as a generator object
    """

    iterator = iter(iterable)
    while chunk := tuple(islice(iterator, chunk_size)):
        yield chunk


def sparql_query(
    virtuoso_url: str,
    virtuoso_user: str,
    virtuoso_password: str,
    query: str,
    format: str = "json",
):
    format_dict = {"json": JSON, "xml": XML}

    endpoint = SPARQLWrapper(virtuoso_url)
    endpoint.setHTTPAuth(DIGEST)
    endpoint.setCredentials(virtuoso_user, virtuoso_password, "SPARQL Endpoint")
    endpoint.setReturnFormat(format_dict.get(format, "json"))

    endpoint.setQuery(query)
    return endpoint.queryAndConvert()


def guess_triple_type(value: str | int | float, g: Graph) -> URIRef | Literal | BNode:
    try:
        if type(value) == int:
            return Literal(value, datatype=XSD.integer)

        if type(value) == float:
            return Literal(value, datatype=XSD.float)

        if re_match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value) is not None:
            return Literal(value, datatype=XSD.dateTime)

        if re_match(r"\d{4}-\d{2}-\d{2}", value) is not None:
            return Literal(value, datatype=XSD.date)

        # uri/curie/bnode
        return get_uri_from_str(value, g)

    except Exception:
        # default is Literal
        return Literal(value)


def get_uri_from_str(value: str, g: Graph) -> URIRef | BNode:
    if value.startswith("_:"):
        _, nodeId = value.split(":")
        return BNode(nodeId) if len(nodeId) > 0 else BNode()
    if value.startswith("http"):
        return URIRef(value)
    return g.namespace_manager.expand_curie(value)
