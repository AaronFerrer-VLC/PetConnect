from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..schemas.pet import PetCreate, PetOut
from ..utils import to_id
from bson import ObjectId

router = APIRouter()

@router.post("", response_model=PetOut, status_code=status.HTTP_201_CREATED)
async def create_pet(payload: PetCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    # ensure owner exists
    if not ObjectId.is_valid(payload.owner_id):
        raise HTTPException(400, "Invalid owner_id")
    owner = await db.users.find_one({"_id": ObjectId(payload.owner_id)})
    if not owner:
        raise HTTPException(404, "Owner not found")

    res = await db.pets.insert_one(payload.model_dump())
    doc = await db.pets.find_one({"_id": res.inserted_id})
    return to_id(doc)

@router.get("", response_model=List[PetOut])
async def list_pets(db: AsyncIOMotorDatabase = Depends(get_db)):
    items = []
    async for doc in db.pets.find().sort("name", 1):
        items.append(to_id(doc))
    return items