import uuid


class IdGenerator:
    """Creates ids that are safe to use as file names."""

    def new_id(self) -> str:
        return uuid.uuid4().hex[:16]
