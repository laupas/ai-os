import base64
import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

from aios.common.clock import Clock
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.oauth_client import OAuthClient
from aios.connectors.oauth_error import OAuthError
from aios.connectors.oauth_metadata import OAuthMetadata
from aios.connectors.pending_sign_in import PendingSignIn
from aios.entities.connectors.connector_token import ConnectorToken
from aios.storage.collection import Collection

log = logging.getLogger(__name__)

PENDING_FOR = timedelta(minutes=15)
RENEW_BEFORE = timedelta(minutes=10)


class ConnectorAuthorizer:
    """Signs a connector in with OAuth from the console, the way Claude Code's
    `/mcp` would, except that the browser comes back to ai-os instead of to a
    localhost port inside the container.

    `start` registers ai-os with the server (once per sign-in) and returns where to
    send the browser; `finish` exchanges the code for tokens. PKCE protects the
    code, and the single-use `state` ties the return to the start, which is what
    replaces the console's CSRF header on that one request.

    A connector with its own `oauth:` client (Google: no discovery, no
    registration) skips both and signs in with the client it names.
    """

    def __init__(
        self,
        connectors: ConnectorCatalog,
        tokens: Collection[ConnectorToken],
        client: OAuthClient,
        clock: Clock,
    ) -> None:
        self._connectors = connectors
        self._tokens = tokens
        self._client = client
        self._clock = clock
        self._pending: dict[str, PendingSignIn] = {}

    def url_of(self, name: str) -> str | None:
        """The connector's server address, if it is one that can be signed in to."""
        connector = self._connectors.get(name)
        url = connector.config.get("url") if connector else None
        return url if isinstance(url, str) and url.startswith("https://") else None

    async def start(self, name: str, user_id: str, redirect_uri: str) -> str:
        url = self.url_of(name)
        if url is None:
            raise OAuthError("only a connector with an https address can be signed in to")
        configured = self._connectors.oauth_of(name)
        if configured is None:
            meta = await self._client.discover(url)
            client_id, client_secret, method = await self._client.register(meta, redirect_uri)
        else:
            meta = OAuthMetadata(
                authorization_endpoint=configured.authorization_endpoint,
                token_endpoint=configured.token_endpoint,
                scopes=configured.scopes,
                params=configured.params,
            )
            client_id, client_secret = configured.client_id, configured.client_secret
            method = configured.auth_method
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        state = secrets.token_urlsafe(24)
        self._drop_stale()
        self._pending[state] = PendingSignIn(
            connector=name,
            user_id=user_id,
            verifier=verifier,
            redirect_uri=redirect_uri,
            metadata=meta,
            client_id=client_id,
            client_secret=client_secret,
            auth_method=method,
            started_at=self._clock.now(),
        )
        query: dict[str, str] = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge.decode().rstrip("="),
            "code_challenge_method": "S256",
            **meta.params,
        }
        if meta.resource:
            query["resource"] = meta.resource
        if meta.scopes:
            query["scope"] = " ".join(meta.scopes)
        separator = "&" if "?" in meta.authorization_endpoint else "?"
        return meta.authorization_endpoint + separator + urlencode(query)

    async def finish(self, state: str, code: str, user_id: str, user_name: str) -> str:
        """Returns the connector's name once its tokens are stored."""
        self._drop_stale()
        pending = self._pending.pop(state, None)
        if pending is None:
            raise OAuthError("this sign-in is unknown or expired; start it again")
        if pending.user_id != user_id:
            raise OAuthError("this sign-in was started by somebody else")
        data = await self._client.token(
            pending.metadata.token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": pending.redirect_uri,
                "code_verifier": pending.verifier,
                **({"resource": pending.metadata.resource} if pending.metadata.resource else {}),
            },
            pending.client_id,
            pending.client_secret,
            pending.auth_method,
        )
        now = self._clock.now()
        await self._tokens.put(
            ConnectorToken(
                id=pending.connector,
                token_endpoint=pending.metadata.token_endpoint,
                client_id=pending.client_id,
                client_secret=pending.client_secret,
                auth_method=pending.auth_method,
                resource=pending.metadata.resource,
                signed_in_by=user_name,
                signed_in_at=now,
                **self._token_fields(data),
            )
        )
        log.info("connector %s signed in by %s", pending.connector, user_name)
        return pending.connector

    async def sign_out(self, name: str) -> None:
        await self._tokens.delete(name)

    async def renew_due(self) -> None:
        """Renews every token that expires soon. A failed renewal is logged; the
        connector then answers needs-auth until somebody signs in again."""
        soon = self._clock.now() + RENEW_BEFORE
        for token in self._tokens.all():
            if not token.refresh_token or token.expires_at is None or token.expires_at > soon:
                continue
            try:
                data = await self._client.token(
                    token.token_endpoint,
                    {
                        "grant_type": "refresh_token",
                        "refresh_token": token.refresh_token,
                        **({"resource": token.resource} if token.resource else {}),
                    },
                    token.client_id,
                    token.client_secret,
                    token.auth_method,
                )
            except OAuthError:
                log.exception("could not renew the sign-in of connector %s", token.id)
                continue
            fields = self._token_fields(data)
            fields.setdefault("refresh_token", token.refresh_token)  # not every server rotates it
            await self._tokens.put(token.model_copy(update=fields))
            log.info("renewed the sign-in of connector %s", token.id)

    def _token_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        fields: dict[str, Any] = {"access_token": data["access_token"]}
        if data.get("refresh_token"):
            fields["refresh_token"] = data["refresh_token"]
        if isinstance(data.get("expires_in"), int | float):
            fields["expires_at"] = self._clock.now() + timedelta(seconds=data["expires_in"])
        return fields

    def _drop_stale(self) -> None:
        cutoff = self._clock.now() - PENDING_FOR
        for state in [s for s, p in self._pending.items() if p.started_at < cutoff]:
            del self._pending[state]
