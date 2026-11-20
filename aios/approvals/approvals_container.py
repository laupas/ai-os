from dependency_injector import containers, providers

from aios.approvals.approval_service import ApprovalService


class ApprovalsContainer(containers.DeclarativeContainer):
    """The approval service. The policy is in `ApprovalPolicyContainer`, because it
    takes rules from the tools, and one of the tools needs this service."""

    approvals = providers.Dependency()
    users = providers.Dependency()
    authorizer = providers.Dependency()
    presenters = providers.Dependency()
    clock = providers.Dependency()
    ids = providers.Dependency()
    approval_config = providers.Dependency()  # a getter: aios.yaml as it is now
    conversations = providers.Dependency()
    observers = providers.Dependency(default=[])

    service = providers.Singleton(
        ApprovalService,
        approvals=approvals,
        users=users,
        authorizer=authorizer,
        presenters=presenters,
        clock=clock,
        ids=ids,
        timeout_seconds=providers.Callable(lambda c: lambda: c().timeout_seconds, approval_config),
        conversations=conversations,
        observers=observers,
    )
