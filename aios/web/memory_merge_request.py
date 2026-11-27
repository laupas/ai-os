from pydantic import Field

from aios.web.memory_request import MemoryRequest


class MemoryMergeRequest(MemoryRequest):
    """Several memories made into one: the first keeps its id and takes the body, the
    others are deleted."""

    ids: list[str] = Field(min_length=2)
