from fastapi import APIRouter, HTTPException

from app.schemas.vehicle import Vehicle
from app.services.mock_data import get_vehicles

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("", response_model=list[Vehicle])
def list_vehicles() -> list[Vehicle]:
    return get_vehicles()


@router.get("/{vehicle_id}", response_model=Vehicle)
def get_vehicle(vehicle_id: str) -> Vehicle:
    vehicle = next((item for item in get_vehicles() if item.id == vehicle_id), None)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle

