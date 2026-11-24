from pydantic import BaseModel, ConfigDict


class ApiDocsConfig(BaseModel):
    """The console's API described as OpenAPI, at `/api/openapi.json`, with a
    Swagger page at `/api/docs`. For administrators, and only while switched on."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    enabled: bool = False
    """Serve `/api/docs` and `/api/openapi.json` to administrators."""
