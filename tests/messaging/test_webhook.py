import json

import pytest
from pydantic import ValidationError

from aios.entities.variables.variable import Variable
from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.messaging.webhook.webhook_poster import WebhookPoster
from aios.messaging.webhook.webhook_template import WebhookTemplate
from aios.messaging.webhook.webhook_template_error import WebhookTemplateError
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.variables.secret_box import SecretBox
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from tests.fakes.fake_clock import FakeClock
from tests.messaging.webhook_target import WebhookTarget

FIELDS = {
    "type": "object",
    "properties": {"text": {"type": "string"}, "level": {"type": "integer"}},
    "required": ["text"],
}


async def _template(tmp_path) -> WebhookTemplate:  # type: ignore[no-untyped-def]
    variables: Collection[Variable] = Collection(
        CollectionDefinition(name="variables", entity=Variable), InMemoryDocumentStore()
    )
    box = SecretBox(None, tmp_path / "secrets.key")
    await VariableCatalog(variables, box, FakeClock()).save(
        "HOOK_TOKEN", "s3cret", True, False, "", "Alice"
    )
    return WebhookTemplate(VariableResolver(variables, box, tmp_path / "files"))


def _destination(**overrides: object) -> WebhookDestination:
    return WebhookDestination.model_validate(
        {
            "id": "alerts",
            "url": "https://hooks.example.com/{{text}}?k=1",
            "headers": {"Authorization": "Bearer ${HOOK_TOKEN}", "X-Note": "{{text}}"},
            "fields": FIELDS,
            "body": {"msg": "Alert: {{text}}", "level": "{{level}}", "tags": ["{{text}}"]},
            **overrides,
        }
    )


async def test_the_templates_are_filled_with_fields_and_variables(tmp_path) -> None:
    call = (await _template(tmp_path)).render(_destination(), {"text": "a b\nc", "level": 3})
    assert call.url == "https://hooks.example.com/a%20b%0Ac?k=1"
    assert call.headers == {"Authorization": "Bearer s3cret", "X-Note": "a b c"}
    assert call.json_body == {"msg": "Alert: a b\nc", "level": 3, "tags": ["a b\nc"]}


async def test_a_field_cannot_pull_in_a_variable(tmp_path) -> None:
    call = (await _template(tmp_path)).render(_destination(), {"text": "${HOOK_TOKEN}"})
    assert "s3cret" not in json.dumps(call.json_body)
    assert call.json_body["msg"] == "Alert: ${HOOK_TOKEN}"
    assert call.json_body["level"] is None  # optional and not given


async def test_a_text_body_is_sent_as_written(tmp_path) -> None:
    call = (await _template(tmp_path)).render(
        _destination(body="level={{level}}&text={{text}}"), {"text": "hi", "level": 2}
    )
    assert call.text_body == "level=2&text=hi" and call.json_body is None


async def test_an_unset_variable_is_named(tmp_path) -> None:
    template = await _template(tmp_path)
    destination = _destination(headers={"X-Key": "${NOPE}"})
    assert template.missing(destination) == ["NOPE"]
    with pytest.raises(WebhookTemplateError, match="NOPE"):
        template.render(destination, {"text": "x"})


def test_a_destination_must_declare_what_its_templates_use() -> None:
    with pytest.raises(ValidationError, match="not declared"):
        _destination(body={"msg": "{{other}}"})
    with pytest.raises(ValidationError, match="GET sends no body"):
        _destination(method="GET")
    with pytest.raises(ValidationError, match="type"):
        _destination(fields={"properties": {}})
    with pytest.raises(ValidationError, match="http"):
        _destination(url="ftp://x")
    assert _destination(method="GET", body=None).body is None


async def test_the_poster_sends_the_request_and_reports_the_answer(tmp_path) -> None:
    target = WebhookTarget()
    await target.server.start_server()
    try:
        poster = WebhookPoster(await _template(tmp_path), enabled=True)
        destination = _destination(url=target.url + "/hook/{{text}}")
        result = await poster.post(destination, {"text": "hi", "level": 1})
        assert result.ok and result.detail == "200 received"
        [request] = target.requests
        assert request["method"] == "POST" and request["path"] == "/hook/hi"
        assert request["headers"]["Authorization"] == "Bearer s3cret"
        assert json.loads(request["body"]) == {"msg": "Alert: hi", "level": 1, "tags": ["hi"]}

        target.status = 500
        failed = await poster.post(destination, {"text": "hi"})
        assert not failed.ok and failed.detail.startswith("500")
    finally:
        await target.server.close()


async def test_fields_that_do_not_fit_are_not_sent(tmp_path) -> None:
    poster = WebhookPoster(await _template(tmp_path), enabled=True)
    result = await poster.post(_destination(), {"level": "high"})
    assert not result.ok
    assert "'text' is a required property" in result.detail and "level" in result.detail
