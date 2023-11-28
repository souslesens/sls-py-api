from pathlib import Path
from typing import Annotated
from tempfile import gettempdir

from fastapi import Depends, File, Form, Header, HTTPException
from ulid import ULID


from sls_api.app import App

app = App()


async def verify_token(x_token: Annotated[str, Header()]):
    user = app.get_user_from_token(x_token)
    if not user:
        raise HTTPException(status_code=400, detail="X-Token header invalid")
    return user


@app.get("/")
def read_root(user: Annotated[dict, Depends(verify_token)]):
    return {}


@app.get("/api/v1/rdf/graph")
def get_rdf_graph(
    user: Annotated[dict, Depends(verify_token)],
    source: Annotated[str, Form()],
    format: Annotated[str, Form()],
):
    user = app.add_sources_for_user(user)
    if not user.can_read(source):
        raise HTTPException(status_code=401, detail=f"Not authorized to read {source}")


@app.delete("/api/v1/rdf/graph")
def delete_rdf_graph(
    source: Annotated[str, Form()],
    user: Annotated[dict, Depends(verify_token)],
):
    user = app.add_sources_for_user(user)
    if not user.can_readwrite(source):
        raise HTTPException(
            status_code=401, detail=f"Not authorized to delete {source}"
        )

    app.delete_graph_from_endpoint(source)
    return {"message": f"{source} deleted"}


@app.post("/api/v1/rdf/graph")
def post_rdf_graph(
    last: Annotated[bool, Form()],
    clean: Annotated[bool, Form()],
    data: Annotated[bytes, File()],
    source: Annotated[str, Form()],
    user: Annotated[dict, Depends(verify_token)],
    identifier: Annotated[str, Form()] = None,
):
    user = app.add_sources_for_user(user)
    if not user.can_readwrite(source):
        raise HTTPException(status_code=401, detail=f"Not authorized to write {source}")

    if not identifier:
        identifier = ULID()

    tmpdir = Path(gettempdir())
    tmpfile = tmpdir.joinpath(identifier)

    if clean:
        tmpfile.unlink()
        return {"identifier": identifier}

    with tmpfile.open("a") as fp:
        fp.write(data.decode())

    # last chunk, load data into triplestore
    if last:
        app.upload_rdf_graph_to_endpoint(tmpfile, source, remove_graph=True)

    # remove tmpfile
    tmpfile.unlink()

    return {"identifier": identifier}
