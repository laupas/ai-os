import re
from typing import Any

from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver

SECRET_WORDS = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|CREDENTIAL|AUTH|COOKIE")


class SecretExtractor:
    """Keeps secrets out of connector configs, which are a git repository: a literal
    value where a secret goes is moved into an encrypted secret variable and replaced
    by its `${NAME}`.

    A secret goes in `oauth.client_secret`, and in a header or environment variable
    whose name says so (key, token, secret, password, credential, auth, cookie). A
    value that already refers to a variable, or is a path, is left alone, and so is
    every other field: a server's address or `NODE_OPTIONS` is not a secret, and
    moving it would only make the config unreadable.
    """

    def __init__(self, variables: VariableCatalog, resolver: VariableResolver) -> None:
        self._variables = variables
        self._resolver = resolver

    async def extract(
        self, owner: str, config: dict[str, Any], author: str
    ) -> tuple[dict[str, Any], list[str]]:
        """The config with every literal secret replaced, and the variables made."""
        config = dict(config)
        moved: list[str] = []
        for section in ("headers", "env"):
            values = config.get(section)
            if not isinstance(values, dict):
                continue
            values = dict(values)
            for key, value in values.items():
                if self._is_literal(value) and SECRET_WORDS.search(key.upper()):
                    values[key] = await self._move(owner, key, value, author, moved)
            config[section] = values
        oauth = config.get("oauth")
        if isinstance(oauth, dict) and self._is_literal(oauth.get("client_secret")):
            oauth = {**oauth}
            oauth["client_secret"] = await self._move(
                owner, "client_secret", oauth["client_secret"], author, moved
            )
            config["oauth"] = oauth
        return config, moved

    @staticmethod
    def _is_literal(value: Any) -> bool:
        return (
            isinstance(value, str)
            and bool(value.strip())
            and "${" not in value
            and not value.startswith(("/", "~"))
        )

    async def _move(self, owner: str, key: str, value: str, author: str, moved: list[str]) -> str:
        base = re.sub(r"[^A-Z0-9]+", "_", f"{owner}_{key}".upper()).strip("_")[:60]
        name, n = base, 1
        while (current := self._variables.get(name)) is not None:
            if current.secret and not current.file and self._resolver.value_of(name) == value:
                break  # the same value, saved again
            n += 1
            name = f"{base}_{n}"
        await self._variables.save(
            name,
            value,
            secret=True,
            file=False,
            description=f"Moved out of connector {owner} ({key}) when it was saved.",
            author=author,
        )
        moved.append(name)
        return "${" + name + "}"
