from pydantic import BaseModel, Field
from typing import Optional, Literal

ServiceType = Literal["boarding", "daycare", "walking", "house_sitting", "drop_in"]

class ServiceCreate(BaseModel):
    type: ServiceType
    price: float = Field(..., ge=0)
    description: Optional[str] = Field(None, max_length=280)

class ServiceOut(BaseModel):
    id: str
    caretaker_id: str
    type: ServiceType
    price: float
    description: Optional[str] = None
    enabled: Optional[bool] = True
