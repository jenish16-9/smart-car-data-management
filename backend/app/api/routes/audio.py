from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.audio import AudioCreate, AudioOut, AudioStatusUpdate, ProcessingStatus
from app.services import audio_service

router = APIRouter(prefix="/audio", tags=["Audio"])


@router.post("", response_model=AudioOut, status_code=status.HTTP_201_CREATED)
async def create_audio(
    payload: AudioCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AudioOut:
    """Register audio metadata + storage URL, classify it, and raise an alert if warranted."""
    return await audio_service.create_audio(session, mongo, user, payload)


@router.get("", response_model=list[AudioOut])
async def list_audio(
    vehicle_id: str | None = None,
    processing_status: ProcessingStatus | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> list[AudioOut]:
    return await audio_service.list_audio(
        session, mongo, user, vehicle=vehicle_id, processing_status=processing_status, limit=limit, offset=offset
    )


@router.get("/{audio_id}", response_model=AudioOut)
async def get_audio(
    audio_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AudioOut:
    return await audio_service.get_audio(session, mongo, user, audio_id)


@router.patch("/{audio_id}/status", response_model=AudioOut)
async def update_audio_status(
    audio_id: UUID,
    payload: AudioStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AudioOut:
    return await audio_service.update_status(session, user, audio_id, payload.processing_status)
