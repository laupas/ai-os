from aios.transcription.whisper_transcriber import WhisperTranscriber
from tests.web.console import ALICE, BOB, Console


async def test_the_key_is_a_secret_variable_the_transcriber_reads_at_once(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AIOS_TRANSCRIBE_LANGUAGE", "de")
    async with Console(tmp_path) as c:
        transcriber = WhisperTranscriber(c.variable_resolver)
        assert not transcriber.is_available()
        response = await c.client.put(
            "/api/settings/voice",
            json={"values": {"OPENAI_API_KEY": " sk-x ", "AIOS_TRANSCRIBE_LANGUAGE": ""}},
            headers=c.headers(ALICE, write=True),
        )
        fields = {f["variable"]: f for f in (await response.json())["fields"]}
        assert fields["OPENAI_API_KEY"] == {
            "variable": "OPENAI_API_KEY",
            "secret": True,
            "source": "variable",
            "value": None,
        }
        assert fields["AIOS_TRANSCRIBE_LANGUAGE"]["source"] == "environment"
        assert fields["AIOS_TRANSCRIBE_LANGUAGE"]["value"] == "de"
        assert transcriber.is_available()
        stored = c.variables.get("OPENAI_API_KEY")
        assert stored is not None and stored.secret


async def test_a_check_without_a_key_says_so_and_voice_is_for_administrators(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    async with Console(tmp_path) as c:
        check = await c.client.post(
            "/api/settings/voice/check", json={}, headers=c.headers(ALICE, write=True)
        )
        assert await check.json() == {"ok": False, "detail": "no key is set"}
        bob = await c.client.put(
            "/api/settings/voice", json={"values": {}}, headers=c.headers(BOB, write=True)
        )
        assert bob.status == 403
