# app/routers/services.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from ..db import get_db
from ..security import get_current_user
from ..utils import to_id

router = APIRouter()

SERVICE_TYPES = {"boarding", "daycare", "walking", "house_sitting", "drop_in"}

def _oid(v: str, field: str = "id") -> ObjectId:
    if not ObjectId.is_valid(v):
        raise HTTPException(400, f"Invalid {field}")
    return ObjectId(v)

# GET /services?sitter_id=...
@router.get("", response_model=List[Dict[str, Any]])
async def list_services(
    sitter_id: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if sitter_id:
        q["caretaker_id"] = sitter_id        # público: servicios de un cuidador
    else:
        q["caretaker_id"] = current["id"]     # “mis servicios”

    docs = await db.services.find(q).sort("type", 1).to_list(200)
    return [to_id(d) for d in docs]

# POST /services
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    if not current.get("is_caretaker"):
        raise HTTPException(403, "Solo cuidadores")

    stype = payload.get("type")
    if stype not in SERVICE_TYPES:
        raise HTTPException(400, "type inválido")

    try:
        price = float(payload.get("price"))
    except Exception:
        raise HTTPException(400, "price inválido")

    doc = {
        "caretaker_id": current["id"],     # string
        "type": stype,
        "price": price,
        "description": payload.get("description") or "",
        "enabled": bool(payload.get("enabled", True)),
    }
    res = await db.services.insert_one(doc)
    created = await db.services.find_one({"_id": res.inserted_id})
    return to_id(created)

# PATCH /services/{service_id}  (editar precio/descripcion/enabled)
@router.patch("/{service_id}")
async def patch_service(
    service_id: str,
    payload: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    s = await db.services.find_one({"_id": _oid(service_id)})
    if not s:
        raise HTTPException(404, "Servicio no encontrado")
    if str(s.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "No eres el propietario")

    updates: Dict[str, Any] = {}
    if "price" in payload:
        try:
            updates["price"] = float(payload["price"])
        except Exception:
            raise HTTPException(400, "price inválido")
    for k in ("description", "enabled"):
        if k in payload:
            updates[k] = payload[k]

    if not updates:
        return to_id(s)

    await db.services.update_one({"_id": s["_id"]}, {"$set": updates})
    s2 = await db.services.find_one({"_id": s["_id"]})
    return to_id(s2)

# POST /services/{service_id}/toggle   (activar/desactivar rápido)
@router.post("/{service_id}/toggle")
async def toggle_service(
    service_id: str,
    body: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    s = await db.services.find_one({"_id": _oid(service_id)})
    if not s:
        raise HTTPException(404, "Servicio no encontrado")
    if str(s.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "No eres el propietario")

    enabled = bool(body.get("enabled", True))
    await db.services.update_one({"_id": s["_id"]}, {"$set": {"enabled": enabled}})
    s2 = await db.services.find_one({"_id": s["_id"]})
    return to_id(s2)

# POST /services/me/enabled  (activar/desactivar todos los de un tipo)
@router.post("/me/enabled")
async def set_service_enabled(
    body: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    if not current.get("is_caretaker"):
        raise HTTPException(403, "Solo cuidadores")

    stype = body.get("type")
    if stype not in SERVICE_TYPES:
        raise HTTPException(400, "type inválido")

    enabled = bool(body.get("enabled", True))
    await db.services.update_many(
        {"caretaker_id": current["id"], "type": stype},
        {"$set": {"enabled": enabled}},
    )
    docs = await db.services.find({"caretaker_id": current["id"]}).to_list(200)
    return [to_id(d) for d in docs]

# DELETE /services/{service_id}  (eliminar)
@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    s = await db.services.find_one({"_id": _oid(service_id)})
    if not s:
        raise HTTPException(404, "Servicio no encontrado")
    if str(s.get("caretaker_id")) != current["id"]:
        raise HTTPException(403, "No eres el propietario")

    await db.services.delete_one({"_id": s["_id"]})
    # 204 No Content
