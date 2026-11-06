import io
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


class ConfigYamlEditor:
    """Writes values edited in the console's form back into aios.yaml without
    losing what the form does not know about: comments, key order, quoting.

    Only what changed is touched. A key the form left out is removed, so its
    default applies again; a list is replaced whole when it changed and kept, with
    its comments, when it did not.
    """

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.indent(mapping=2, sequence=4, offset=2)
        self._yaml.width = 4096
        self._yaml.preserve_quotes = True

    def values(self, text: str) -> dict[str, Any]:
        """What the file sets, as plain data; defaults are not filled in."""
        data = YAML(typ="safe").load(text) if text.strip() else None
        return data if isinstance(data, dict) else {}

    def apply(self, text: str, values: dict[str, Any]) -> str:
        document = self._yaml.load(text) if text.strip() else None
        if not isinstance(document, CommentedMap):
            document = CommentedMap()
        self._merge(document, values)
        out = io.StringIO()
        self._yaml.dump(document, out)
        return out.getvalue()

    def _merge(self, target: CommentedMap, values: dict[str, Any]) -> None:
        for key in [k for k in target if k not in values]:
            del target[key]
        for key, value in values.items():
            current = target.get(key)
            if isinstance(value, dict) and isinstance(current, CommentedMap):
                self._merge(current, value)
            elif key not in target or self._plain(current) != value:
                target[key] = value

    @classmethod
    def _plain(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: cls._plain(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._plain(v) for v in value]
        return value
