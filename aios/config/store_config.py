from pydantic import BaseModel, ConfigDict

from aios.config.store_source import StoreSource

TEMPLATES = "https://github.com/laupas/ai-os-templates"


class StoreConfig(BaseModel):
    """Where the console's Store finds what it offers."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    sources: list[StoreSource] = [StoreSource(url=TEMPLATES)]
    """Git repositories laid out like a configuration repository; the first one
    that has an item wins."""
