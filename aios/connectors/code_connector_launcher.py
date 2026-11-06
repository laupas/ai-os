import os
import sys

# Kept from the environment besides what the manifest declares: enough for Python
# and the network to work, nothing that is ai-os's.
BASE = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "SSL_CERT_FILE", "SSL_CERT_DIR")


class CodeConnectorLauncher:
    """Starts a code connector's server with only the variables named in
    `AIOS_CONNECTOR_KEEP`. Claude Code starts every MCP server with its own
    environment, which is ai-os's, secrets included; this is where they are left
    behind. The values travel in the environment, never on the command line."""

    @staticmethod
    def environment(current: dict[str, str]) -> dict[str, str]:
        keep = {n for n in current.get("AIOS_CONNECTOR_KEEP", "").split(",") if n}
        kept = {k: v for k, v in current.items() if k in keep or k in BASE}
        # The server's folder is in the configuration repository: bytecode written
        # beside it would leave the repository unclean, and a branch switch refused.
        return {**kept, "PYTHONDONTWRITEBYTECODE": "1"}

    @classmethod
    def main(cls, argv: list[str]) -> None:
        server, *rest = argv
        os.execve(
            sys.executable, [sys.executable, server, *rest], cls.environment(dict(os.environ))
        )


if __name__ == "__main__":
    CodeConnectorLauncher.main(sys.argv[1:])
