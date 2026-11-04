from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
from aiohttp.test_utils import make_mocked_request
from cryptography.hazmat.primitives.asymmetric import rsa

from aios.web.jwt_header_identity import JwtHeaderIdentity

HEADER = "Cf-Access-Jwt-Assertion"

TEAM = "team.cloudflareaccess.com"
AUD = "the-aud"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _identity() -> JwtHeaderIdentity:
    identity = JwtHeaderIdentity.cloudflare(TEAM, AUD)
    identity._keys = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=KEY.public_key())
    )
    return identity


def _token(key=KEY, **overrides: object) -> str:  # type: ignore[no-untyped-def]
    claims = {
        "email": "alice@example.com",
        "aud": [AUD],
        "iss": f"https://{TEAM}",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="RS256")


def _request(token: str | None):  # type: ignore[no-untyped-def]
    return make_mocked_request("GET", "/", headers={HEADER: token} if token else {})


async def test_a_valid_token_gives_its_email() -> None:
    assert await _identity().email_of(_request(_token())) == "alice@example.com"


async def test_no_token_gives_nobody() -> None:
    assert await _identity().email_of(_request(None)) is None


async def test_a_token_for_another_application_is_refused() -> None:
    assert await _identity().email_of(_request(_token(aud=["other"]))) is None


async def test_a_token_from_another_team_is_refused() -> None:
    assert await _identity().email_of(_request(_token(iss="https://evil.example"))) is None


async def test_an_expired_token_is_refused() -> None:
    expired = _token(exp=datetime.now(UTC) - timedelta(minutes=1))
    assert await _identity().email_of(_request(expired)) is None


async def test_a_token_signed_with_another_key_is_refused() -> None:
    assert await _identity().email_of(_request(_token(key=OTHER_KEY))) is None
