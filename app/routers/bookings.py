# app/routers/bookings.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Request
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timedelta

from ..db import get_db
from ..schemas.booking import BookingCreate, BookingOut, StatusPatch, BookingStatus
from ..utils import to_id, to_object_id
from ..security import get_current_user
from ..middleware.rate_limit import apply_rate_limit
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------- Utilidades ----------
# Usar to_object_id de utils.py en lugar de _oid local
_oid = to_object_id

def _days_between_inclusive(start_dt: datetime, end_dt: datetime) -> list[str]:
    if end_dt < start_dt:
        raise HTTPException(status_code=400, detail="end debe ser posterior a start")
    days = []
    cur = start_dt.date()
    last = end_dt.date()
    while cur <= last:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days

def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return (a_start < b_end) and (a_end > b_start)

ALLOWED: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.pending: {BookingStatus.accepted, BookingStatus.rejected},
    BookingStatus.accepted: {BookingStatus.completed, BookingStatus.rejected},
    BookingStatus.rejected: set(),
    BookingStatus.completed: set(),
}

def _to_out(doc: dict) -> dict:
    d = to_id(doc)
    if isinstance(d.get("status"), BookingStatus):
        d["status"] = d["status"].value
    return d

# ---------- Endpoints ----------

@router.get("/mine", response_model=List[BookingOut])
@router.get("/my", response_model=List[BookingOut])  # alias opcional
async def list_my_bookings(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    docs = await db.bookings.find({
        "$or": [{"owner_id": current["id"]}, {"caretaker_id": current["id"]}]
    }).sort("start", 1).to_list(500)
    return [_to_out(d) for d in docs]

@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(
    booking_id: str = Path(..., pattern=r"^[0-9a-fA-F]{24}$"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    b = await db.bookings.find_one({"_id": _oid(booking_id)})
    if not b:
        raise HTTPException(404, "Reserva no encontrada")
    if str(b.get("owner_id")) != current["id"] and str(b.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "Sin acceso a esta reserva")
    return _to_out(b)

@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: Request,
    payload: BookingCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    # Rate limiting: máximo 15 reservas por minuto por IP
    apply_rate_limit(request, "15/minute")
    if payload.end <= payload.start:
        raise HTTPException(400, "end debe ser posterior a start")

    caretaker = await db.users.find_one({"_id": _oid(payload.caretaker_id)})
    if not caretaker or not caretaker.get("is_caretaker", False):
        raise HTTPException(404, "Cuidador no encontrado")

    service = await db.services.find_one({"_id": _oid(payload.service_id)})
    if not service or str(service.get("caretaker_id")) != payload.caretaker_id:
        raise HTTPException(400, "Servicio inválido para este cuidador")

    pet = await db.pets.find_one({"_id": _oid(payload.pet_id)})
    if not pet or str(pet.get("owner_id")) != current["id"]:
        raise HTTPException(403, "No puedes reservar con una mascota que no es tuya")

    av = caretaker.get("availability", {"max_pets": 1, "blocked_dates": []})
    max_pets = max(1, int(av.get("max_pets", 1)))
    blocked = set(av.get("blocked_dates", []))
    for day in _days_between_inclusive(payload.start, payload.end):
        if day in blocked:
            raise HTTPException(400, f"El cuidador no está disponible el {day}")

    overlapping = await db.bookings.count_documents({
        "caretaker_id": payload.caretaker_id,
        "status": {"$in": [BookingStatus.pending.value, BookingStatus.accepted.value]},
        "start": {"$lt": payload.end},
        "end": {"$gt": payload.start},
    })
    if overlapping >= max_pets:
        raise HTTPException(409, "No hay hueco en esas fechas/horas")

    # Calcular precio total basado en el servicio y duración
    service_price = float(service.get("price", 0))
    duration_days = (payload.end - payload.start).days + 1
    if duration_days < 1:
        duration_days = 1
    total_price = round(service_price * duration_days, 2)

    doc = {
        "owner_id": current["id"],
        "caretaker_id": payload.caretaker_id,
        "service_id": payload.service_id,
        "pet_id": payload.pet_id,
        "start": payload.start,
        "end": payload.end,
        "status": BookingStatus.pending.value,
        "total_price": total_price,
        "created_at": datetime.utcnow(),
    }
    res = await db.bookings.insert_one(doc)
    created = await db.bookings.find_one({"_id": res.inserted_id})
    return _to_out(created)

@router.patch("/{booking_id}/status", response_model=BookingOut)
async def patch_status(
    body: StatusPatch,  # <-- SIN default va primero
    booking_id: str = Path(..., pattern=r"^[0-9a-fA-F]{24}$"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    doc = await db.bookings.find_one({"_id": _oid(booking_id)})
    if not doc:
        raise HTTPException(404, "Reserva no encontrada")

    # Obtener el status actual (puede ser string o BookingStatus)
    status_str = doc.get("status")
    if not status_str:
        raise HTTPException(400, "Estado de reserva inválido")
    try:
        old = BookingStatus(status_str) if isinstance(status_str, str) else status_str
    except (ValueError, TypeError):
        raise HTTPException(400, f"Estado de reserva inválido: {status_str}")
    
    new = body.status

    # Verificar que el usuario actual es el cuidador
    caretaker_id_str = str(doc.get("caretaker_id", ""))
    if caretaker_id_str != current["id"]:
        raise HTTPException(403, "Solo el cuidador puede cambiar el estado")

    if new == old:
        return _to_out(doc)

    allowed_next = ALLOWED.get(old, set())
    if new not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Transición no permitida: {old.value} → {new.value}",
        )

    if new == BookingStatus.accepted:
        # Usar ObjectId para buscar el cuidador
        caretaker_oid = doc["caretaker_id"] if isinstance(doc["caretaker_id"], ObjectId) else _oid(caretaker_id_str)
        caretaker = await db.users.find_one({"_id": caretaker_oid})
        if not caretaker:
            raise HTTPException(404, "Cuidador no encontrado")
        av = caretaker.get("availability", {"max_pets": 1})
        max_pets = max(1, int(av.get("max_pets", 1)))
        overlapping = await db.bookings.count_documents({
            "_id": {"$ne": doc["_id"]},
            "caretaker_id": caretaker_id_str,  # Usar string para la consulta
            "status": {"$in": [BookingStatus.pending.value, BookingStatus.accepted.value]},
            "start": {"$lt": doc["end"]},
            "end": {"$gt": doc["start"]},
        })
        if overlapping >= max_pets:
            raise HTTPException(409, "Capacidad agotada; no se puede aceptar")

    await db.bookings.update_one({"_id": doc["_id"]}, {"$set": {"status": new.value}})
    updated = await db.bookings.find_one({"_id": doc["_id"]})
    return _to_out(updated)
