from pathlib import Path
from typing import Annotated
from tempfile import gettempdir

from fastapi import Depends, Form, Header, HTTPException, UploadFile
from ulid import ULID


from sls_api.app import App

app = App()


async def verify_token(authorization: Annotated[str, Header()]):
    output = app.authorization_pattern.match(authorization)
    if output is None:
        raise HTTPException(
            status_code=400, detail="The specified Authorization is not valid"
        )

    if not output.group("scheme") == "Bearer":
        raise HTTPException(
            status_code=405, detail="The only authorized auth scheme is Bearer"
        )

    user = app.get_user_from_token(output.group("token"))
    if not user:
        raise HTTPException(status_code=401, detail="You are not authorized")
    return user


@app.get("/")
def read_root(user: Annotated[dict, Depends(verify_token)]):
    return {}


@app.get("/api/v1/rdf/graph")
def get_rdf_graph(
    user: Annotated[dict, Depends(verify_token)],
    source: str,
    identifier: str = "",
    offset: int = 0,
    format: str = "nt",
):
    limit = 1_000_000  # 1MB
    user = app.add_sources_for_user(user)
    if not user.can_read(source):
        raise HTTPException(status_code=401, detail=f"Not authorized to read {source}")

    tmpdir = Path(gettempdir())

    # first call, write graph to file
    if not identifier:
        identifier = str(ULID())
        tmpfile = tmpdir.joinpath(f"{identifier}.{format}")
        app.get_rdf_graph_from_endpoint(tmpfile, source, format=format)
    else:
        tmpfile = tmpdir.joinpath(f"{identifier}.{format}")

    # Get a slice of the file
    data = tmpfile.read_text()
    chunk = data[offset : offset + limit]

    filesize = tmpfile.stat().st_size
    if offset + limit >= filesize:
        next_offset = None
    else:
        next_offset = offset + limit

    return {
        "identifier": identifier,
        "filesize": filesize,
        "next_offset": next_offset,
        "data": chunk,
    }


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
    data: UploadFile,
    source: Annotated[str, Form()],
    replace: Annotated[bool, Form()],
    user: Annotated[dict, Depends(verify_token)],
    identifier: Annotated[str, Form()] = "",
):
    user = app.add_sources_for_user(user)
    if not user.can_readwrite(source):
        raise HTTPException(status_code=401, detail=f"Not authorized to write {source}")

    if not identifier:
        identifier = str(ULID())
    tmpdir = Path(gettempdir())
    ext = Path(data.filename).suffix
    tmpfile = tmpdir.joinpath(f"{identifier}{ext}")

    if clean:
        tmpfile.unlink()
        return {"identifier": identifier}

    with tmpfile.open("ab") as fp:
        fp.write(data.file.read())

    # last chunk, load data into triplestore
    if last:
        app.upload_rdf_graph_to_endpoint(tmpfile, source, remove_graph=replace)

        # remove tmpfile
        tmpfile.unlink()

    return {"identifier": identifier}
