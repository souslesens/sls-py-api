from typing import Literal
from typing_extensions import TypedDict


## API responses
class ResponseConvert(TypedDict):
    data: str


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
