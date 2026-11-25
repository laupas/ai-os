import io
import re
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:")


class ConfigYamlEditor:
    """Writes a key into aios.yaml's text without losing anything else in it:
        comments, key order, quoting. For the console's reference of the keys there
        are, which inserts one with its default for the administrator to change, and for
    the console's simple settings, which set one."""

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.indent(mapping=2, sequence=4, offset=2)
        self._yaml.width = 4096
        self._yaml.preserve_quotes = True

    def insert(self, text: str, path: list[str], value: Any) -> str:
        """`text` with `path` set to `value`, the sections on the way created, and
        nothing else touched; unchanged when `path` is set already."""
        return self._write(text, path, value, replace=False)

    def set(self, text: str, path: list[str], value: Any) -> str:
        """Like `insert`, but a value already at `path` is replaced."""
        return self._write(text, path, value, replace=True)

    def replace_section(self, text: str, key: str, value: Any) -> str:
        """`text` with the top-level `key` made `value`, or removed (with the
        comment above it) when `value` is None.

        Only that section's lines are rewritten. The comment lines above a
        top-level key belong to that key, which ruamel does not know: it hangs them
        on the last item of the section before, and would lose them with it.
        Within the section, mappings are merged key by key and a list that only
        grew keeps its items, so the comments on what stays, stay.
        """
        text = self._as_block(text)
        lines = text.splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        starts = self._section_starts(lines)
        if key not in starts:
            if value is None:
                return text
            block = self._dump({key: value})
            gap = "\n" if lines and lines[-1].strip() else ""
            return "".join(lines) + gap + block
        own = starts[key]
        after = sorted(s for s in starts.values() if s[0] > own[0])
        end = after[0][0] if after else len(lines)
        if value is None:
            kept = "".join(lines[: own[0]] + lines[end:])
            # Removing the last section leaves the blank line that set it apart.
            return kept.rstrip("\n") + "\n" if kept.strip() else ""
        body_end = end
        while body_end > own[1] + 1 and not lines[body_end - 1].strip():
            body_end -= 1  # the blank lines before the next section stay as they are
        section = self._yaml.load("".join(lines[own[1] : body_end]))
        self._merge(section, key, value)
        return "".join(lines[: own[1]]) + self._dump(section) + "".join(lines[body_end:])

    def _as_block(self, text: str) -> str:
        """`text` in block style when it is a mapping written in flow style (the
        JSON a deployment template writes): its keys are not at the start of a
        line, so a section added below it would make a second document. Such a
        file has no comments to lose."""
        if not text.strip() or self._section_starts(text.splitlines()):
            return text
        document = YAML(typ="safe").load(text)
        return self._dump(document) if isinstance(document, dict) else text

    @staticmethod
    def _section_starts(lines: list[str]) -> dict[str, tuple[int, int]]:
        """Each top-level key: where its comment above starts, and its own line."""
        starts: dict[str, tuple[int, int]] = {}
        for index, line in enumerate(lines):
            match = TOP_LEVEL_KEY.match(line)
            if not match:
                continue
            first = index
            while first > 0 and (not lines[first - 1].strip() or lines[first - 1].startswith("#")):
                first -= 1
            while first < index and not lines[first].strip():  # blank lines stay before
                first += 1
            starts[match.group(1)] = (first, index)
        return starts

    def _dump(self, document: Any) -> str:
        out = io.StringIO()
        self._yaml.dump(document, out)
        return out.getvalue()

    def _merge(self, node: CommentedMap, key: str, value: Any) -> None:
        current = node.get(key)
        if isinstance(value, dict) and isinstance(current, CommentedMap):
            for name in [k for k in current if k not in value]:
                del current[name]
            for name, inner in value.items():
                self._merge(current, name, inner)
        elif (
            isinstance(value, list)
            and isinstance(current, CommentedSeq)
            and list(current) == value[: len(current)]
        ):
            current.extend(value[len(current) :])
        elif key not in node or current != value:
            node[key] = value

    def _write(self, text: str, path: list[str], value: Any, replace: bool) -> str:
        document = self._yaml.load(text) if text.strip() else None
        if not isinstance(document, CommentedMap):
            document = CommentedMap()
        node = document
        for key in path[:-1]:
            if not isinstance(node.get(key), CommentedMap):
                node[key] = CommentedMap()
            node = node[key]
        if path[-1] in node and (not replace or node[path[-1]] == value):
            return text
        node[path[-1]] = value
        out = io.StringIO()
        self._yaml.dump(document, out)
        return out.getvalue()
