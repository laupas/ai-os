from aios.approvals.deny_list_rule import DenyListRule
from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.config.app_config import AppConfig
from aios.config.app_config_watcher import AppConfigWatcher
from aios.config.live_app_config import LiveAppConfig
from aios.entities.users.user import User

STARTED = "channels: [web]\napproval: {deny: [mcp__x__send]}\n"


def _live() -> LiveAppConfig:
    live = LiveAppConfig(AppConfig.model_validate({"channels": ["web"]}))
    live.apply(STARTED)
    return live


def _call(tool: str) -> ToolCall:
    return ToolCall(tool_name=tool, tool_input={}, user=User(id="u", name="U"), conversation_id="c")


def test_a_change_applies_to_what_reads_it_on_use() -> None:
    live = _live()
    rule = DenyListRule(lambda: live.current().approval)
    assert rule.evaluate(_call("mcp__x__send")).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]

    assert live.apply("channels: [web]\napproval: {deny: [mcp__x__delete]}\n")

    assert rule.evaluate(_call("mcp__x__send")) is None
    assert rule.evaluate(_call("mcp__x__delete")) is not None


def test_a_file_that_does_not_load_keeps_the_previous_one() -> None:
    live = _live()
    assert not live.apply("approval: {deny: nope: [}")
    assert not live.apply("scheduler: {tick_seconds: soon}")
    assert live.current().approval.deny == ["mcp__x__send"]


def test_only_startup_sections_need_a_restart() -> None:
    live = LiveAppConfig(AppConfig.model_validate({"channels": ["web"]}))
    assert not live.restart_needed("channels: [web]\ntimezone: UTC\nagent: {model: opus}\n")
    assert not live.restart_needed("channels: [web]\nfiles: {read_roots: [/vault]}\n")
    assert live.restart_needed("channels: [web, slack]\n")
    assert live.restart_needed("channels: [web]\nweb: {enabled: true}\n")
    assert live.restart_needed("channels: [web]\ncollection_access: {users: read}\n")
    assert live.restart_needed("not: [yaml")


async def test_the_watcher_applies_what_it_reads() -> None:
    live = _live()
    text = {"now": STARTED}
    watcher = AppConfigWatcher(live, lambda: text["now"], interval_seconds=0)

    await watcher.check()
    assert live.current().approval.deny == ["mcp__x__send"]

    text["now"] = "channels: [web]\ntimezone: UTC\n"
    await watcher.check()
    assert live.current().timezone == "UTC" and live.current().approval.deny == []


async def test_the_watcher_keeps_the_config_without_a_file() -> None:
    live = _live()
    await AppConfigWatcher(live, lambda: None).check()
    assert live.current().approval.deny == ["mcp__x__send"]
