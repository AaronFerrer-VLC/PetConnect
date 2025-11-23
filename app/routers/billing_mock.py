from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..db import get_db
from ..config import get_settings
from ..security import get_current_user

router = APIRouter()
settings = get_settings()

@router.post("/create-checkout-session")
async def create_checkout_session(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Demo 100% gratis: activa plan PRO para cuidadores sin cobrar nada.
    Devuelve una URL de 'éxito' para que el front redirija.
    """
    if not current.get("is_caretaker"):
        raise HTTPException(403, "Sólo cuidadores pueden activar el plan Pro (demo)")
    await db.users.update_one(
        {"_id": ObjectId(current["id"])},
        {"$set": {"plan": "pro", "subscription_status": "active (mock)"}},
    )
    return {"url": f"{settings.frontend_base_url}/pricing?success=1&mock=1"}

@router.post("/create-portal-session")
async def create_portal_session(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Simula un 'portal' de facturación. El front puede mostrar botón de downgrade.
    """
    return {"url": f"{settings.frontend_base_url}/pricing?portal=1&mock=1"}

@router.post("/downgrade")
async def downgrade(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """
    Cancela la suscripción en modo demo.
    """
    await db.users.update_one(
        {"_id": ObjectId(current["id"])},
        {"$set": {"plan": "free", "subscription_status": "canceled (mock)"}},
    )
    return {"ok": True}

@router.post("/webhook")
async def webhook():
    """
    No hace nada en mock (compatibilidad de rutas).
    """
    return {"ok": True}
