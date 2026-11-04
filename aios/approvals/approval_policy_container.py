from dependency_injector import containers, providers

from aios.approvals.always_ask_rule import AlwaysAskRule
from aios.approvals.deny_list_rule import DenyListRule
from aios.approvals.file_access_rule import FileAccessRule
from aios.approvals.known_tools_rule import KnownToolsRule
from aios.approvals.rule_based_approval_policy import RuleBasedApprovalPolicy


class ApprovalPolicyContainer(containers.DeclarativeContainer):
    """General rules first (unknown or denied tools refused, files kept in their
    folders, `approval.always` asked), then the rules other domains contribute."""

    approval_config = providers.Dependency()
    files_config = providers.Dependency()
    builtin_tools = providers.Dependency()
    tool_prefixes = providers.Dependency()
    extra_rules = providers.Dependency(default=[])

    known_tools_rule = providers.Singleton(
        KnownToolsRule, builtin_tools=builtin_tools, tool_prefixes=tool_prefixes
    )
    deny_list_rule = providers.Singleton(DenyListRule, tool_names=approval_config.provided.deny)
    file_access_rule = providers.Singleton(FileAccessRule, config=files_config)
    always_ask_rule = providers.Singleton(AlwaysAskRule, tool_names=approval_config.provided.always)
    policy = providers.Singleton(
        RuleBasedApprovalPolicy,
        rules=providers.Callable(
            lambda *rules: [*rules[:-1], *rules[-1]],
            known_tools_rule,
            deny_list_rule,
            file_access_rule,
            always_ask_rule,
            extra_rules,
        ),
    )
