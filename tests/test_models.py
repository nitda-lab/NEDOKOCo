from sqlalchemy import select

from db.models import AppState


async def test_app_state_insert_and_read(session):
    session.add(AppState(key="foo", value="bar"))
    await session.commit()

    result = await session.execute(select(AppState).where(AppState.key == "foo"))
    row = result.scalar_one()
    assert row.value == "bar"
