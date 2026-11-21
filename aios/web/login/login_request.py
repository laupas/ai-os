from pydantic import BaseModel


class LoginRequest(BaseModel):
    """What the login page sends: the fields of whichever way is in use."""

    user_id: str | None = None
    username: str | None = None
    password: str | None = None
    code: str | None = None
