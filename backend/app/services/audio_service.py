"""Audio workflow: metadata -> storage URL -> classify -> MongoDB result -> alert.

1. Audio metadata is created (PostgreSQL `audio_records`).
2. The storage URL (object storage) is saved with it; no file bytes are stored in a database.
3. The audio classifier processes the file.
4. The classification result is saved in MongoDB (`audio_analysis_results`).
5. If confidence >= 0.80 and the class is not `normal`, a PostgreSQL alert is created.
6. The alert is then visible on the dashboard; admins acknowledge/resolve it, and
   every action is stored in `alert_actions` (see alert_service).
"""

import asyncio
import logging
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.audio import AudioRecord
from app.models.common import utcnow
from app.models.user import User
from app.repositories import analysis_repository, audio_repository, telemetry_repository, vehicle_repository
from app.schemas.audio import AnalysisOut, AudioCreate, AudioOut
from app.services import alert_service, audio_classifier, vehicle_service

logger = logging.getLogger(__name__)


async def _get_visible(session: AsyncSession, user: User, audio_id: UUID) -> AudioRecord:
    audio = await audio_repository.get(session, audio_id)
    if audio is None or not await vehicle_repository.user_can_access(session, user, audio.vehicle):
        raise NotFoundError("Audio record not found")
    return audio


async def _process(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, audio: AudioRecord
) -> tuple[dict | None, UUID | None]:
    """Run steps 3-5. Returns (analysis document, alert id)."""
    result = await asyncio.to_thread(audio_classifier.classify_audio, audio.storage_url)
    document = {
        "audio_record_id": str(audio.id),
        "vehicle_id": audio.vehicle.vehicle_code,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "predicted_class": result.event_type,
        "confidence": result.confidence,
        "processing_time_ms": result.processing_time_ms,
        "created_at": result.processing_timestamp,
    }
    await analysis_repository.insert_result(mongo, document)

    alert_id = None
    if alert_service.should_raise_alert(result.event_type, result.confidence):
        alert = await alert_service.create_from_classification(
            session, vehicle_id=audio.vehicle_id, audio_record_id=audio.id, analysis=document
        )
        alert_id = alert.id
    return document, alert_id


async def create_audio(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, payload: AudioCreate
) -> AudioOut:
    vehicle = await vehicle_service.get_accessible(session, user, payload.vehicle_id)
    audio = await audio_repository.create(
        session,
        vehicle_id=vehicle.id,
        storage_url=payload.storage_url,
        file_name=payload.file_name,
        file_type=payload.file_type,
        duration_seconds=payload.duration_seconds,
        file_size=payload.file_size,
        processing_status="processing",
    )
    await session.commit()  # metadata + URL are durable before any processing starts
    audio_id = audio.id

    try:
        document, alert_id = await _process(session, mongo, audio)
        audio.processing_status = "completed"
        await session.commit()
    except Exception:  # classifier or MongoDB failure must not lose the upload record
        logger.exception("Audio processing failed for %s", audio_id)
        await session.rollback()  # expires loaded objects, so reload before updating
        failed = await audio_repository.get(session, audio_id)
        await audio_repository.set_status(session, failed, "failed")
        await session.commit()
        return AudioOut.from_model(failed)

    await telemetry_repository.insert_device_log(
        mongo,
        vehicle_code=vehicle.vehicle_code,
        event_type="audio_processed",
        message=f"Audio {audio.file_name} classified as {document['predicted_class']}",
        timestamp=utcnow(),
    )
    return AudioOut.from_model(audio, analysis=AnalysisOut.from_document(document), alert_id=alert_id)


async def list_audio(
    session: AsyncSession,
    mongo: AsyncIOMotorDatabase,
    user: User,
    *,
    vehicle: str | None,
    processing_status: str | None,
    limit: int,
    offset: int,
) -> list[AudioOut]:
    scope = await vehicle_repository.accessible_scope(session, user)
    vehicle_id = (await vehicle_service.get_accessible(session, user, vehicle)).id if vehicle else None
    records = await audio_repository.list_records(
        session,
        vehicle_ids=None if scope is None else [v.id for v in scope],
        vehicle_id=vehicle_id,
        processing_status=processing_status,
        limit=limit,
        offset=offset,
    )
    analyses = await analysis_repository.get_for_audios(mongo, [str(record.id) for record in records])
    return [
        AudioOut.from_model(record, analysis=AnalysisOut.from_document(analyses[str(record.id)]))
        if str(record.id) in analyses
        else AudioOut.from_model(record)
        for record in records
    ]


async def get_audio(session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, audio_id: UUID) -> AudioOut:
    audio = await _get_visible(session, user, audio_id)
    document = await analysis_repository.get_for_audio(mongo, str(audio.id))
    return AudioOut.from_model(audio, analysis=AnalysisOut.from_document(document) if document else None)


async def update_status(session: AsyncSession, user: User, audio_id: UUID, processing_status: str) -> AudioOut:
    audio = await _get_visible(session, user, audio_id)
    await audio_repository.set_status(session, audio, processing_status)
    await session.commit()
    return AudioOut.from_model(audio)
