from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    city: Optional[str] = None
    is_caretaker: bool = False
    password: str = Field(..., min_length=6)

class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    city: Optional[str] = None
    is_caretaker: bool