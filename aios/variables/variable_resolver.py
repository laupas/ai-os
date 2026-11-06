import hashlib
import os
import re
from pathlib import Path
from typing import Any

from aios.entities.variables.variable import Variable
from aios.storage.collection import Collection
from aios.variables.secret_box import SecretBox

REFERENCE = re.compile(r"\$\{(file:)?([A-Za-z_][A-Za-z0-9_]*)\}")


class VariableResolver:
    """Fills `${NAME}` and `${file:NAME}` into connector configs, from the
    variables set in the console, else from the process environment.

    `${file:NAME}` becomes the path of a file holding the value, written (mode
    0600) only when the value changed since it was last written: an MCP server that
    keeps its refreshed credentials in that file keeps them across turns. The file
    is a decrypted copy: keep the directory on a tmpfs (`AIOS_VARIABLE_FILES_DIR`),
    and it is removed with its variable.
    """

    def __init__(self, variables: Collection[Variable], box: SecretBox, files_dir: Path) -> None:
        self._variables = variables
        self._box = box
        self._files = Path(files_dir)

    def expand(self, value: Any) -> Any:
        if isinstance(value, str):
            return REFERENCE.sub(self._replace, value)
        if isinstance(value, list):
            return [self.expand(v) for v in value]
        if isinstance(value, dict):
            return {k: self.expand(v) for k, v in value.items()}
        return value

    def value_of(self, name: str) -> str | None:
        variable = self._variables.get(name)
        if variable is None:
            return os.environ.get(name)
        return self._box.decrypt(variable.value) if variable.secret else variable.value

    def references(self, value: Any) -> set[str]:
        """Every name `value` refers to."""
        if isinstance(value, str):
            return {m.group(2) for m in REFERENCE.finditer(value)}
        if isinstance(value, list):
            return set().union(*(self.references(v) for v in value)) if value else set()
        if isinstance(value, dict):
            return self.references(list(value.values()))
        return set()

    def missing(self, value: Any) -> list[str]:
        return sorted(n for n in self.references(value) if self.value_of(n) is None)

    def forget(self, name: str) -> None:
        """Removes the file written for `name`, if any."""
        for path in (self._files / name, self._files / f".{name}.sha256"):
            path.unlink(missing_ok=True)

    def _replace(self, match: re.Match[str]) -> str:
        as_file, name = match.group(1), match.group(2)
        value = self.value_of(name)
        if value is None:
            return match.group(0)  # left visible, so the failure names what is missing
        return str(self._file_for(name, value)) if as_file else value

    def _file_for(self, name: str, value: str) -> Path:
        self._files.mkdir(parents=True, exist_ok=True)
        path = self._files / name
        stamp = self._files / f".{name}.sha256"
        digest = hashlib.sha256(value.encode()).hexdigest()
        if not path.exists() or not stamp.exists() or stamp.read_text() != digest:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(value)
            stamp.write_text(digest)
        return path
