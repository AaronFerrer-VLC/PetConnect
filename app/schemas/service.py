from pydantic import BaseModel, Field
from typing import Optional

class ServiceCreate(BaseModel):
    caretaker_id: str
    title: str = Field(..., min_length=3, max_length=80)
    price_per_hour: float = Field(..., ge=0.0)
    description: Optional[str] = None
    category: Optional[str] = None  # "paseo", "alojamiento", etc.

class ServiceOut(BaseModel):
    id: str
    caretaker_id: str
    title: str
    price_per_hour: float
    description: Optional[str] = None