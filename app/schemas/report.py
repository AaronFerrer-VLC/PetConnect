from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import Optional, List

class ReportType(str, Enum):
    photo = "photo"
    check_in = "check_in"
    update = "update"
    activity = "activity"

class ReportCreate(BaseModel):
    booking_id: str
    type: ReportType
    message: Optional[str] = None
    photo_url: Optional[str] = None
    activity_type: Optional[str] = None  # "walk", "play", "feed", etc.

class ReportOut(BaseModel):
    id: str
    booking_id: str
    caretaker_id: str
    type: ReportType
    message: Optional[str] = None
    photo_url: Optional[str] = None
    activity_type: Optional[str] = None
    created_at: datetime

