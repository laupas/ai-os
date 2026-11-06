import logging
from typing import Any

from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.connectors.sign_in_mode import SignInMode
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.variables.secret_box import SecretBox

log = logging.getLogger(__name__)

SECRET_FIELDS = ("access_token", "refresh_token", "client_secret")


class ConnectorTokens:
    """Connector sign-ins, one per connector and account, encrypted at rest.

    Everything handed out is decrypted; everything stored is encrypted with the same
    key as the console's secret variables (`AIOS_SECRETS_KEY`). A token that cannot be
    decrypted (the key changed) counts as not signed in.
    """

    def __init__(self, tokens: Collection[ConnectorToken], box: SecretBox) -> None:
        self._tokens = tokens
        self._box = box

    @staticmethod
    def key(connector: str, user_id: str | None) -> str:
        return f"{connector}.shared" if user_id is None else f"{connector}.user.{user_id}"

    def shared(self, connector: str) -> ConnectorToken | None:
        return self._get(self.key(connector, None))

    def of_user(self, connector: str, user_id: str) -> ConnectorToken | None:
        return self._get(self.key(connector, user_id))

    def for_turn(self, connector: Connector, user: User | None) -> ConnectorToken | None:
        """The account a turn of `user` uses. A shared connector: the shared one. Per
        user: the user's own, the shared one only if the connector falls back to it.
        A run without a user takes the shared one, if there is one."""
        if user is None or connector.sign_in is SignInMode.SHARED:
            return self.shared(connector.id)
        own = self.of_user(connector.id, user.id)
        if own is not None or not connector.shared_fallback:
            return own
        return self.shared(connector.id)

    def users_signed_in(self, connector: str) -> int:
        return len(
            self._tokens.filter(lambda t: t.connector == connector and t.user_id is not None)
        )

    def all(self) -> list[ConnectorToken]:
        return [t for t in (self._open(s) for s in self._tokens.all()) if t is not None]

    async def put(self, token: ConnectorToken) -> ConnectorToken:
        token = token.model_copy(update={"id": self.key(token.connector, token.user_id)})
        await self._tokens.put(self._seal(token))
        return token

    async def delete(self, connector: str, user_id: str | None) -> None:
        await self._tokens.delete(self.key(connector, user_id))

    async def migrate(self) -> None:
        """Moves each token to its key and encrypts it: the one token per connector
        from before 2026-11-06 becomes that connector's shared sign-in."""
        for stored in self._tokens.all():
            key = self.key(stored.connector, stored.user_id)
            if stored.id == key and stored.encrypted:
                continue
            token = self._open(stored)
            if token is None:
                continue
            await self.put(token)
            if stored.id != key:
                await self._tokens.delete(stored.id)
            log.info("moved connector sign-in %s to %s, encrypted", stored.id, key)

    def _get(self, key: str) -> ConnectorToken | None:
        stored = self._tokens.get(key)
        return self._open(stored) if stored is not None else None

    def _seal(self, token: ConnectorToken) -> ConnectorToken:
        fields = {f: self._box.encrypt(v) for f in SECRET_FIELDS if (v := getattr(token, f))}
        return token.model_copy(update={**fields, "encrypted": True})

    def _open(self, stored: ConnectorToken) -> ConnectorToken | None:
        if not stored.encrypted:
            return stored
        fields: dict[str, Any] = {"encrypted": False}
        for name in SECRET_FIELDS:
            value = getattr(stored, name)
            if value:
                fields[name] = self._box.decrypt(value)
                if fields[name] is None:
                    log.error("the sign-in %s cannot be decrypted; sign in again", stored.id)
                    return None
        return stored.model_copy(update=fields)
