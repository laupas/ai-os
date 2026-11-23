import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from aios.config_repo.file_layout import FileLayout
from aios.config_repo.front_matter_layout import FrontMatterLayout
from aios.config_repo.yaml_layout import YamlLayout
from aios.connectors.code_connector_library import MANIFEST
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.skills.skill import Skill
from aios.entities.triggers.trigger import Trigger
from aios.store.store_item import StoreItem
from aios.store.store_kind import StoreKind
from aios.store.store_listing import StoreListing
from aios.store.store_meta import StoreMeta

log = logging.getLogger(__name__)

STORE_FILE = "store.yaml"
META_KEY = "store"
TEMPLATE_USER = "store-template"
"""Stands in for `user_id` while a trigger template is checked: whoever installs it
is the user."""


class StoreSourceReader:
    """Reads a checked-out source: `store.yaml`, and each item in the same files as
    the configuration repository holds them, each checked against its model. An
    item that does not read is left out and named in `problems`."""

    LAYOUTS: dict[StoreKind, FileLayout] = {
        StoreKind.AGENT: FrontMatterLayout("agents/{id}.md", "prompt"),
        StoreKind.SKILL: FrontMatterLayout("skills/{id}/SKILL.md", "content", name_in_head=True),
        StoreKind.CONNECTOR: YamlLayout("connectors"),
        StoreKind.TRIGGER: YamlLayout("triggers"),
    }
    MODELS = {
        StoreKind.AGENT: Agent,
        StoreKind.SKILL: Skill,
        StoreKind.CONNECTOR: Connector,
        StoreKind.TRIGGER: Trigger,
    }

    def read(self, root: Path, listing: StoreListing) -> StoreListing:
        head = self._yaml(root / STORE_FILE)
        items: list[StoreItem] = []
        problems: list[str] = []
        for kind, layout in self.LAYOUTS.items():
            for item_id in layout.ids(root):
                path = layout.path(item_id)
                try:
                    items.append(self._item(root, kind, item_id, listing.url))
                except (OSError, ValueError, yaml.YAMLError) as exc:
                    message = self._message(exc)
                    log.warning("store %s: skipping %s: %s", listing.url, path, message)
                    problems.append(f"{path}: {message}")
        return listing.model_copy(
            update={
                "name": str(head.get("name") or listing.url.rstrip("/").rsplit("/", 1)[-1]),
                "description": str(head.get("description") or ""),
                "items": items,
                "problems": problems,
            }
        )

    def _item(self, root: Path, kind: StoreKind, item_id: str, url: str) -> StoreItem:
        layout = self.LAYOUTS[kind]
        document = layout.parse((root / layout.path(item_id)).read_text("utf-8"), item_id)
        meta = StoreMeta.model_validate(document.pop(META_KEY, None) or {})
        check = {**document, "user_id": TEMPLATE_USER} if kind is StoreKind.TRIGGER else document
        self.MODELS[kind].model_validate(check)
        item = StoreItem(source=url, kind=kind, id=item_id, document=document, meta=meta)
        if item.code_name is not None:
            folder = root / "code" / item.code_name
            if not (folder / MANIFEST).is_file():
                raise ValueError(f"its code is not in code/{item.code_name}/")
            item.code_folder = folder
        return item

    @staticmethod
    def _yaml(file: Path) -> dict[str, Any]:
        try:
            data = yaml.safe_load(file.read_text("utf-8")) if file.is_file() else None
        except (OSError, yaml.YAMLError) as exc:
            log.warning("unreadable %s: %s", file, exc)
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _message(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'item'}: {e['msg']}" for e in exc.errors()
            )
        return str(exc)
