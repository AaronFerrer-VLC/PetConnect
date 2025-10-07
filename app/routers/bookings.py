from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..schemas.booking import BookingCreate, BookingOut, BookingStatusUpdate
from ..utils import to_id
from bson import ObjectId

router = APIRouter()

@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(payload: BookingCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    for key in ["owner_id", "caretaker_id", "service_id", "pet_id"]:
        if not ObjectId.is_valid(getattr(payload, key)):
            raise HTTPException(400, f"Invalid {key}")
    # basic existence checks
    if not await db.users.find_one({"_id": ObjectId(payload.owner_id)}):
        raise HTTPException(404, "Owner not found")
    if not await db.users.find_one({"_id": ObjectId(payload.caretaker_id)}):
        raise HTTPException(404, "Caretaker not found")
    if not await db.services.find_one({"_id": ObjectId(payload.service_id)}):
        raise HTTPException(404, "Service not found")
    if not await db.pets.find_one({"_id": ObjectId(payload.pet_id)}):
        raise HTTPException(404, "Pet not found")

    if payload.end <= payload.start:
        raise HTTPException(400, "end must be after start")

    res = await db.bookings.insert_one(payload.model_dump())
    doc = await db.bookings.find_one({"_id": res.inserted_id})
    return to_id(doc)

@router.get("", response_model=List[BookingOut])
async def list_bookings(db: AsyncIOMotorDatabase = Depends(get_db)):
    items = []
    async for doc in db.bookings.find().sort("start", -1):
        items.append(to_id(doc))
    return items

@router.patch("/{booking_id}/status", response_model=BookingOut)
async def update_status(booking_id: str, payload: BookingStatusUpdate, db: AsyncIOMotorDatabase = Depends(get_db)):
    if not ObjectId.is_valid(booking_id):
        raise HTTPException(400, "Invalid booking id")

    doc = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not doc:
        raise HTTPException(404, "Booking not found")

    old = doc.get("status", "pending")
    new = payload.status
    allowed = {
        "pending": {"accepted", "rejected"},
        "accepted": {"completed", "rejected"},
        "rejected": set(),
        "completed": set(),
    }
    if old != new and new not in allowed.get(old, set()):
        raise HTTPException(400, f"Transición no permitida: {old} → {new}")

    await db.bookings.update_one({"_id": doc["_id"]}, {"$set": {"status": new}})
    doc = await db.bookings.find_one({"_id": doc["_id"]})
    return to_id(doc)