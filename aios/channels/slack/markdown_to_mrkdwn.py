import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_HEADER = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.*?)[ \t]*$", re.MULTILINE)
_SEPARATOR_CELL = re.compile(r":?-{1,}:?")


class MarkdownToMrkdwn:
    """Converts the Markdown agents write into Slack's mrkdwn.

    Slack has no headers, uses single-star bold and `<url|text>` links, and cannot
    show tables, so a table becomes an aligned code block. Code fences are kept as
    they are. Ported from the v1 Slack bridge.
    """

    def convert(self, text: str) -> str:
        parts = text.split("```")
        for index in range(0, len(parts), 2):  # even parts are outside code fences
            segment = parts[index]
            segment = _HEADER.sub(r"*\1*", segment)
            segment = _BOLD.sub(r"*\1*", segment)
            segment = _LINK.sub(r"<\2|\1>", segment)
            parts[index] = self._convert_tables(segment)
        return "```".join(parts)

    def _convert_tables(self, text: str) -> str:
        lines = text.split("\n")
        out: list[str] = []
        i = 0
        while i < len(lines):
            if self._starts_table(lines, i):
                rows = [self._cells(lines[i])]
                j = i + 2
                while j < len(lines) and "|" in lines[j] and lines[j].strip():
                    rows.append(self._cells(lines[j]))
                    j += 1
                out.append(self._render(rows))
                i = j
            else:
                out.append(lines[i])
                i += 1
        return "\n".join(out)

    def _starts_table(self, lines: list[str], i: int) -> bool:
        if "|" not in lines[i] or i + 1 >= len(lines) or "|" not in lines[i + 1]:
            return False
        cells = self._cells(lines[i + 1])
        return bool(cells) and all(c and _SEPARATOR_CELL.fullmatch(c) for c in cells)

    @staticmethod
    def _cells(line: str) -> list[str]:
        stripped = line.strip().removeprefix("|").removesuffix("|")
        return [c.strip() for c in stripped.split("|")]

    @staticmethod
    def _render(rows: list[list[str]]) -> str:
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        sizes = [max(len(r[c]) for r in rows) for c in range(width)]
        lines = []
        for index, row in enumerate(rows):
            lines.append("  ".join(row[c].ljust(sizes[c]) for c in range(width)).rstrip())
            if index == 0:
                lines.append("  ".join("-" * sizes[c] for c in range(width)))
        return "```\n" + "\n".join(lines) + "\n```"
