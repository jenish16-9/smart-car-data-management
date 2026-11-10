from datetime import datetime, timezone

from app.schemas.alert import Alert
from app.schemas.analytics import AnalyticsSummary
from app.schemas.vehicle import Vehicle


def get_vehicles() -> list[Vehicle]:
    return [
        Vehicle(
            id="CAR-1024",
            name="CAR-1024",
            type="Sedan",
            status="connected",
            last_seen=datetime.now(timezone.utc),
            uptime="2 days 6 hours",
            engine_status="healthy",
            cabin_audio_status="online",
            gps_status="locked",
        ),
        Vehicle(
            id="CAR-1025",
            name="CAR-1025",
            type="SUV",
            status="connected",
            last_seen=datetime.now(timezone.utc),
            uptime="1 day 4 hours",
            engine_status="healthy",
            cabin_audio_status="online",
            gps_status="locked",
        ),
    ]


def get_alerts() -> list[Alert]:
    return [
        Alert(
            id="ALT-1001",
            vehicle_id="CAR-1024",
            event_type="Glass Break",
            severity="high",
            confidence=94,
            status="unread",
            detected_at=datetime.now(timezone.utc),
            location="Front Right",
        )
    ]


def get_analytics() -> AnalyticsSummary:
    return AnalyticsSummary(
        total_events=1248,
        critical_events=87,
        average_confidence=92,
        resolution_rate=96,
    )

