from pydantic import BaseModel
from enum import Enum
from datetime import datetime

class BookingStatus(str, Enum):
    pending   = "pending"
    accepted  = "accepted"
    rejected  = "rejected"
    completed = "completed"

class BookingCreate(BaseModel):
    caretaker_id: str
    service_id: str
    pet_id: str
    start: datetime
    end: datetime

class BookingOut(BaseModel):
    id: str
    owner_id: str
    caretaker_id: str
    service_id: str
    pet_id: str
    start: datetime
    end: datetime
    status: BookingStatus
    total_price: float | None = None

class StatusPatch(BaseModel):
    status: BookingStatus
