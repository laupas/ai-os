from pydantic import BaseModel


class ChannelBinding(BaseModel):
    """Where a conversation lives on one channel.

    `address` is the place (a Slack channel id, "local" for the CLI) and `thread`
    the conversation inside it (a Slack thread ts).
    """

    channel: str
    address: str
    thread: str

    def same_place(self, other: "ChannelBinding") -> bool:
        return (self.channel, self.address, self.thread) == (
            other.channel,
            other.address,
            other.thread,
        )
