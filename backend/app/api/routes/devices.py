from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_auth_context, get_current_user, optional_bearer
from app.core.errors import UnprocessableError
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.device import (
    DeviceConfigurationUpdate,
    DeviceControlState,
    DeviceControlsUpdate,
    DeviceCreate,
    DeviceOut,
    DeviceRegisteredOut,
    DeviceStatusValue,
    DeviceUpdate,
    HeartbeatCreate,
    HeartbeatOut,
    SimulatedAudioEvent,
)
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("", response_model=DeviceRegisteredOut, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> DeviceRegisteredOut:
    """Register an IoT device (administrators). Starts as PENDING; the returned device key is shown once."""
    device, key = await device_service.register(session, user, payload)
    return DeviceRegisteredOut(**device.model_dump(), device_key=key)


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    vehicle_id: str | None = Query(None, description="Vehicle UUID or vehicle_code"),
    status_filter: DeviceStatusValue | None = Query(None, alias="status"),
    include_retired: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DeviceOut]:
    return await device_service.list_devices(
        session,
        user,
        vehicle=vehicle_id,
        status=status_filter,
        include_retired=include_retired,
        limit=limit,
        offset=offset,
    )


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    return await device_service.get_detail(session, user, device_id)


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: str,
    payload: DeviceUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceOut:
    return await device_service.update(session, user, device_id, payload)


@router.put("/{device_id}/configuration", response_model=DeviceOut)
async def update_configuration(
    device_id: str,
    payload: DeviceConfigurationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceOut:
    return await device_service.update_configuration(session, user, device_id, payload)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_device(
    device_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> Response:
    """Soft removal: the device becomes RETIRED (history is kept). It is never physically deleted."""
    await device_service.retire(session, user, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{device_id}/rotate-key", response_model=dict[str, str])
async def rotate_device_key(
    device_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    return {"device_key": await device_service.rotate_key(session, user, device_id)}


@router.get("/{device_id}/status", response_model=DeviceControlState)
async def get_status(
    device_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> DeviceControlState:
    return DeviceControlState.model_validate(await device_service.controls(session, user, device_id))


async def _apply(
    device_id: str, changes: DeviceControlsUpdate, user: User, session: AsyncSession, mongo: AsyncIOMotorDatabase
) -> DeviceControlState:
    device = await device_service.update_controls(session, mongo, user, device_id, changes)
    return DeviceControlState.model_validate(device)


@router.patch("/{device_id}/status", response_model=DeviceControlState)
async def update_status(
    device_id: str,
    payload: DeviceControlsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> DeviceControlState:
    """Set monitoring mode, audio capture and recording on this device."""
    return await _apply(device_id, payload, user, session, mongo)


def _command(path: str, changes: DeviceControlsUpdate, summary: str) -> None:
    async def handler(
        device_id: str,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
        mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    ) -> DeviceControlState:
        return await _apply(device_id, changes, user, session, mongo)

    handler.__doc__ = summary
    handler.__name__ = path.strip("/").replace("/", "_")
    router.add_api_route(f"/{{device_id}}/{path}", handler, methods=["POST"], response_model=DeviceControlState)


_command("recording/start", DeviceControlsUpdate(recording=True), "Start recording on this device.")
_command("recording/stop", DeviceControlsUpdate(recording=False), "Stop recording on this device.")
_command("monitoring/pause", DeviceControlsUpdate(monitoring_mode="paused"), "Pause monitoring (stops recording).")
_command("monitoring/resume", DeviceControlsUpdate(monitoring_mode="continuous"), "Resume continuous monitoring.")


@router.post("/{device_id}/heartbeat", response_model=DeviceOut)
async def post_heartbeat(
    device_id: str,
    payload: HeartbeatCreate,
    x_device_key: str | None = Header(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> DeviceOut:
    """Record a heartbeat. Authenticate with `X-Device-Key` (device) or a Bearer token (signed-in user)."""
    user = None
    if x_device_key is None:
        user = (await get_auth_context(credentials, session)).user
    return await device_service.heartbeat(session, mongo, device_id, payload, user=user, device_key=x_device_key)


@router.get("/{device_id}/heartbeats", response_model=list[HeartbeatOut])
async def list_heartbeats(
    device_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[HeartbeatOut]:
    beats = await device_service.list_heartbeats(
        session, user, device_id, start=start, end=end, limit=limit, offset=offset
    )
    return [HeartbeatOut.from_model(beat) for beat in beats]


@router.post("/{device_id}/classify-audio", response_model=SimulatedAudioEvent)
async def classify_audio(
    device_id: str,
    audio: UploadFile = File(...),
    location: str | None = Form(default=None, max_length=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> SimulatedAudioEvent:
    filename = (audio.filename or "").lower()
    if not filename.endswith(".wav"):
        raise UnprocessableError("Only .wav audio files are supported")
    audio_bytes = await audio.read(settings.audio_upload_max_bytes + 1)
    await audio.close()
    if not audio_bytes:
        raise UnprocessableError("Audio file cannot be empty")
    if len(audio_bytes) > settings.audio_upload_max_bytes:
        raise UnprocessableError(f"Audio file exceeds the {settings.audio_upload_max_bytes // 1_000_000} MB limit")
    if not audio_bytes.startswith(b"RIFF") or audio_bytes[8:12] != b"WAVE":
        raise UnprocessableError("Audio file must be a valid WAV container")
    return await device_service.classify_simulated_audio(
        session, mongo, user, device_id, audio_bytes, location=location or None
    )
