import base64
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class GitCredentials:
    """How one git command signs in to a remote, as environment variables.

    An SSH key becomes a temporary file (0600) named in GIT_SSH_COMMAND; a token
    becomes an HTTP header passed through git's GIT_CONFIG_* variables. Neither is
    written to the repository's config or appears in a process list, and either is
    gone when the command is.
    """

    @staticmethod
    @contextmanager
    def env(ssh_key: str | None, token: str | None, known_hosts: Path) -> Iterator[dict[str, str]]:
        env = {"GIT_TERMINAL_PROMPT": "0"}  # fail, never wait for a password
        if token:
            basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            env.update(
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "http.extraHeader",
                    "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
                }
            )
            yield env
            return
        if ssh_key:
            known_hosts.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="aios-ssh-") as tmp:
                key_file = Path(tmp) / "key"
                fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as handle:
                    handle.write(ssh_key.strip() + "\n")
                env["GIT_SSH_COMMAND"] = (
                    f"ssh -i {key_file} -o IdentitiesOnly=yes -o BatchMode=yes "
                    f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={known_hosts}"
                )
                yield env
            return
        yield env
