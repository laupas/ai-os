import pytest
from aiohttp.test_utils import make_mocked_request
from pydantic import ValidationError

from aios.config.web_auth_config import WebAuthConfig
from aios.config.web_config import WebConfig
from aios.web.fixed_identity import FixedIdentity
from aios.web.jwt_header_identity import JwtHeaderIdentity
from aios.web.trusted_header_identity import TrustedHeaderIdentity
from aios.web.web_identity_factory import WebIdentityFactory


def _request(remote: str, **headers: str):  # type: ignore[no-untyped-def]
    request = make_mocked_request("GET", "/api/me", headers=headers)
    request._transport_peername = (remote, 1234)  # type: ignore[attr-defined]
    return request.clone(remote=remote)


async def test_a_plain_header_is_believed_only_from_the_proxy() -> None:
    identity = TrustedHeaderIdentity("Remote-Email", ["172.20.0.0/16"], "X-Aios-Proxy-Secret", None)
    assert (
        await identity.email_of(_request("172.20.0.5", **{"Remote-Email": "a@example.com"}))
        == "a@example.com"
    )
    assert (
        await identity.email_of(_request("10.0.0.9", **{"Remote-Email": "a@example.com"})) is None
    )


async def test_a_plain_header_can_also_be_bound_to_a_shared_secret() -> None:
    identity = TrustedHeaderIdentity("Remote-Email", [], "X-Aios-Proxy-Secret", "s3cret")
    good = _request(
        "10.0.0.9", **{"Remote-Email": "a@example.com", "X-Aios-Proxy-Secret": "s3cret"}
    )
    forged = _request(
        "10.0.0.9", **{"Remote-Email": "a@example.com", "X-Aios-Proxy-Secret": "guess"}
    )
    assert await identity.email_of(good) == "a@example.com"
    assert await identity.email_of(forged) is None


def test_a_plain_header_without_any_check_is_refused_by_the_config() -> None:
    with pytest.raises(ValidationError):
        WebAuthConfig(mode="header", header="Remote-Email")
    with pytest.raises(ValidationError):
        WebAuthConfig(mode="jwt", header="Authorization")  # no keys to check it with


def test_the_older_access_settings_still_mean_cloudflare(monkeypatch) -> None:
    older = WebConfig(access_team_domain="x.cloudflareaccess.com", access_aud="aud")
    assert isinstance(WebIdentityFactory.create(older), JwtHeaderIdentity)
    assert isinstance(WebIdentityFactory.create(WebConfig()), FixedIdentity)  # refuses all
    monkeypatch.setenv("PROXY_SECRET", "s")
    header = WebConfig(
        auth=WebAuthConfig(mode="header", header="Remote-Email", secret_env="PROXY_SECRET")
    )
    assert isinstance(WebIdentityFactory.create(header), TrustedHeaderIdentity)
    monkeypatch.delenv("PROXY_SECRET")
    with pytest.raises(RuntimeError):
        WebIdentityFactory.create(header)  # a named secret that is not set fails loudly


async def test_an_unconfigured_console_lets_nobody_in() -> None:
    assert await WebIdentityFactory.create(WebConfig()).email_of(_request("127.0.0.1")) is None
