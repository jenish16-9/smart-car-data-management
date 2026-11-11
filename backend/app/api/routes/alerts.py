from fastapi import APIRouter

from app.schemas.alert import Alert
from app.services.mock_data import get_alerts

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[Alert])
def list_alerts() -> list[Alert]:
    return get_alerts()
