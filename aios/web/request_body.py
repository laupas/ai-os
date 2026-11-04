from aiohttp import web
from pydantic import BaseModel, ValidationError


class RequestBody:
    """Reads a JSON request body into a model, answering 400 when it does not fit."""

    @staticmethod
    async def parse[M: BaseModel](request: web.Request, model: type[M]) -> M:
        try:
            return model.model_validate(await request.json())
        except (ValueError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
