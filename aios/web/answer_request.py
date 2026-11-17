from pydantic import BaseModel


class AnswerRequest(BaseModel):
    answer: str
    voice: bool = False
    """The answer was spoken, and only some questions may be answered that way."""
