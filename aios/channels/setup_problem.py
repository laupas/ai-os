from pydantic import BaseModel


class SetupProblem(BaseModel):
    """Something that commonly goes wrong while setting a channel up, as the
    console shows it: what one sees, and what to do about it."""

    symptom: str
    fix: str
