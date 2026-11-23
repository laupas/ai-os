class StoreError(Exception):
    """An install that cannot go ahead, with why, for the console."""

    def __init__(self, message: str, conflict: bool = False) -> None:
        super().__init__(message)
        self.conflict = conflict
        """The item is installed already and replacing it was not asked for."""
