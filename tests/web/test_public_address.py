from aiohttp.test_utils import make_mocked_request

from aios.web.public_address import PublicAddress


def test_cookies_are_secure_when_the_console_is_reached_over_https() -> None:
    plain = make_mocked_request("GET", "/", headers={"Host": "ai-os.example.com"})
    proxied = make_mocked_request(
        "GET", "/", headers={"Host": "ai-os.example.com", "X-Forwarded-Proto": "https"}
    )
    assert PublicAddress("https://ai-os.example.com").secure(plain)
    assert not PublicAddress("http://192.168.1.5:8080").secure(proxied)
    assert PublicAddress(None).secure(proxied)
    assert not PublicAddress(None).secure(plain)
