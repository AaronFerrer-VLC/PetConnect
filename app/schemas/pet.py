from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class PetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    breed: Optional[str] = Field(None, max_length=80)
    age_years: Optional[float] = None
    weight_kg: Optional[float] = None
    sex: Literal["M","F","unknown"] = "unknown"
    photos: List[str] = []
    care_instructions: Optional[str] = None
    personality: Optional[str] = None
    needs: Optional[str] = None
    notes: Optional[str] = None

class PetOut(PetCreate):
    id: str
    owner_id: str
