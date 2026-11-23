from tests.web.console import ALICE, BOB, Console

SCHEDULE = {
    "name": "brief",
    "prompt": "brief me",
    "cron": ["0 7 * * 1-5"],
    "user_id": "alice",
}


async def _create(c: Console, **overrides: object):  # type: ignore[no-untyped-def]
    return await c.client.post(
        "/api/triggers", json={**SCHEDULE, **overrides}, headers=c.headers(ALICE, write=True)
    )


async def test_a_trigger_can_be_created(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await _create(c)
        assert response.status == 201
        trigger = c.triggers.get((await response.json())["id"])
        assert trigger is not None and trigger.cron == ["0 7 * * 1-5"]
        assert trigger.created_at is not None and trigger.last_fired_at is None


async def test_a_bad_trigger_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        assert (await _create(c, cron=["every morning"])).status == 400
        assert (await _create(c, timezone="Mars/Olympus")).status == 400
        assert (await _create(c, user_id="nobody")).status == 400
        assert (await _create(c, cron=[])).status == 400  # neither cron nor once_at
        assert c.triggers.all() == []


async def test_changing_the_time_counts_from_now(tmp_path) -> None:
    async with Console(tmp_path) as c:
        trigger_id = (await (await _create(c)).json())["id"]

        response = await c.client.put(
            f"/api/triggers/{trigger_id}",
            json={**SCHEDULE, "cron": ["0 6 * * 1-5"], "prompt": "brief me early"},
            headers=c.headers(ALICE, write=True),
        )

        assert response.status == 200
        trigger = c.triggers.get(trigger_id)
        assert trigger is not None
        assert trigger.prompt == "brief me early"
        assert trigger.last_fired_at is not None


async def test_changing_only_the_prompt_keeps_when_it_last_fired(tmp_path) -> None:
    async with Console(tmp_path) as c:
        trigger_id = (await (await _create(c)).json())["id"]

        await c.client.put(
            f"/api/triggers/{trigger_id}",
            json={**SCHEDULE, "prompt": "brief me well"},
            headers=c.headers(ALICE, write=True),
        )

        trigger = c.triggers.get(trigger_id)
        assert trigger is not None and trigger.last_fired_at is None


async def test_turning_a_trigger_into_a_one_off(tmp_path) -> None:
    async with Console(tmp_path) as c:
        trigger_id = (await (await _create(c)).json())["id"]

        response = await c.client.put(
            f"/api/triggers/{trigger_id}",
            json={**SCHEDULE, "cron": [], "once_at": "2099-01-01T07:00:00+01:00"},
            headers=c.headers(ALICE, write=True),
        )

        assert response.status == 200
        trigger = c.triggers.get(trigger_id)
        assert trigger is not None and trigger.cron == [] and trigger.last_fired_at is None


async def test_triggers_are_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.post(
            "/api/triggers", json=SCHEDULE, headers=c.headers(BOB, write=True)
        )
        assert response.status == 403
