# app/routers/reports.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime
from uuid import uuid4
from pathlib import Path

from ..db import get_db
from ..config import get_settings
from ..security import get_current_user
from ..utils import to_id
from ..schemas.report import ReportCreate, ReportOut, ReportType
# Importación condicional para evitar circular
def get_websocket_manager():
    from ..routers.websocket import manager
    return manager

router = APIRouter()
settings = get_settings()

def _oid(value: str, field_name: str = "id") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return ObjectId(value)

@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Crear un reporte durante el servicio (foto, check-in, actualización).
    Solo el cuidador puede crear reportes.
    """
    # Verificar que la reserva existe y pertenece al cuidador
    booking = await db.bookings.find_one({"_id": _oid(payload.booking_id)})
    if not booking:
        raise HTTPException(404, "Reserva no encontrada")
    
    if str(booking.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "Solo el cuidador puede crear reportes")
    
    if booking.get("status") not in ["accepted", "completed"]:
        raise HTTPException(400, "Solo se pueden crear reportes para reservas aceptadas o completadas")
    
    # Validar tipo de reporte
    if payload.type == ReportType.photo and not payload.photo_url:
        raise HTTPException(400, "Los reportes de foto requieren photo_url")
    
    # Crear reporte
    doc = {
        "booking_id": payload.booking_id,
        "caretaker_id": current["id"],
        "type": payload.type.value,
        "message": payload.message,
        "photo_url": payload.photo_url,
        "activity_type": payload.activity_type,
        "created_at": datetime.utcnow(),
    }
    
    res = await db.reports.insert_one(doc)
    created = await db.reports.find_one({"_id": res.inserted_id})
    report_out = _to_report_out(created)
    
    # Notificar al dueño vía WebSocket si está conectado
    owner_id = booking.get("owner_id")
    if owner_id:
        try:
            manager = get_websocket_manager()
            await manager.send_personal_message({
                "type": "new_report",
                "report": report_out,
                "booking_id": payload.booking_id,
            }, str(owner_id))
        except Exception:
            pass  # Si no hay conexión WebSocket, no pasa nada
    
    return report_out

@router.post("/{report_id}/photo", response_model=ReportOut)
async def upload_report_photo(
    report_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Subir foto para un reporte existente.
    """
    report = await db.reports.find_one({"_id": _oid(report_id)})
    if not report:
        raise HTTPException(404, "Reporte no encontrado")
    
    if str(report.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "No eres el propietario de este reporte")
    
    # Validar tipo de archivo
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(415, "Solo imágenes")
    
    # Guardar archivo
    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{ext}"
    rel_path = Path("reports") / filename
    abs_path = Path(settings.media_dir) / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Guardar async
    import aiofiles
    async with aiofiles.open(abs_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)
    
    photo_url = f"/media/{rel_path.as_posix()}"
    
    # Actualizar reporte
    await db.reports.update_one(
        {"_id": _oid(report_id)},
        {"$set": {"photo_url": photo_url, "type": ReportType.photo.value}}
    )
    
    updated = await db.reports.find_one({"_id": _oid(report_id)})
    report_out = _to_report_out(updated)
    
    # Notificar al dueño
    booking = await db.bookings.find_one({"_id": report.get("booking_id")})
    if booking:
        owner_id = booking.get("owner_id")
        if owner_id:
            try:
                manager = get_websocket_manager()
                await manager.send_personal_message({
                    "type": "new_report",
                    "report": report_out,
                    "booking_id": str(booking["_id"]),
                }, str(owner_id))
            except Exception:
                pass
    
    return report_out

@router.get("/booking/{booking_id}", response_model=List[ReportOut])
async def get_booking_reports(
    booking_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Obtener todos los reportes de una reserva.
    Solo el dueño o el cuidador pueden ver los reportes.
    """
    booking = await db.bookings.find_one({"_id": _oid(booking_id)})
    if not booking:
        raise HTTPException(404, "Reserva no encontrada")
    
    owner_id = str(booking.get("owner_id"))
    caretaker_id = str(booking.get("caretaker_id"))
    
    if current["id"] not in [owner_id, caretaker_id]:
        raise HTTPException(403, "No tienes acceso a estos reportes")
    
    docs = await db.reports.find({"booking_id": booking_id}).sort("created_at", 1).to_list(100)
    return [_to_report_out(d) for d in docs]

@router.get("/mine", response_model=List[ReportOut])
async def list_my_reports(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Listar todos los reportes creados por el cuidador o recibidos como dueño.
    """
    # Obtener bookings donde el usuario es dueño o cuidador
    bookings = await db.bookings.find({
        "$or": [
            {"owner_id": current["id"]},
            {"caretaker_id": current["id"]}
        ]
    }).to_list(1000)
    
    booking_ids = [str(b["_id"]) for b in bookings]
    
    docs = await db.reports.find({"booking_id": {"$in": booking_ids}}).sort("created_at", -1).to_list(200)
    return [_to_report_out(d) for d in docs]

def _to_report_out(doc: dict) -> dict:
    """Convierte documento de MongoDB a ReportOut"""
    d = to_id(doc)
    if isinstance(d.get("type"), ReportType):
        d["type"] = d["type"].value
    return d

