from db.state import delete_state, get_state, set_state


async def test_set_get_roundtrip(session):
    assert await get_state(session, "k") is None
    await set_state(session, "k", "v1")
    assert await get_state(session, "k") == "v1"


async def test_set_upsert_overwrites(session):
    await set_state(session, "k", "v1")
    await set_state(session, "k", "v2")
    assert await get_state(session, "k") == "v2"


async def test_delete(session):
    await set_state(session, "k", "v")
    await delete_state(session, "k")
    assert await get_state(session, "k") is None
