import tempfile
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE_NAME = "aios.yaml"


class Settings(BaseSettings):
    """Environment: where things are, and every secret. Nothing here is personal data."""

    model_config = SettingsConfigDict(extra="ignore")

    data_dir: Path = Field(Path("/data"), alias="AIOS_DATA_DIR")
    config_file: Path | None = Field(None, alias="AIOS_CONFIG_FILE")
    repo_dir: Path = Field(_REPO_DIR, alias="AIOS_REPO_DIR")
    log_level: str = Field("INFO", alias="AIOS_LOG_LEVEL")

    # The channels' tokens and addresses (SLACK_BOT_TOKEN, SIGNAL_SENDER, …) are
    # not read here: each channel type reads its own, as Variables or from here.

    # Voice notes (OPENAI_API_KEY, AIOS_TRANSCRIBE_LANGUAGE) are read by the
    # transcriber itself, as Variables or from here.

    config_remote: str | None = Field(None, alias="AIOS_CONFIG_REMOTE")
    """The configuration repository to clone when the data dir has none: how a new
    machine gets its whole configuration back. Signed in with one of the next two."""
    config_ssh_key: str | None = Field(None, alias="AIOS_CONFIG_SSH_KEY")
    config_token: str | None = Field(None, alias="AIOS_CONFIG_TOKEN")

    initial_config: str | None = Field(None, alias="AIOS_INITIAL_CONFIG")
    """The first `config.yaml` (YAML or JSON), for a data dir with neither a
    repository nor a remote to clone: how a one-shot deployment (a cloud template)
    sets the owner and the login before the first start. Ignored afterwards."""
    owner_password: str | None = Field(None, alias="AIOS_OWNER_PASSWORD")
    """The owner's first console password, for `web.auth.mode: password` from the
    first start. Set only while no user has a password."""

    variable_files: Path | None = Field(None, alias="AIOS_VARIABLE_FILES_DIR")
    """Where `${file:NAME}` values are written; best a tmpfs, so a decrypted copy
    never reaches a disk. Never inside the data dir. Default: a folder in the system's
    temporary directory."""

    secrets_key: str | None = Field(None, alias="AIOS_SECRETS_KEY")
    """Required. Encrypts the secrets stored in the data dir (variables, connector
    sign-ins, the configuration remote's key): a Fernet key or a long generated
    password, kept outside the data dir (`SecretsKeySource`)."""
    secrets_key_previous: str | None = Field(None, alias="AIOS_SECRETS_KEY_PREVIOUS")
    """The key before `secrets_key`, only while replacing it: ai-os moves every secret
    onto the new key at start, then this is removed."""

    def resolved_config_file(self) -> Path:
        """`aios.yaml` in the configuration repository; before that exists, the
        data dir's `config.yaml`, which the first start moves into the repository."""
        if self.config_file:
            return self.config_file
        in_repo = self.config_dir() / CONFIG_FILE_NAME
        return in_repo if in_repo.exists() else self.legacy_config_file()

    def legacy_config_file(self) -> Path:
        return self.data_dir / "config.yaml"

    def config_dir(self) -> Path:
        """The configuration repository: agents, skills, connectors, triggers."""
        return self.data_dir / "config"

    def secrets_key_file(self) -> Path:
        """The key an older ai-os generated when `AIOS_SECRETS_KEY` was not set."""
        return self.data_dir / "secrets.key"

    def variable_files_dir(self) -> Path:
        """Where `${file:NAME}` variables are written for the MCP servers that read them."""
        return self.variable_files or Path(tempfile.gettempdir()) / "aios-variable-files"

    def legacy_variable_files_dir(self) -> Path:
        """Where an older ai-os wrote them: removed at start."""
        return self.data_dir / "variable-files"

    def known_hosts_file(self) -> Path:
        """SSH host keys of the configuration repository's remote, learnt on first use."""
        return self.data_dir / "git" / "known_hosts"

    def log_file(self) -> Path:
        return self.data_dir / "logs" / "aios.log"

    def startup_notice_file(self) -> Path:
        return self.data_dir / "startup_notice"
