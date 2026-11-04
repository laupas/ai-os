from contextvars import ContextVar

from aios.config_repo.change_author import ChangeAuthor

AIOS = ChangeAuthor(name="ai-os", email="ai-os@localhost")

_author: ContextVar[ChangeAuthor] = ContextVar("config_author", default=AIOS)


class CurrentAuthor:
    """The author of changes made in the current task: a console user while their
    request is handled, ai-os itself otherwise (an agent's write, a schedule run)."""

    @staticmethod
    def get() -> ChangeAuthor:
        return _author.get()

    @staticmethod
    def set(author: ChangeAuthor) -> None:
        _author.set(author)
