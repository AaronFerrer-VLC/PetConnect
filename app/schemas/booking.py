from pydantic import BaseModel
from datetime import datetime

class BookingCreate(BaseModel):
    owner_id: str
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