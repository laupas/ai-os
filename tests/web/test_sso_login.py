from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from aios.config.sso_provider import SsoProvider
from aios.config.web_auth_config import WebAuthConfig
from aios.web.routes.login_routes import STATE_COOKIE
from tests.web.console import ALICE, Console
from tests.web.fake_oidc_provider import CLIENT_ID, CLIENT_SECRET, FakeOidcProvider

W = {"X-Aios": "1"}
SECRET_VAR = "AIOS_TEST_SSO_SECRET"


def _auth(issuer: str, **provider: object) -> WebAuthConfig:
    return WebAuthConfig(
        mode="sso",
        providers=[
            SsoProvider(
                kind="oidc",
                issuer=issuer,
                client_id=CLIENT_ID,
                client_secret_variable=SECRET_VAR,
                **provider,
            )
        ],
    )


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_VAR, CLIENT_SECRET)


async def _me(c: Console) -> int:
    return (await c.client.get("/api/conversations")).status


async def _sign_in(c: Console, idp: FakeOidcProvider) -> str:
    """Clicks the button, signs in at the provider; returns where ai-os sends the
    browser in the end."""
    start = await c.client.get("/api/login/sso/start/oidc", allow_redirects=False)
    assert start.status == 302
    query = idp.authorize(start.headers["Location"])
    back = await c.client.get(
        "/api/login/sso/callback",
        params={"state": query["state"], "code": "the-code"},
        allow_redirects=False,
    )
    assert back.status == 302
    return back.headers["Location"]


def _error(location: str) -> str:
    return parse_qs(urlsplit(location).query).get("login_error", [""])[0]


async def test_the_login_page_offers_a_button_per_provider(tmp_path) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        page = await (await c.client.get("/api/login")).json()
        assert page == {
            "mode": "sso",
            "providers": [{"id": "oidc", "kind": "oidc", "label": "single sign-on"}],
        }


async def test_signing_in_at_the_provider_signs_in_the_user_with_that_web_account(
    tmp_path,
) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        idp.claims = {"email": ALICE.upper(), "email_verified": True}
        start = await c.client.get("/api/login/sso/start/oidc", allow_redirects=False)
        query = idp.authorize(start.headers["Location"])
        assert query["client_id"] == CLIENT_ID
        assert query["code_challenge_method"] == "S256"
        assert query["redirect_uri"].endswith("/api/login/sso/callback")
        assert query["scope"] == "openid email profile"
        back = await c.client.get(
            "/api/login/sso/callback",
            params={"state": query["state"], "code": "the-code"},
            allow_redirects=False,
        )
        assert back.headers["Location"] == "/"
        assert await _me(c) == 200
        you = await (await c.client.get("/api/settings/web-auth")).json()
        assert you["you"] == ALICE


async def test_an_address_nobody_has_as_web_account_is_refused(tmp_path) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        idp.claims = {"email": "mallory@example.com"}
        assert "not a web account" in _error(await _sign_in(c, idp))
        assert await _me(c) == 403


async def test_an_address_the_provider_has_not_verified_is_refused(tmp_path) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        idp.claims = {"email": ALICE, "email_verified": False}
        assert "not verified" in _error(await _sign_in(c, idp))
        assert await _me(c) == 403


async def test_domains_narrow_who_gets_in(tmp_path) -> None:
    async with FakeOidcProvider() as idp:
        auth = _auth(idp.issuer, domains=["@Other.org"])
        assert auth.providers[0].domains == ["other.org"]
        async with Console(tmp_path, auth=auth) as c:
            idp.claims = {"email": ALICE}
            assert "not in a domain" in _error(await _sign_in(c, idp))
            assert await _me(c) == 403


async def test_a_sign_in_finishes_only_in_the_browser_that_started_it(tmp_path) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        idp.claims = {"email": ALICE}
        start = await c.client.get("/api/login/sso/start/oidc", allow_redirects=False)
        query = idp.authorize(start.headers["Location"])
        c.client.session.cookie_jar.clear()
        back = await c.client.get(
            "/api/login/sso/callback",
            params={"state": query["state"], "code": "the-code"},
            allow_redirects=False,
        )
        assert "another browser" in _error(back.headers["Location"])
        assert await _me(c) == 403


async def test_a_state_works_once(tmp_path) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        idp.claims = {"email": ALICE}
        start = await c.client.get("/api/login/sso/start/oidc", allow_redirects=False)
        query = idp.authorize(start.headers["Location"])
        params = {"state": query["state"], "code": "the-code"}
        first = await c.client.get("/api/login/sso/callback", params=params, allow_redirects=False)
        assert first.headers["Location"] == "/"
        await c.client.post("/api/logout", headers=W)
        c.client.session.cookie_jar.update_cookies({STATE_COOKIE: query["state"]})
        idp.authorize(start.headers["Location"])
        again = await c.client.get("/api/login/sso/callback", params=params, allow_redirects=False)
        assert "expired or was used" in _error(again.headers["Location"])
        assert await _me(c) == 403


async def test_a_provider_error_is_shown_on_the_login_page(tmp_path) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        back = await c.client.get(
            "/api/login/sso/callback",
            params={"error": "access_denied", "error_description": "The user said no"},
            allow_redirects=False,
        )
        assert _error(back.headers["Location"]) == "The user said no"


async def test_a_wrong_client_secret_does_not_sign_in(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(SECRET_VAR, "wrong")
    async with FakeOidcProvider() as idp, Console(tmp_path, auth=_auth(idp.issuer)) as c:
        idp.claims = {"email": ALICE}
        assert "refused the sign-in" in _error(await _sign_in(c, idp))
        assert await _me(c) == 403


async def test_settings_refuse_sso_while_its_client_secret_is_not_set(
    tmp_path, monkeypatch
) -> None:
    async with FakeOidcProvider() as idp, Console(tmp_path) as c:
        body = {"auth": _auth(idp.issuer).model_dump(exclude_defaults=True)}
        headers = c.headers(ALICE, write=True)
        ok = await c.client.post("/api/settings/web-auth/check", json=body, headers=headers)
        assert (await ok.json())["ok"] is True
        monkeypatch.delenv(SECRET_VAR)
        save = await c.client.put("/api/settings/web-auth", json=body, headers=headers)
        assert save.status == 409
        assert SECRET_VAR in await save.text()


def test_microsoft_needs_a_tenant_of_its_own() -> None:
    with pytest.raises(ValidationError, match="any organisation"):
        SsoProvider(kind="microsoft", tenant="common", client_id="x", client_secret_variable="S")
    with pytest.raises(ValidationError, match="needs tenant"):
        SsoProvider(kind="microsoft", client_id="x", client_secret_variable="S")
    p = SsoProvider(
        kind="microsoft", tenant="example.com", client_id="x", client_secret_variable="S"
    )
    assert p.issuer_url() == "https://login.microsoftonline.com/example.com/v2.0"


def test_google_and_microsoft_need_a_client_secret_and_oidc_an_https_issuer() -> None:
    with pytest.raises(ValidationError, match="client_secret_variable"):
        SsoProvider(kind="google", client_id="x")
    with pytest.raises(ValidationError, match="https"):
        SsoProvider(kind="oidc", issuer="http://auth.example.com", client_id="x")


def test_two_providers_of_one_kind_need_ids() -> None:
    google = SsoProvider(kind="google", client_id="x", client_secret_variable="S")
    with pytest.raises(ValidationError, match="id each"):
        WebAuthConfig(mode="sso", providers=[google, google])
    WebAuthConfig(mode="sso", providers=[google, google.model_copy(update={"id": "work"})])
