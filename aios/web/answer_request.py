from pydantic import BaseModel


class AnswerRequest(BaseModel):
    answer: str
