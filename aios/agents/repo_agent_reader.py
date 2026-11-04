import logging
from pathlib import Path
from typing import Any

import yaml

from aios.entities.agents.agent import Agent

log = logging.getLogger(__name__)

MCP_PREFIX = "mcp__"


class RepoAgentReader:
    """Reads the agents that ship with ai-os from `agents/*.md`, to seed the store.

    Each file is YAML front matter (name, description, tools, skills, model) and the
    prompt. `tools` names built-in tools and connector tools alike; a connector tool
    (`mcp__<connector>__<tool>`) becomes a grant on that connector.
    """

    def __init__(self, agents_dir: Path) -> None:
        self._dir = Path(agents_dir)

    def read(self) -> list[Agent]:
        agents = []
        for path in sorted(self._dir.glob("*.md")):
            try:
                agents.append(self._parse(path))
            except (ValueError, yaml.YAMLError) as exc:
                log.error("skipping agent file %s: %s", path.name, exc)
        return agents

    def _parse(self, path: Path) -> Agent:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise ValueError("no front matter")
        head, _, body = text[4:].partition("\n---\n")
        meta: dict[str, Any] = yaml.safe_load(head) or {}
        builtin: list[str] = []
        connectors: dict[str, list[str] | None] = {}
        for tool in self._names(meta.get("tools")):
            if tool.startswith(MCP_PREFIX):
                server, _, name = tool[len(MCP_PREFIX) :].partition("__")
                granted = connectors.setdefault(server, [])
                if granted is not None:
                    granted.append(name)
            elif tool != "Skill":  # a skill is granted by name, under `skills`
                builtin.append(tool)
        return Agent(
            id=str(meta.get("name") or path.stem),
            description=str(meta.get("description") or ""),
            prompt=body.strip() + "\n",
            model=meta.get("model"),
            builtin_tools=builtin,
            skills=self._names(meta.get("skills")),
            connectors=connectors,
        )

    @staticmethod
    def _names(value: Any) -> list[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else str(value).split(",")
        return [str(i).strip() for i in items if str(i).strip()]
