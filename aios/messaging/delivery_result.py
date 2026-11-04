from pydantic import BaseModel


class DeliveryResult(BaseModel):
    ok: bool
    detail: str = ""
    """Provider message id on success, the error on failure."""
