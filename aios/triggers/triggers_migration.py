import asyncio
import logging
import re
from contextlib import suppress
from typing import Any

import yaml

from aios.bootstrap.startup_step import StartupStep
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.config_repo.current_author import CurrentAuthor
from aios.config_repo.git_document_store import GitDocumentStore
from aios.storage.collection import Collection
from aios.storage.document_store import DocumentStore
from aios.web.aios_yaml_file import AiosYamlFile

log = logging.getLogger(__name__)

AGENT_BEFORE = "agents/scheduler.md"
AGENT_NOW = "agents/triggers.md"


class TriggersMigration(StartupStep):
    """Until 2026-11-23 triggers were schedules. Moves what still has the old name,
    and does nothing once it is moved:

    - `schedules/` to `triggers/` and the fixed agent `scheduler` to `triggers`, in
      one commit on the checked-out branch (another branch moves once it is checked
      out and ai-os starts);
    - when each one last fired, in the data dir;
    - `scheduler:` and `collection_access.schedules` in aios.yaml (read under the
      new names already, so this only tidies the file).
    """

    def __init__(
        self,
        store: GitDocumentStore,
        state: DocumentStore,
        collections: list[Collection[Any]],
        config: AiosYamlFile,
    ) -> None:
        self._store = store
        self._state = state
        self._collections = collections
        self._config = config

    async def run(self) -> None:
        await self._move_state()  # first: moving the files reloads them with it
        if await asyncio.to_thread(self._store.repo.exists):
            await self._move_files()
        await self._rename_in_aios_yaml()

    async def _move_files(self) -> None:
        async with self._store.lock:
            paths = await asyncio.to_thread(self._move)
            if not paths:
                return
            head = await asyncio.to_thread(
                self._store.repo.commit, paths, "Schedules are triggers now", CurrentAuthor.get()
            )
        if head is not None:
            self._store.last_head = head
            await self._store.committed()
        for collection in self._collections:
            await collection.load()
        log.info("moved %d files from schedules to triggers", len(paths) // 2)

    def _move(self) -> list[str]:
        root = self._store.repo.root
        paths: list[str] = []
        before, now = root / "schedules", root / "triggers"
        if before.is_dir():
            now.mkdir(exist_ok=True)
            for file in sorted(before.glob("*.yaml")):
                if not (now / file.name).exists():
                    file.rename(now / file.name)
                    paths += [f"schedules/{file.name}", f"triggers/{file.name}"]
            with suppress(OSError):
                before.rmdir()  # only once nothing is left in it
        if (root / AGENT_BEFORE).exists() and not (root / AGENT_NOW).exists():
            (root / AGENT_BEFORE).rename(root / AGENT_NOW)
            paths += [AGENT_BEFORE, AGENT_NOW]
        return paths

    async def _move_state(self) -> None:
        for document in await self._state.list("schedules-state"):
            await self._state.put("triggers-state", document["id"], document)
            await self._state.delete("schedules-state", document["id"])

    async def _rename_in_aios_yaml(self) -> None:
        text = self._config.read()
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            return  # ai-os would not have started; nothing to do here
        if not isinstance(data, dict):
            return
        changed = text
        if "scheduler" in data and "triggers" not in data:
            changed = re.sub(r"^scheduler:", "triggers:", changed, count=1, flags=re.MULTILINE)
        access = data.get("collection_access")
        if isinstance(access, dict) and "schedules" in access and "triggers" not in access:
            renamed = {("triggers" if k == "schedules" else k): v for k, v in access.items()}
            editor = ConfigYamlEditor()
            changed = editor.replace_section(changed, "collection_access", None)
            changed = editor.replace_section(changed, "collection_access", renamed)
        if changed != text:
            await self._config.write(changed, "aios.yaml: schedules are triggers now")
            log.info("aios.yaml: scheduler is triggers now")
