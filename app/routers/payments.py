# app/routers/payments.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime
import uuid

from ..db import get_db
from ..security import get_current_user
from ..utils import to_id
from ..schemas.payment import PaymentCreate, PaymentOut, PaymentStatus, PaymentMethod

router = APIRouter()

# Comisión de plataforma: 15% (como Rover)
PLATFORM_FEE_RATE = 0.15

def _oid(value: str, field_name: str = "id") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return ObjectId(value)

def _calculate_payment(amount: float) -> dict:
    """Calcula comisión de plataforma y pago al cuidador"""
    platform_fee = round(amount * PLATFORM_FEE_RATE, 2)
    caretaker_payout = round(amount - platform_fee, 2)
    return {
        "platform_fee": platform_fee,
        "caretaker_payout": caretaker_payout,
    }

@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Crea un pago mockeado para una reserva.
    En producción, esto se integraría con Stripe/PayPal.
    """
    # Verificar que la reserva existe y pertenece al usuario
    booking = await db.bookings.find_one({"_id": _oid(payload.booking_id)})
    if not booking:
        raise HTTPException(404, "Reserva no encontrada")
    
    if str(booking.get("owner_id")) != current["id"]:
        raise HTTPException(403, "Solo el dueño puede pagar esta reserva")
    
    if booking.get("status") != "accepted":
        raise HTTPException(400, "Solo se puede pagar una reserva aceptada")
    
    # Verificar que no existe ya un pago para esta reserva
    existing = await db.payments.find_one({"booking_id": payload.booking_id})
    if existing:
        raise HTTPException(400, "Ya existe un pago para esta reserva")
    
    # Calcular comisiones
    calc = _calculate_payment(payload.amount)
    
    # Crear pago mockeado
    doc = {
        "booking_id": payload.booking_id,
        "owner_id": current["id"],
        "caretaker_id": booking.get("caretaker_id"),
        "amount": payload.amount,
        "platform_fee": calc["platform_fee"],
        "caretaker_payout": calc["caretaker_payout"],
        "status": PaymentStatus.pending.value,
        "payment_method": payload.payment_method.value,
        "transaction_id": None,  # Se generará al procesar
        "created_at": datetime.utcnow(),
        "completed_at": None,
    }
    
    res = await db.payments.insert_one(doc)
    created = await db.payments.find_one({"_id": res.inserted_id})
    return _to_payment_out(created)

@router.post("/{payment_id}/process", response_model=PaymentOut)
async def process_payment(
    payment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Procesa un pago mockeado (simula el procesamiento de tarjeta).
    En producción, esto llamaría a Stripe/PayPal.
    """
    payment = await db.payments.find_one({"_id": _oid(payment_id)})
    if not payment:
        raise HTTPException(404, "Pago no encontrado")
    
    if str(payment.get("owner_id")) != current["id"]:
        raise HTTPException(403, "No tienes acceso a este pago")
    
    if payment.get("status") != PaymentStatus.pending.value:
        raise HTTPException(400, f"El pago ya está {payment.get('status')}")
    
    # Simular procesamiento (en producción esto sería asíncrono con webhooks)
    transaction_id = f"mock_txn_{uuid.uuid4().hex[:16]}"
    
    await db.payments.update_one(
        {"_id": payment["_id"]},
        {
            "$set": {
                "status": PaymentStatus.completed.value,
                "transaction_id": transaction_id,
                "completed_at": datetime.utcnow(),
            }
        }
    )
    
    updated = await db.payments.find_one({"_id": payment["_id"]})
    return _to_payment_out(updated)

@router.get("/mine", response_model=List[PaymentOut])
async def list_my_payments(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Lista todos los pagos del usuario (como dueño o cuidador)"""
    docs = await db.payments.find({
        "$or": [
            {"owner_id": current["id"]},
            {"caretaker_id": current["id"]}
        ]
    }).sort("created_at", -1).to_list(100)
    return [_to_payment_out(d) for d in docs]

@router.get("/booking/{booking_id}", response_model=Optional[PaymentOut])
async def get_payment_by_booking(
    booking_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Obtiene el pago asociado a una reserva"""
    payment = await db.payments.find_one({"booking_id": booking_id})
    if not payment:
        return None
    
    # Verificar acceso
    if str(payment.get("owner_id")) != current["id"] and str(payment.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "No tienes acceso a este pago")
    
    return _to_payment_out(payment)

@router.post("/{payment_id}/refund", response_model=PaymentOut)
async def refund_payment(
    payment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Simula un reembolso (solo para demo).
    En producción, esto procesaría el reembolso real.
    """
    payment = await db.payments.find_one({"_id": _oid(payment_id)})
    if not payment:
        raise HTTPException(404, "Pago no encontrado")
    
    if str(payment.get("owner_id")) != current["id"]:
        raise HTTPException(403, "Solo el dueño puede solicitar reembolso")
    
    if payment.get("status") != PaymentStatus.completed.value:
        raise HTTPException(400, "Solo se pueden reembolsar pagos completados")
    
    await db.payments.update_one(
        {"_id": payment["_id"]},
        {"$set": {"status": PaymentStatus.refunded.value}}
    )
    
    updated = await db.payments.find_one({"_id": payment["_id"]})
    return _to_payment_out(updated)

def _to_payment_out(doc: dict) -> dict:
    """Convierte documento de MongoDB a PaymentOut"""
    d = to_id(doc)
    if isinstance(d.get("status"), PaymentStatus):
        d["status"] = d["status"].value
    if isinstance(d.get("payment_method"), PaymentMethod):
        d["payment_method"] = d["payment_method"].value
    return d

