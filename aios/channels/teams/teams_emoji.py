import re

_SHORTCODE = re.compile(r":([a-z0-9_+-]+):")
_EMOJI = {
    "alarm_clock": "⏰",
    "large_green_circle": "🟢",
    "white_check_mark": "✅",
    "raised_hand": "✋",
    "studio_microphone": "🎙️",
    "hourglass_flowing_sand": "⏳",
    "warning": "⚠️",
    "x": "❌",
}


class TeamsEmoji:
    """Turns the Slack emoji shortcodes ai-os writes (`:alarm_clock:`) into the
    characters, as Teams shows shortcodes literally. Unknown ones are left alone."""

    def convert(self, text: str) -> str:
        return _SHORTCODE.sub(lambda m: _EMOJI.get(m.group(1), m.group(0)), text)
