from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..schemas.message import MessageCreate, MessageOut
from ..utils import to_id

router = APIRouter()

@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(payload: MessageCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    data = payload.model_dump()
    data["created_at"] = datetime.utcnow()
    res = await db.messages.insert_one(data)
    doc = await db.messages.find_one({"_id": res.inserted_id})
    return to_id(doc)

@router.get("", response_model=List[MessageOut])
async def list_messages(thread_id: str | None = None, db: AsyncIOMotorDatabase = Depends(get_db)):
    query = {"thread_id": thread_id} if thread_id else {}
    items = []
    async for doc in db.messages.find(query).sort("created_at", -1):
        items.append(to_id(doc))
    return items