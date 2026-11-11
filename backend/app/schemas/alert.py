from datetime import datetime
from pydantic import BaseModel


class Alert(BaseModel):
    id: str
    vehicle_id: str
    event_type: str
    severity: str
    confidence: int
    status: str
    detected_at: datetime
    location: str
