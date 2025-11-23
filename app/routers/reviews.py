from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional, Dict, Any, List
from datetime import datetime
from ..db import get_db
from ..security import get_current_user
from ..utils import to_id

router = APIRouter()

def _oid(v: str, field="id") -> ObjectId:
    if not ObjectId.is_valid(v):
        raise HTTPException(400, f"Invalid {field}")
    return ObjectId(v)

class ReviewCreate(BaseModel):
    booking_id: str
    sitter_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None

@router.get("")
async def list_reviews(sitter_id: Optional[str] = None,
                       db: AsyncIOMotorDatabase = Depends(get_db)):
    q: Dict[str, Any] = {}
    if sitter_id:
        q["sitter_id"] = _oid(sitter_id)
    out: List[Dict[str, Any]] = []
    async for r in db.reviews.find(q).sort("created_at", -1):
        out.append(to_id(r))
    return out

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_review(payload: ReviewCreate,
                        db: AsyncIOMotorDatabase = Depends(get_db),
                        me=Depends(get_current_user)):
    b = await db.bookings.find_one({"_id": _oid(payload.booking_id)})
    if not b:
        raise HTTPException(404, "Booking not found")
    if str(b["owner_id"]) != me["id"]:
        raise HTTPException(403, "Solo el dueño puede reseñar")
    if str(b["caretaker_id"]) != payload.sitter_id:
        raise HTTPException(400, "Booking no pertenece a ese cuidador")
    if b.get("status") != "completed":
        raise HTTPException(400, "La reserva debe estar completada")

    doc = {
        "booking_id": _oid(payload.booking_id),
        "sitter_id": _oid(payload.sitter_id),
        "author_id": ObjectId(me["id"]),
        "author": me.get("name") or me.get("email"),
        "rating": int(payload.rating),
        "comment": payload.comment or "",
        "created_at": datetime.utcnow(),
    }
    res = await db.reviews.insert_one(doc)
    return to_id(await db.reviews.find_one({"_id": res.inserted_id}))
