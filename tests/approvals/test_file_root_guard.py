from aios.approvals.file_access_rule import FileAccessRule
from aios.approvals.file_root_guard import FileRootGuard
from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.config.files_config import FilesConfig
from aios.entities.users.user import User


def test_the_disk_the_system_and_protected_folders_are_refused(tmp_path) -> None:
    data = tmp_path / "data"
    guard = FileRootGuard([data])
    assert "whole disk" in (guard.problem("/") or "")
    assert "/proc" in (guard.problem("/proc/self") or "")
    assert "inside" in (guard.problem(str(data / "config")) or "")
    assert "contains" in (guard.problem(str(tmp_path)) or "")
    assert "absolute" in (guard.problem("vault") or "")
    assert guard.problem(str(tmp_path / "vault")) is None


def test_a_symlink_into_a_protected_folder_is_refused(tmp_path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (tmp_path / "innocent").symlink_to(data)
    assert FileRootGuard([data]).problem(str(tmp_path / "innocent")) is not None


def test_the_rule_leaves_out_a_root_the_guard_refuses(tmp_path) -> None:
    data = tmp_path / "data"
    (data / "users").mkdir(parents=True)
    rule = FileAccessRule(lambda: FilesConfig(read_roots=[str(tmp_path)]), FileRootGuard([data]))
    call = ToolCall(
        tool_name="Read",
        tool_input={"file_path": str(data / "users" / "a.json")},
        user=User(id="u", name="U"),
        conversation_id="c",
    )
    decision = rule.evaluate(call)
    assert decision is not None and decision.verdict is PolicyVerdict.DENY
