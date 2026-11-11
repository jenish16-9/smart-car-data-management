from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import AudioRecord


async def create(session: AsyncSession, **fields: object) -> AudioRecord:
    audio = AudioRecord(**fields)
    session.add(audio)
    await session.flush()
    return await get(session, audio.id)  # type: ignore[return-value]  # reload with vehicle


async def get(session: AsyncSession, audio_id: UUID) -> AudioRecord | None:
    result = await session.execute(
        select(AudioRecord).where(AudioRecord.id == audio_id).execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def list_records(
    session: AsyncSession,
    *,
    vehicle_ids: list[UUID] | None,
    vehicle_id: UUID | None,
    processing_status: str | None,
    limit: int,
    offset: int,
) -> list[AudioRecord]:
    query = select(AudioRecord).order_by(AudioRecord.uploaded_at.desc()).limit(limit).offset(offset)
    if vehicle_ids is not None:
        query = query.where(AudioRecord.vehicle_id.in_(vehicle_ids))
    if vehicle_id is not None:
        query = query.where(AudioRecord.vehicle_id == vehicle_id)
    if processing_status:
        query = query.where(AudioRecord.processing_status == processing_status)
    return list((await session.execute(query)).scalars().all())


async def set_status(session: AsyncSession, audio: AudioRecord, processing_status: str) -> AudioRecord:
    audio.processing_status = processing_status
    await session.flush()
    return audio


async def count(session: AsyncSession, vehicle_ids: list[UUID] | None) -> int:
    query = select(func.count()).select_from(AudioRecord)
    if vehicle_ids is not None:
        query = query.where(AudioRecord.vehicle_id.in_(vehicle_ids))
    return int((await session.execute(query)).scalar_one())
