from pydantic import BaseModel, Field
from typing import Optional

class PetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    species: str = Field(..., min_length=2, max_length=40)
    owner_id: str

class PetOut(BaseModel):
    id: str
    name: str
    species: str
    owner_id: str