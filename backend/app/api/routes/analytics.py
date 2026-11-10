from fastapi import APIRouter

from app.schemas.analytics import AnalyticsSummary
from app.services.mock_data import get_analytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary() -> AnalyticsSummary:
    return get_analytics()

