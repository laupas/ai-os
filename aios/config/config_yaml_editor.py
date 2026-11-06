import io
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


class ConfigYamlEditor:
    """Writes a key into aios.yaml's text without losing anything else in it:
    comments, key order, quoting. For the console's reference of the keys there
    are, which inserts one with its default for the administrator to change."""

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.indent(mapping=2, sequence=4, offset=2)
        self._yaml.width = 4096
        self._yaml.preserve_quotes = True

    def insert(self, text: str, path: list[str], value: Any) -> str:
        """`text` with `path` set to `value`, the sections on the way created, and
        nothing else touched; unchanged when `path` is set already."""
        document = self._yaml.load(text) if text.strip() else None
        if not isinstance(document, CommentedMap):
            document = CommentedMap()
        node = document
        for key in path[:-1]:
            if not isinstance(node.get(key), CommentedMap):
                node[key] = CommentedMap()
            node = node[key]
        if path[-1] in node:
            return text
        node[path[-1]] = value
        out = io.StringIO()
        self._yaml.dump(document, out)
        return out.getvalue()
