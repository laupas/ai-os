class WebhookTemplateError(Exception):
    """A destination's templates cannot be filled in, e.g. a Variable is not set."""
