from sqlalchemy import select

from db.models import AppState


async def test_app_state_insert_and_read(session):
    session.add(AppState(key="foo", value="bar"))
    await session.commit()

    result = await session.execute(select(AppState).where(AppState.key == "foo"))
    row = result.scalar_one()
    assert row.value == "bar"


async def test_world_has_metric_columns(session):
    from datetime import datetime

    from db.models import World

    w = World(
        world_id="wm1", name="n", author_name="a",
        vrc_url="https://vrchat.com/home/world/wm1",
        vrc_updated_at=datetime(2026, 6, 1), favorites=123, popularity=45,
    )
    session.add(w)
    await session.commit()

    row = (await session.execute(select(World).where(World.world_id == "wm1"))).scalar_one()
    assert row.favorites == 123
    assert row.popularity == 45
    assert row.vrc_updated_at.year == 2026
