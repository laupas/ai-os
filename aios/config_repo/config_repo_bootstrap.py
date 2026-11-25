import logging
import shutil

import yaml

from aios.config.settings import CONFIG_FILE_NAME, Settings
from aios.config_repo.current_author import AIOS
from aios.config_repo.git_credentials import GitCredentials
from aios.config_repo.git_repository import GitRepository

log = logging.getLogger(__name__)


class ConfigRepoBootstrap:
    """Runs before anything reads the configuration, since `aios.yaml` is itself in
    the repository.

    A data dir without a repository clones it from `AIOS_CONFIG_REMOTE` when that is
    set: that is the whole of moving ai-os to a new machine. An existing repository
    without `aios.yaml` gets the data dir's `config.yaml` moved into it, in a commit.
    A data dir with neither gets `config.yaml` from `AIOS_INITIAL_CONFIG`, which the
    new repository then takes in. A deployment template sends it as JSON; it is
    written as block YAML, the form the console edits a section of.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = GitRepository(settings.config_dir())

    def run(self) -> None:
        if not self._repo.exists() and self._settings.config_remote:
            self._clone()
        if not self._repo.exists() and self._settings.initial_config:
            self._write_initial_config()
        if self._repo.exists() and self._repo.head():
            self._move_config_file()

    def _write_initial_config(self) -> None:
        target = self._settings.legacy_config_file()
        if target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        text = (self._settings.initial_config or "").strip()
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError:
            loaded = None  # left as it is, for the configuration check to report
        if isinstance(loaded, dict):
            text = yaml.safe_dump(loaded, sort_keys=False, allow_unicode=True).strip()
        target.write_text(text + "\n")
        log.info("wrote %s from AIOS_INITIAL_CONFIG", target)

    def _clone(self) -> None:
        url = self._settings.config_remote or ""
        with GitCredentials.env(
            self._settings.config_ssh_key,
            self._settings.config_token,
            self._settings.known_hosts_file(),
        ) as env:
            self._repo.clone(url, env)
        log.info("cloned the configuration repository from %s", url)

    def _move_config_file(self) -> None:
        target = self._repo.root / CONFIG_FILE_NAME
        legacy = self._settings.legacy_config_file()
        if target.exists() or not legacy.exists() or self._settings.config_file:
            return
        shutil.copyfile(legacy, target)
        self._repo.commit(
            [CONFIG_FILE_NAME], f"{CONFIG_FILE_NAME}: moved in from the data dir", AIOS
        )
        legacy.rename(legacy.with_name("config.yaml.moved-to-repository"))
        log.info("moved %s into the configuration repository as %s", legacy, CONFIG_FILE_NAME)
