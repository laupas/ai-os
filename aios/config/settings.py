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

    slack_bot_token: str | None = Field(None, alias="SLACK_BOT_TOKEN")
    slack_app_token: str | None = Field(None, alias="SLACK_APP_TOKEN")

    signal_api_url: str = Field("http://signal-api:8080", alias="SIGNAL_API_URL")
    signal_sender: str | None = Field(None, alias="SIGNAL_SENDER")

    resend_api_key: str | None = Field(None, alias="RESEND_API_KEY")
    mail_from: str | None = Field(None, alias="AIOS_MAIL_FROM")

    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    transcribe_language: str | None = Field(None, alias="AIOS_TRANSCRIBE_LANGUAGE")

    config_remote: str | None = Field(None, alias="AIOS_CONFIG_REMOTE")
    """The configuration repository to clone when the data dir has none: how a new
    machine gets its whole configuration back. Signed in with one of the next two."""
    config_ssh_key: str | None = Field(None, alias="AIOS_CONFIG_SSH_KEY")
    config_token: str | None = Field(None, alias="AIOS_CONFIG_TOKEN")

    secrets_key: str | None = Field(None, alias="AIOS_SECRETS_KEY")
    """Encrypts the secret variables set in the console: a Fernet key or a long
    generated password. Unset, a key is generated into the data dir."""

    kraken_api_key: str | None = Field(None, alias="KRAKEN_API_KEY")
    kraken_api_secret: str | None = Field(None, alias="KRAKEN_API_SECRET")

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
        """The configuration repository: agents, skills, connectors, schedules."""
        return self.data_dir / "config"

    def secrets_key_file(self) -> Path:
        return self.data_dir / "secrets.key"

    def variable_files_dir(self) -> Path:
        """Where `${file:NAME}` variables are written for the MCP servers that read them."""
        return self.data_dir / "variable-files"

    def known_hosts_file(self) -> Path:
        """SSH host keys of the configuration repository's remote, learnt on first use."""
        return self.data_dir / "git" / "known_hosts"

    def log_file(self) -> Path:
        return self.data_dir / "logs" / "aios.log"

    def startup_notice_file(self) -> Path:
        return self.data_dir / "startup_notice"
