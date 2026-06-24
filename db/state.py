from sqlalchemy import select

from db.models import AppState

VRC_AUTH_COOKIE = "vrc_auth_cookie"
VRC_TWOFACTOR_COOKIE = "vrc_twofactor_cookie"
VRC_PENDING_COOKIE = "vrc_pending_cookie"
COLLECT_CURSOR = "collect_cursor"
LAST_COLLECT_AT = "last_collect_at"
LAST_STATUS = "last_status"


async def get_state(session, key: str) -> str | None:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_state(session, key: str, value: str | None) -> None:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(AppState(key=key, value=value))
    await session.commit()


async def delete_state(session, key: str) -> None:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.commit()
