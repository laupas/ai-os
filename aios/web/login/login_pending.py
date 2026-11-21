class LoginPending(Exception):
    """A sign-in needs another step (a code was sent); the message says what to do."""
