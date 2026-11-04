import os

import pytest

from aios.approvals.deny_list_rule import DenyListRule
from aios.approvals.file_access_rule import FileAccessRule
from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.config.files_config import FilesConfig
from aios.entities.users.user import User

USER = User(id="u", name="U")


def _call(tool: str, **tool_input: object) -> ToolCall:
    return ToolCall(tool_name=tool, tool_input=tool_input, user=USER, conversation_id="c")


@pytest.fixture
def vault(tmp_path) -> str:
    (tmp_path / "vault" / "notes").mkdir(parents=True)
    (tmp_path / "secret").mkdir()
    return str(tmp_path / "vault")


def test_reads_and_writes_inside_the_vault_pass(vault: str) -> None:
    rule = FileAccessRule(FilesConfig(write_roots=[vault]))
    assert rule.evaluate(_call("Read", file_path=f"{vault}/notes/a.md")) is None
    assert rule.evaluate(_call("Write", file_path=f"{vault}/new.md")) is None
    assert rule.evaluate(_call("Grep", path=vault, pattern="x")) is None
    assert rule.evaluate(_call("Glob", pattern=f"{vault}/**/*.md")) is None


@pytest.mark.parametrize(
    "tool,args",
    [
        ("Read", {"file_path": "/proc/self/environ"}),
        ("Read", {"file_path": "relative.md"}),
        ("Grep", {"pattern": "x"}),  # no path: would search the app dir
        ("Glob", {"pattern": "**/*.md"}),
        ("Glob", {"pattern": "*/../../secret/*"}),
    ],
)
def test_everything_else_is_refused(vault: str, tool: str, args: dict[str, object]) -> None:
    rule = FileAccessRule(FilesConfig(read_roots=[vault]))
    decision = rule.evaluate(_call(tool, **args))
    assert decision is not None and decision.verdict is PolicyVerdict.DENY


def test_dot_dot_and_symlinks_cannot_escape(vault: str) -> None:
    os.symlink(os.path.join(vault, "..", "secret"), os.path.join(vault, "link"))
    rule = FileAccessRule(FilesConfig(write_roots=[vault]))
    for path in (f"{vault}/../secret/x", f"{vault}/link/x"):
        decision = rule.evaluate(_call("Read", file_path=path))
        assert decision is not None and decision.verdict is PolicyVerdict.DENY


def test_read_only_roots_refuse_writes(vault: str) -> None:
    rule = FileAccessRule(FilesConfig(read_roots=[vault]))
    decision = rule.evaluate(_call("Edit", file_path=f"{vault}/a.md"))
    assert decision is not None and decision.verdict is PolicyVerdict.DENY


def test_no_roots_means_no_file_access() -> None:
    decision = FileAccessRule(FilesConfig()).evaluate(_call("Read", file_path="/vault/a.md"))
    assert decision is not None and decision.verdict is PolicyVerdict.DENY


def test_other_tools_are_not_its_business() -> None:
    assert FileAccessRule(FilesConfig()).evaluate(_call("WebSearch", query="x")) is None


def test_deny_list() -> None:
    rule = DenyListRule(["mcp__gmail__send_email"])
    assert rule.evaluate(_call("mcp__gmail__send_email")).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]
    assert rule.evaluate(_call("mcp__gmail__read_email")) is None
