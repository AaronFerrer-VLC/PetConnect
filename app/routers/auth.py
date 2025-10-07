from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..security import hash_password, verify_password, create_access_token
from ..utils import to_id

router = APIRouter()

class Signup(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=6)
    city: str | None = None
    is_caretaker: bool = False

class Login(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: Signup, db: AsyncIOMotorDatabase = Depends(get_db)):
    if await db.users.find_one({"email": payload.email}):
        raise HTTPException(409, "Email ya registrado")
    doc = payload.model_dump()
    doc["password_hash"] = hash_password(doc.pop("password"))
    res = await db.users.insert_one(doc)
    return to_id(await db.users.find_one({"_id": res.inserted_id}))

@router.post("/login")
async def login(payload: Login, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(401, "Credenciales inválidas")
    token = create_access_token(str(user["_id"]))
    return {"access_token": token, "token_type": "bearer"}

