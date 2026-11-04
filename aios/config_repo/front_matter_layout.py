from pathlib import Path
from typing import Any

import yaml

from aios.config_repo.file_layout import FileLayout


class FrontMatterLayout(FileLayout):
    """Markdown with YAML front matter: the settings on top, one text field (a
    prompt, a skill's instructions) as the body, so it diffs and edits as text.

    `pattern` places the file, `{id}` standing for the document id, e.g.
    `agents/{id}.md` or `skills/{id}/SKILL.md`. With `name_in_head`, the id is also
    written as `name:`, which is what Claude Code expects of a SKILL.md.
    """

    def __init__(self, pattern: str, body_field: str, name_in_head: bool = False) -> None:
        self._pattern = pattern
        self._body = body_field
        self._name_in_head = name_in_head

    def path(self, doc_id: str) -> str:
        return self._pattern.format(id=doc_id)

    def ids(self, root: Path) -> list[str]:
        before, _, after = self._pattern.partition("{id}")
        return sorted(
            str(p.relative_to(root))[len(before) : -len(after) or None]
            for p in root.glob(self._pattern.replace("{id}", "*"))
            if p.is_file()
        )

    def render(self, doc: dict[str, Any]) -> str:
        head = {k: v for k, v in doc.items() if k not in ("id", self._body)}
        if self._name_in_head:
            head = {"name": doc["id"], **head}
        text = yaml.safe_dump(head, allow_unicode=True, sort_keys=False, width=1000)
        body = str(doc.get(self._body) or "").rstrip("\n") + "\n"
        return f"---\n{text}---\n\n{body}"

    def parse(self, text: str, doc_id: str) -> dict[str, Any]:
        head: dict[str, Any] = {}
        body = text
        if text.startswith("---\n"):
            raw, _, body = text[4:].partition("\n---\n")
            head = yaml.safe_load(raw) or {}
        head.pop("name", None)
        return {**head, "id": doc_id, self._body: body.strip("\n") + "\n"}
