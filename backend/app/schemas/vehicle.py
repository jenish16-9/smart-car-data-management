from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.vehicle import VehicleStatus


class VehicleCreate(BaseModel):
    vin: str = Field(min_length=17, max_length=17)
    name: str = Field(min_length=1, max_length=100)
    make: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=60)
    year: int = Field(ge=1886, le=2100)
    license_plate: str | None = Field(default=None, max_length=20)

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, value: str) -> str:
        normalized = value.strip().upper()
        if any(char in normalized for char in "IOQ") or not normalized.isalnum():
            raise ValueError("VIN must contain 17 letters/digits excluding I, O, and Q")
        return normalized


class VehicleResponse(VehicleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime


class VehicleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    make: str | None = Field(default=None, min_length=1, max_length=60)
    model: str | None = Field(default=None, min_length=1, max_length=60)
    year: int | None = Field(default=None, ge=1886, le=2100)
    license_plate: str | None = Field(default=None, max_length=20)
    status: VehicleStatus | None = None
