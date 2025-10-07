from pydantic import BaseModel
from datetime import datetime
from typing import Literal

BookingStatus = Literal["pending", "accepted", "rejected", "completed"]

class BookingCreate(BaseModel):
    owner_id: str
    caretaker_id: str
    service_id: str
    pet_id: str
    start: datetime
    end: datetime
    status: BookingStatus = "pending"

class BookingOut(BaseModel):
    id: str
    owner_id: str
    caretaker_id: str
    service_id: str
    pet_id: str
    start: datetime
    end: datetime
    status: BookingStatus

class BookingStatusUpdate(BaseModel):
    status: BookingStatus
