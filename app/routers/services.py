from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..schemas.service import ServiceCreate, ServiceOut
from ..utils import to_id
from bson import ObjectId

router = APIRouter()

@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(payload: ServiceCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    if not ObjectId.is_valid(payload.caretaker_id):
        raise HTTPException(400, "Invalid caretaker_id")
    ct = await db.users.find_one({"_id": ObjectId(payload.caretaker_id)})
    if not ct:
        raise HTTPException(404, "Caretaker not found")

    res = await db.services.insert_one(payload.model_dump())
    doc = await db.services.find_one({"_id": res.inserted_id})
    return to_id(doc)

@router.get("", response_model=List[ServiceOut])
async def list_services(db: AsyncIOMotorDatabase = Depends(get_db)):
    items = []
    async for doc in db.services.find().sort("title", 1):
        items.append(to_id(doc))
    return items