from datetime import datetime, timezone

from app.schemas.alert import Alert
from app.schemas.analytics import AnalyticsSummary


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
