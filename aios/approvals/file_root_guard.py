import os
from pathlib import Path

# Never a root, wherever ai-os runs: the process's environment (every secret) is
# readable under /proc, and decrypted copies of variables may sit under /run.
SYSTEM = ["/proc", "/sys", "/dev", "/run", "/etc", "/boot", "/root"]


class FileRootGuard:
    """Which folders may be given to agents' file tools. Refused: `/`, the system
    folders, and `protected` (the data dir, ai-os's own code, the decrypted
    variable files), and any folder inside or around one of them."""

    def __init__(self, protected: list[Path | str] | None = None) -> None:
        self._protected = sorted({self._real(str(p)) for p in [*SYSTEM, *(protected or [])]})

    def problem(self, root: str) -> str | None:
        """Why `root` may not be given, or None."""
        if not root or not os.path.isabs(root):
            return f"{root or '(empty)'}: give an absolute path"
        real = self._real(root)
        if real == os.sep:
            return f"{root}: not the whole disk"
        for protected in self._protected:
            if real == protected or real.startswith(protected + os.sep):
                return f"{root}: inside {protected}, which agents may never reach"
            if protected.startswith(real + os.sep):
                return f"{root}: contains {protected}, which agents may never reach"
        return None

    def allowed(self, roots: list[str]) -> list[str]:
        return [r for r in roots if self.problem(r) is None]

    @property
    def protected(self) -> list[str]:
        return list(self._protected)

    @staticmethod
    def _real(path: str) -> str:
        return os.path.realpath(path).rstrip(os.sep) or os.sep
