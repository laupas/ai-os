import inspect
import re
from typing import Any

from aiohttp import web
from pydantic import BaseModel

BODY = re.compile(r"RequestBody\.parse\(\s*request\s*,\s*(\w+)")
PERMISSION = re.compile(r"Permission\.([A-Z_]+)")
PARAMETER = re.compile(r"\{(\w+)(?::[^}]*)?\}")
WORD = re.compile(r"(?<!^)(?=[A-Z])")
SKIPPED = {"HEAD", "OPTIONS", "*"}

INTRO = """The JSON API of the ai-os web console: everything the console itself does.

**Signing in.** A request counts as whoever the console's login says it is: the
session cookie of the console's own login, or the token of the login proxy in front
of it. From this page, *Try it out* uses this browser's sign-in.

**Changes** (anything but GET) need the header `X-Aios: 1`, which this page adds.

**Permissions.** Every `/api` route needs the `chat` permission; those marked
*administer* need that one too. `/hooks/` routes take a `Authorization: Bearer`
token of their own instead of a sign-in."""


class OpenApiBuilder:
    """Describes the routes an application serves as OpenAPI 3.1, read from the
    application itself, so it never falls behind: each route's group is its
    `WebRoutes` class, its text the handler's docstring, its body the model the
    handler reads with `RequestBody.parse`, its permission the one it checks."""

    def build(self, app: web.Application, version: str) -> dict[str, Any]:
        paths: dict[str, dict[str, Any]] = {}
        schemas: dict[str, Any] = {}
        tags: dict[str, str] = {}
        for route in app.router.routes():
            resource = route.resource
            if (
                route.method in SKIPPED
                or resource is None
                or isinstance(resource, web.StaticResource)
            ):
                continue
            path = PARAMETER.sub(r"{\1}", resource.canonical)
            if not path.startswith(("/api/", "/hooks/")):
                continue
            handler = route.handler
            owner = getattr(handler, "__self__", None)
            tag = self._tag(type(owner).__name__) if owner is not None else "Other"
            if owner is not None and tag not in tags:
                tags[tag] = inspect.cleandoc(type(owner).__doc__ or "")
            paths.setdefault(path, {})[route.method.lower()] = self._operation(
                path, handler, tag, schemas
            )
        return {
            "openapi": "3.1.0",
            "info": {"title": "ai-os", "version": version, "description": INTRO},
            "tags": [{"name": name, "description": text} for name, text in sorted(tags.items())],
            "paths": dict(sorted(paths.items())),
            "components": {
                "schemas": dict(sorted(schemas.items())),
                "securitySchemes": {
                    "hookToken": {"type": "http", "scheme": "bearer"},
                },
            },
        }

    def _operation(
        self, path: str, handler: Any, tag: str, schemas: dict[str, Any]
    ) -> dict[str, Any]:
        source = self._source(handler)
        name = getattr(handler, "__name__", "handler")
        doc = inspect.cleandoc(handler.__doc__ or "") if handler.__doc__ else ""
        operation: dict[str, Any] = {
            "tags": [tag],
            "summary": doc.split("\n", 1)[0]
            if doc
            else name.strip("_").replace("_", " ").capitalize(),
            "operationId": f"{tag.replace(' ', '')}.{name.strip('_')}.{path}",
            "responses": {"200": {"description": "OK"}},
        }
        notes = [doc] if doc else []
        permission = PERMISSION.search(source)
        if path.startswith("/hooks/"):
            operation["security"] = [{"hookToken": []}]
        elif permission and permission.group(1) != "CHAT":
            notes.append(f"Needs the *{permission.group(1).lower()}* permission.")
        if notes:
            operation["description"] = "\n\n".join(notes)
        parameters = [
            {"name": p, "in": "path", "required": True, "schema": {"type": "string"}}
            for p in PARAMETER.findall(path)
        ]
        if parameters:
            operation["parameters"] = parameters
        model = self._body_model(handler, source)
        if model is not None:
            schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
            schemas.update(schema.pop("$defs", {}))
            schemas[model.__name__] = schema
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
                    }
                },
            }
        return operation

    @staticmethod
    def _source(handler: Any) -> str:
        try:
            return inspect.getsource(inspect.unwrap(handler))
        except (OSError, TypeError):
            return ""

    @staticmethod
    def _body_model(handler: Any, source: str) -> type[BaseModel] | None:
        found = BODY.search(source)
        if found is None:
            return None
        model = getattr(inspect.unwrap(handler), "__globals__", {}).get(found.group(1))
        return model if isinstance(model, type) and issubclass(model, BaseModel) else None

    @staticmethod
    def _tag(class_name: str) -> str:
        words = WORD.sub(" ", class_name.removesuffix("Routes")).split()
        return " ".join([words[0], *(w.lower() for w in words[1:])]) if words else class_name
