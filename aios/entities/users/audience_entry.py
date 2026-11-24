from typing import Annotated

from pydantic import StringConstraints

EVERYONE = "everyone"
"""The built-in group everybody is in."""

AudienceEntry = Annotated[str, StringConstraints(pattern=r"^(everyone|group:[A-Za-z0-9_.-]+)$")]
"""A group an agent or connector is available to: `everyone` or `group:<id>`.
Administrators always are."""
