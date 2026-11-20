import logging
import os
from collections.abc import Callable

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.file_root_guard import FileRootGuard
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.config.files_config import FilesConfig

log = logging.getLogger(__name__)

_READ_TOOLS = {"Read": "file_path", "Grep": "path", "Glob": "path"}
_WRITE_TOOLS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path"}


class FileAccessRule(ApprovalRule):
    """Keeps the built-in file tools inside the configured folders.

    Paths are resolved (symlinks, `..`) before they are compared, and a search
    without an explicit path is refused, since it would start in the app's own
    directory. Everything else, such as /proc or the data dir, is out of reach, and
    a configured folder that would reach them (`/`, `/data`, …) is left out.

    The folders are those of aios.yaml as it is now, worked out again when it changes.
    """

    def __init__(
        self, config: Callable[[], FilesConfig], guard: FileRootGuard | None = None
    ) -> None:
        self._config = config
        self._guard = guard or FileRootGuard()
        self._seen: FilesConfig | None = None
        self._read_roots: list[str] = []
        self._write_roots: list[str] = []
        self._refresh()  # the folders left out are logged at start, not at the first call

    def _refresh(self) -> None:
        config = self._config()
        if config == self._seen:
            return
        for root in config.read_roots + config.write_roots:
            problem = self._guard.problem(root)
            if problem:
                log.warning("files: left out %s", problem)
        self._read_roots = [
            self._real(r) for r in self._guard.allowed(config.read_roots + config.write_roots)
        ]
        self._write_roots = [self._real(r) for r in self._guard.allowed(config.write_roots)]
        self._seen = config

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        self._refresh()
        if call.tool_name in _WRITE_TOOLS:
            path = call.tool_input.get(_WRITE_TOOLS[call.tool_name])
            return self._check(path, self._write_roots, "write")
        if call.tool_name == "Glob":
            return self._check_glob(call)
        if call.tool_name in _READ_TOOLS:
            path = call.tool_input.get(_READ_TOOLS[call.tool_name])
            return self._check(path, self._read_roots, "read")
        return None

    def _check_glob(self, call: ToolCall) -> PolicyDecision | None:
        path = call.tool_input.get("path")
        pattern = str(call.tool_input.get("pattern", ""))
        if ".." in pattern.split("/"):
            return PolicyDecision.deny("Glob patterns may not contain '..'.")
        if path is None and os.path.isabs(pattern):
            path = pattern.split("*", 1)[0] or "/"
        elif path is not None and os.path.isabs(pattern):
            return PolicyDecision.deny("Give Glob a relative pattern inside its path.")
        return self._check(path, self._read_roots, "read")

    def _check(self, path: object, roots: list[str], action: str) -> PolicyDecision | None:
        if not roots:
            return PolicyDecision.deny(f"No folder is configured that agents may {action}.")
        if not isinstance(path, str) or not os.path.isabs(path):
            return PolicyDecision.deny(f"Use an absolute path inside: {', '.join(roots)}.")
        real = self._real(path)
        if any(real == root or real.startswith(root + os.sep) for root in roots):
            return None  # inside: no objection, later rules may still ask
        return PolicyDecision.deny(f"{path} is outside the folders agents may {action}.")

    @staticmethod
    def _real(path: str) -> str:
        return os.path.realpath(path).rstrip(os.sep) or os.sep
