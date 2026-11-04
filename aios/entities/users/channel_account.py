from pydantic import BaseModel


class ChannelAccount(BaseModel):
    """One way to reach a user: a Slack user id, a phone number, a mail address."""

    channel: str
    address: str
