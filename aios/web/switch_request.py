from pydantic import BaseModel


class SwitchRequest(BaseModel):
    branch: str
