from pydantic import BaseModel


class FilesConfig(BaseModel):
    """Where the built-in file tools (Read, Grep, Glob, Edit, Write) may go.

    Anything outside these folders is refused, which also keeps agents away from
    the process environment and the data dir.
    """

    read_roots: list[str] = []
    write_roots: list[str] = []
