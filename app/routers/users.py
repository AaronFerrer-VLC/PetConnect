from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..schemas.user import UserCreate, UserOut
from ..utils import to_id
from ..security import get_current_user

router = APIRouter()

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    exists = await db.users.find_one({"email": payload.email})
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    res = await db.users.insert_one(payload.model_dump())
    doc = await db.users.find_one({"_id": res.inserted_id})
    return to_id(doc)

@router.get("", response_model=List[UserOut])
async def list_users(db: AsyncIOMotorDatabase = Depends(get_db)):
    items = []
    async for doc in db.users.find().sort("name", 1):
        items.append(to_id(doc))
    return items

@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    return current_user