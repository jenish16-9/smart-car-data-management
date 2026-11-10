from datetime import datetime
from pydantic import BaseModel


class Vehicle(BaseModel):
    id: str
    name: str
    type: str
    status: str
    last_seen: datetime
    uptime: str
    engine_status: str
    cabin_audio_status: str
    gps_status: str

