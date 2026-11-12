from typing import Any
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.alert import Alert
from app.models.common import utcnow
from app.models.user import User
from app.repositories import alert_repository, analysis_repository, audio_repository, vehicle_repository
from app.schemas.alert import AlertActionOut, AlertCreate, AlertDetail, AlertOut
from app.schemas.audio import AnalysisOut
from app.services import vehicle_service

ALERT_CONFIDENCE_THRESHOLD = 0.80
SEVERITY_BY_CLASS = {
    "crash": "critical",
    "gunshot": "critical",
    "glass_breaking": "high",
    "screaming": "high",
    "emergency_vehicle_siren": "high",
    "tire_skidding": "high",
    "abnormal_engine_noise": "medium",
}


def should_raise_alert(predicted_class: str, confidence: float) -> bool:
    """Workflow rule: confidence >= 0.80 and the class is not 'normal'."""
    return predicted_class != "normal" and confidence >= ALERT_CONFIDENCE_THRESHOLD


async def create_from_classification(
    session: AsyncSession, *, vehicle_id: UUID, audio_record_id: UUID, analysis: dict[str, Any]
) -> Alert:
    """Create the alert for a positive classification (caller commits)."""
    predicted = analysis["predicted_class"]
    alert = await alert_repository.create(
        session,
        vehicle_id=vehicle_id,
        audio_record_id=audio_record_id,
        event_type=predicted,
        severity=SEVERITY_BY_CLASS.get(predicted, "medium"),
        confidence=analysis["confidence"],
        status="open",
        detected_at=utcnow(),
    )
    await alert_repository.add_action(
        session,
        alert_id=alert.id,
        user_id=None,
        action_type="created",
        notes="Created automatically by audio classification",
    )
    return alert


async def create_from_simulation(
    session: AsyncSession,
    *,
    vehicle_id: UUID,
    event_id: UUID,
    analysis: dict[str, Any],
    location: str | None,
) -> Alert:
    predicted = analysis["predicted_class"]
    alert = await alert_repository.create(
        session,
        vehicle_id=vehicle_id,
        audio_record_id=None,
        event_type=predicted,
        severity=SEVERITY_BY_CLASS.get(predicted, "medium"),
        confidence=analysis["confidence"],
        status="open",
        location=location,
        is_simulation=True,
        simulation_event_id=str(event_id),
        detected_at=utcnow(),
    )
    await alert_repository.add_action(
        session,
        alert_id=alert.id,
        user_id=None,
        action_type="created",
        notes="Created by a simulated device audio event",
    )
    return alert


async def create_alert(session: AsyncSession, user: User, payload: AlertCreate) -> AlertOut:
    vehicle = await vehicle_service.get_accessible(session, user, payload.vehicle_id)
    if payload.audio_record_id is not None:
        audio = await audio_repository.get(session, payload.audio_record_id)
        if audio is None or audio.vehicle_id != vehicle.id:
            raise NotFoundError("Audio record not found for this vehicle")
    alert = await alert_repository.create(
        session,
        vehicle_id=vehicle.id,
        audio_record_id=payload.audio_record_id,
        event_type=payload.event_type,
        severity=payload.severity,
        confidence=payload.confidence,
        status="open",
        location=payload.location,
        detected_at=payload.detected_at or utcnow(),
    )
    await alert_repository.add_action(
        session, alert_id=alert.id, user_id=user.id, action_type="created", notes="Created manually"
    )
    await session.commit()
    return AlertOut.from_model(alert)


async def _get_visible(session: AsyncSession, user: User, alert_id: UUID) -> Alert:
    alert = await alert_repository.get(session, alert_id)
    if alert is None or not await vehicle_repository.user_can_access(session, user, alert.vehicle):
        raise NotFoundError("Alert not found")
    return alert


async def list_alerts(
    session: AsyncSession,
    user: User,
    *,
    vehicle: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> list[AlertOut]:
    scope = await vehicle_repository.accessible_scope(session, user)
    vehicle_id = (await vehicle_service.get_accessible(session, user, vehicle)).id if vehicle else None
    alerts = await alert_repository.list_alerts(
        session,
        vehicle_ids=None if scope is None else [v.id for v in scope],
        vehicle_id=vehicle_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [AlertOut.from_model(alert) for alert in alerts]


async def get_detail(session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, alert_id: UUID) -> AlertDetail:
    alert = await _get_visible(session, user, alert_id)
    actions = await alert_repository.list_actions(session, alert.id)
    if alert.audio_record_id:
        document = await analysis_repository.get_for_audio(mongo, str(alert.audio_record_id))
    elif alert.simulation_event_id:
        document = await analysis_repository.get_for_event(mongo, alert.simulation_event_id)
    else:
        document = None
    return AlertDetail(
        **AlertOut.from_model(alert).model_dump(),
        actions=[AlertActionOut.from_model(action) for action in actions],
        analysis=AnalysisOut.from_document(document) if document else None,
    )


async def acknowledge(session: AsyncSession, user: User, alert_id: UUID, notes: str | None) -> AlertOut:
    alert = await _get_visible(session, user, alert_id)
    if alert.status != "open":
        raise ConflictError(f"Alert is already {alert.status}")
    alert.status = "acknowledged"
    alert.reviewed_at = utcnow()
    await alert_repository.add_action(
        session, alert_id=alert.id, user_id=user.id, action_type="acknowledged", notes=notes
    )
    await session.commit()
    return AlertOut.from_model(alert)


async def resolve(session: AsyncSession, user: User, alert_id: UUID, notes: str | None) -> AlertOut:
    alert = await _get_visible(session, user, alert_id)
    if alert.status == "resolved":
        raise ConflictError("Alert is already resolved")
    now = utcnow()
    alert.status = "resolved"
    alert.reviewed_at = alert.reviewed_at or now
    alert.resolved_at = now
    await alert_repository.add_action(session, alert_id=alert.id, user_id=user.id, action_type="resolved", notes=notes)
    await session.commit()
    return AlertOut.from_model(alert)
