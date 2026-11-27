import subprocess
from importlib.metadata import version
from pathlib import Path


class BuildVersion:
    """The package version and the commit it was built from: `2.0.0 (ee2ee59)`.

    The image has no `.git`, so its build writes the commit into `aios/COMMIT`
    (with `-dirty` when the tree had changes). Run from a clone, git answers.
    """

    def __init__(self) -> None:
        self.version = version("aios")
        self.commit = self._commit()

    def describe(self) -> str:
        return f"{self.version} ({self.commit})" if self.commit else self.version

    @staticmethod
    def _commit() -> str | None:
        package = Path(__file__).resolve().parent.parent
        stamped = package / "COMMIT"
        if stamped.is_file():
            return stamped.read_text().strip() or None
        try:
            done = subprocess.run(
                ["git", "describe", "--always", "--dirty", "--abbrev=7"],
                cwd=package.parent,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        return done.stdout.strip() or None
