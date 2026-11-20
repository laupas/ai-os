from pydantic import BaseModel


class FilesRequest(BaseModel):
    """`files` in aios.yaml as the console sends it, or just folders to look at."""

    read_roots: list[str] = []
    write_roots: list[str] = []
