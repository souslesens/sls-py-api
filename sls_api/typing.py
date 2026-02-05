from typing import Literal
from typing_extensions import TypedDict

from rdflib import URIRef, Literal as RdfLiteral


## API responses
class ResponseConvert(TypedDict):
    data: str


Triple = tuple[URIRef, URIRef, URIRef | RdfLiteral]

RdfFormat = Literal[
    "xml",
    "n3",
    "turtle",
    "nt",
    "pretty-xml",
    "trig",
    "json-ld",
    "hext",
]
SlsRdfFormat = Literal["sls"]
