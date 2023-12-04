from itertools import islice
from typing import Iterator

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
