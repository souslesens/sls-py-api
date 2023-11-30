from itertools import islice
from typing import Iterator


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
