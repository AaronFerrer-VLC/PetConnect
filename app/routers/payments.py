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
    try:
        # Verificar que la reserva existe y pertenece al usuario
        booking_oid = _oid(payload.booking_id, "booking_id")
        booking = await db.bookings.find_one({"_id": booking_oid})
        if not booking:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")
        
        # Convertir owner_id y caretaker_id a string para comparación
        booking_owner_id = str(booking.get("owner_id", ""))
        booking_caretaker_id = str(booking.get("caretaker_id", ""))
        current_id = str(current.get("id", ""))
        
        if booking_owner_id != current_id:
            raise HTTPException(status_code=403, detail="Solo el dueño puede pagar esta reserva")
        
        booking_status = booking.get("status")
        if booking_status != "accepted":
            raise HTTPException(
                status_code=400, 
                detail=f"Solo se puede pagar una reserva aceptada. Estado actual: {booking_status}"
            )
        
        # Verificar que no existe ya un pago para esta reserva
        existing = await db.payments.find_one({"booking_id": booking_oid})
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe un pago para esta reserva")
        
        # Calcular comisiones
        calc = _calculate_payment(payload.amount)
        
        # Obtener payment_method como string (puede venir como enum o string)
        payment_method_str = payload.payment_method
        if hasattr(payment_method_str, 'value'):
            payment_method_str = payment_method_str.value
        elif not isinstance(payment_method_str, str):
            payment_method_str = str(payment_method_str)
        
        # Validar que el método de pago sea válido
        if payment_method_str not in ["card", "bank_transfer"]:
            payment_method_str = "card"  # Default
        
        # Crear pago mockeado
        doc = {
            "booking_id": booking_oid,
            "owner_id": _oid(current_id),
            "caretaker_id": _oid(booking_caretaker_id),
            "amount": float(payload.amount),
            "platform_fee": calc["platform_fee"],
            "caretaker_payout": calc["caretaker_payout"],
            "status": PaymentStatus.pending.value,
            "payment_method": payment_method_str,
            "transaction_id": None,  # Se generará al procesar
            "created_at": datetime.utcnow(),
            "completed_at": None,
        }
        
        res = await db.payments.insert_one(doc)
        created = await db.payments.find_one({"_id": res.inserted_id})
        if not created:
            raise HTTPException(status_code=500, detail="Error al crear el pago")
        
        return _to_payment_out(created)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Error en create_payment: {error_msg}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error al crear el pago: {error_msg}")

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
    current_id = _oid(current["id"])
    docs = await db.payments.find({
        "$or": [
            {"owner_id": current_id},
            {"caretaker_id": current_id}
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
    try:
        booking_oid = _oid(booking_id, "booking_id")
    except HTTPException:
        return None
    
    payment = await db.payments.find_one({"booking_id": booking_oid})
    if not payment:
        return None
    
    # Verificar acceso
    if str(payment.get("owner_id")) != current["id"] and str(payment.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "No tienes acceso a este pago")
    
    return _to_payment_out(payment)

@router.get("/caretaker/stats")
async def get_caretaker_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Obtiene estadísticas de pagos para el cuidador: total acumulado, pagos completados, etc."""
    if not current.get("is_caretaker"):
        raise HTTPException(403, "Solo cuidadores pueden ver estas estadísticas")
    
    # Obtener todos los pagos completados del cuidador
    payments = await db.payments.find({
        "caretaker_id": _oid(current["id"]),
        "status": "completed"
    }).to_list(1000)
    
    total_earnings = sum(p.get("caretaker_payout", 0) for p in payments)
    total_payments = len(payments)
    total_platform_fee = sum(p.get("platform_fee", 0) for p in payments)
    
    # Pagos pendientes
    pending_payments = await db.payments.find({
        "caretaker_id": _oid(current["id"]),
        "status": {"$in": ["pending", "processing"]}
    }).to_list(100)
    
    pending_total = sum(p.get("caretaker_payout", 0) for p in pending_payments)
    
    return {
        "total_earnings": round(total_earnings, 2),
        "total_payments": total_payments,
        "total_platform_fee": round(total_platform_fee, 2),
        "pending_earnings": round(pending_total, 2),
        "pending_count": len(pending_payments),
    }

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
    if not doc:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    d = to_id(doc)
    
    # Convertir ObjectIds a strings si es necesario
    for key in ["booking_id", "owner_id", "caretaker_id"]:
        if key in d and isinstance(d[key], ObjectId):
            d[key] = str(d[key])
    
    # Convertir status
    status_val = d.get("status")
    if isinstance(status_val, PaymentStatus):
        d["status"] = status_val.value
    elif not isinstance(status_val, str):
        d["status"] = str(status_val) if status_val else "pending"
    
    # Convertir payment_method
    method_val = d.get("payment_method")
    if isinstance(method_val, PaymentMethod):
        d["payment_method"] = method_val.value
    elif not isinstance(method_val, str):
        d["payment_method"] = str(method_val) if method_val else "card"
    
    return d

