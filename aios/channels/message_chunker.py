class MessageChunker:
    """Splits long text into pieces under a size limit, preferring line breaks."""

    def __init__(self, size: int = 3500) -> None:
        if size <= 0:
            raise ValueError("size must be positive")
        self._size = size

    def split(self, text: str) -> list[str]:
        chunks: list[str] = []
        rest = text
        while len(rest) > self._size:
            cut = rest.rfind("\n", 0, self._size)
            if cut <= 0:
                cut = self._size
            chunks.append(rest[:cut])
            rest = rest[cut:].lstrip("\n")
        if rest or not chunks:
            chunks.append(rest)
        return chunks
