import base64
import hashlib
import logging
from typing import Any
from urllib.parse import urlencode

from aios.config.sso_provider import SsoProvider
from aios.config.web_auth_config import WebAuthConfig
from aios.entities.users.user import User
from aios.variables.variable_resolver import VariableResolver
from aios.web.login.console_users import ConsoleUsers
from aios.web.login.login_refused import LoginRefused
from aios.web.login.login_request import LoginRequest
from aios.web.login.new_user_maker import NewUserMaker
from aios.web.login.redirect_login import RedirectLogin
from aios.web.login.sso.oidc_client import OidcClient
from aios.web.login.sso.sso_attempts import SsoAttempts
from aios.web.login.web_login import WebLogin

log = logging.getLogger(__name__)


class SsoLogin(RedirectLogin):
    """Single sign-on with OpenID Connect: a button per provider (Microsoft 365,
    Google, any OpenID provider), the authorization code flow with PKCE and a
    nonce, done by ai-os itself. The user is the one whose `web` account is the
    address in the provider's ID token: only an exact address, never a name. A
    provider with `create_users` makes that user on their first sign-in.

    Google's address counts only when Google says it is verified; any provider's
    when it does not say it is not. `domains` narrows it further."""

    mode = "sso"

    def __init__(
        self,
        users: ConsoleUsers,
        attempts: SsoAttempts,
        client: OidcClient,
        secrets: VariableResolver,
        maker: NewUserMaker,
        providers: list[SsoProvider] | None = None,
    ) -> None:
        self._users = users
        self._attempts = attempts
        self._client = client
        self._secrets = secrets
        self._maker = maker
        self._providers = {p.key: p for p in providers or []}

    def configured(self, auth: WebAuthConfig) -> WebLogin:
        return SsoLogin(
            self._users, self._attempts, self._client, self._secrets, self._maker, auth.providers
        )

    def page(self) -> dict[str, Any]:
        return {
            "providers": [
                {"id": p.key, "kind": p.kind, "label": p.name} for p in self._providers.values()
            ]
        }

    async def sign_in(self, request: LoginRequest) -> User:
        raise LoginRefused("sign in with one of the buttons")

    async def start(self, provider: str, redirect_uri: str) -> tuple[str, str]:
        p = self._provider(provider)
        meta = await self._client.discover(p.issuer_url())
        state, attempt = self._attempts.open(p.key, redirect_uri)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(attempt.verifier.encode()).digest())
        query = {
            "response_type": "code",
            "client_id": p.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(p.scopes),
            "state": state,
            "nonce": attempt.nonce,
            "code_challenge": challenge.decode().rstrip("="),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        if p.kind == "google" and len(p.domains) == 1:
            query["hd"] = p.domains[0]
        return f"{meta.authorization_endpoint}?{urlencode(query)}", state

    async def finish(self, state: str, code: str) -> User:
        attempt = self._attempts.take(state)
        if attempt is None:
            raise LoginRefused("this sign-in expired or was used already; start again")
        p = self._provider(attempt.provider)
        meta = await self._client.discover(p.issuer_url())
        token = await self._client.exchange(
            meta, code, attempt.redirect_uri, attempt.verifier, p.client_id, self._secret(p)
        )
        claims = await self._client.verify(meta, token, p.client_id, attempt.nonce)
        email = self._email(p, claims)
        user = self._users.by_address(email)
        if user is None and p.create_users and not self._users.has_address(email):
            name = claims.get("name")
            try:
                await self._maker.make(
                    email, name if isinstance(name, str) else None, p.default_role, p.name
                )
            except ValueError as exc:
                raise LoginRefused(f"{email} could not be added: {exc}") from exc
            user = self._users.by_address(email)
        if user is None:
            log.warning("sso: %s signed in at %s, but is no console user", email, p.name)
            raise LoginRefused(f"{email} is not a web account of anyone on this ai-os")
        return user

    def refusal(self, user: User) -> str | None:
        return None if self._users.may_sign_in(user) else "you have no web account"

    async def problem(self) -> str | None:
        for p in self._providers.values():
            if p.client_secret_variable and not self._secrets.value_of(p.client_secret_variable):
                return (
                    f"the Variable {p.client_secret_variable} ({p.name}'s client secret) is not set"
                )
            if p.create_users:
                reason = self._maker.refusal(p.default_role)
                if reason:
                    return f"{p.name}: {reason}"
            try:
                await self._client.discover(p.issuer_url())
            except LoginRefused as exc:
                return f"{p.name}: {exc}"
        return None

    def _provider(self, key: str) -> SsoProvider:
        p = self._providers.get(key)
        if p is None:
            raise LoginRefused("no such sign-in")
        return p

    def _secret(self, p: SsoProvider) -> str | None:
        if not p.client_secret_variable:
            return None
        secret = self._secrets.value_of(p.client_secret_variable)
        if not secret:
            raise LoginRefused(f"the Variable {p.client_secret_variable} is not set")
        return secret

    @staticmethod
    def _email(p: SsoProvider, claims: dict[str, Any]) -> str:
        email = claims.get(p.email_claim)
        if not email and p.kind == "microsoft":
            # Work accounts often carry no `email`; the sign-in name is the address,
            # and within one tenant its administrator sets it.
            email = claims.get("preferred_username")
        if not isinstance(email, str) or "@" not in email:
            raise LoginRefused(f"{p.name} did not say which address signed in")
        verified = claims.get("email_verified")
        if (
            verified is False
            or str(verified).casefold() == "false"
            or (p.kind == "google" and verified is not True)
        ):
            raise LoginRefused(f"{p.name} has not verified {email}")
        domain = email.rsplit("@", 1)[1].casefold()
        if p.domains and domain not in p.domains:
            raise LoginRefused(f"{email} is not in a domain this sign-in accepts")
        return email
