from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from ..db import get_db
from ..security import get_current_user
from ..schemas.message import MessageCreate, MessageOut
from ..utils import to_id, to_object_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Usar función centralizada (con alias para compatibilidad)
def _oid(value: str, field_name: str = "id") -> ObjectId:
    return to_object_id(value, field_name)

@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(
    payload: MessageCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Crear mensaje (también se puede hacer vía WebSocket)"""
    if payload.sender_id != current["id"]:
        raise HTTPException(403, "No puedes enviar mensajes como otro usuario")
    
    data = payload.model_dump()
    data["created_at"] = datetime.utcnow()
    data["read"] = False
    res = await db.messages.insert_one(data)
    doc = await db.messages.find_one({"_id": res.inserted_id})
    return to_id(doc)

@router.get("", response_model=List[MessageOut])
async def list_messages(
    thread_id: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Listar mensajes de un thread o todos los mensajes del usuario"""
    if thread_id:
        query = {"thread_id": thread_id}
    else:
        # Solo mensajes donde el usuario es sender o receiver
        query = {
            "$or": [
                {"sender_id": current["id"]},
                {"receiver_id": current["id"]}
            ]
        }
    
    items = []
    async for doc in db.messages.find(query).sort("created_at", 1):
        items.append(to_id(doc))
    return items

@router.get("/threads", response_model=List[dict])
async def list_threads(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Listar todas las conversaciones (threads) del usuario"""
    # Obtener todos los mensajes del usuario
    messages = []
    async for doc in db.messages.find({
        "$or": [
            {"sender_id": current["id"]},
            {"receiver_id": current["id"]}
        ]
    }).sort("created_at", -1):
        messages.append(to_id(doc))
    
    # Agrupar por thread_id y obtener el último mensaje de cada thread
    threads_map = {}
    for msg in messages:
        thread_id = msg["thread_id"]
        if thread_id not in threads_map:
            threads_map[thread_id] = {
                "thread_id": thread_id,
                "last_message": msg,
                "unread_count": 0,
                "other_user_id": msg["receiver_id"] if msg["sender_id"] == current["id"] else msg["sender_id"],
            }
        # Contar no leídos
        if msg.get("receiver_id") == current["id"] and not msg.get("read", False):
            threads_map[thread_id]["unread_count"] += 1
    
    # Obtener información del otro usuario
    threads = []
    for thread_data in threads_map.values():
        other_user = await db.users.find_one({"_id": _oid(thread_data["other_user_id"])})
        if other_user:
            threads.append({
                "thread_id": thread_data["thread_id"],
                "other_user": to_id(other_user),
                "last_message": thread_data["last_message"],
                "unread_count": thread_data["unread_count"],
            })
    
    return sorted(threads, key=lambda x: x["last_message"]["created_at"], reverse=True)

@router.patch("/{message_id}/read", response_model=MessageOut)
async def mark_message_read(
    message_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Marcar un mensaje como leído"""
    message = await db.messages.find_one({"_id": _oid(message_id)})
    if not message:
        raise HTTPException(404, "Mensaje no encontrado")
    
    if str(message.get("receiver_id")) != current["id"]:
        raise HTTPException(403, "No puedes marcar este mensaje como leído")
    
    await db.messages.update_one(
        {"_id": _oid(message_id)},
        {"$set": {"read": True, "read_at": datetime.utcnow()}}
    )
    
    updated = await db.messages.find_one({"_id": _oid(message_id)})
    return to_id(updated)

@router.patch("/thread/{thread_id}/read-all")
async def mark_thread_read(
    thread_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Marcar todos los mensajes de un thread como leídos"""
    result = await db.messages.update_many(
        {
            "thread_id": thread_id,
            "receiver_id": current["id"],
            "read": False
        },
        {"$set": {"read": True, "read_at": datetime.utcnow()}}
    )
    return {"updated": result.modified_count}

@router.patch("/{message_id}", response_model=MessageOut)
async def update_message(
    message_id: str,
    payload: dict,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Editar un mensaje (solo el autor y dentro de un tiempo límite)"""
    message = await db.messages.find_one({"_id": _oid(message_id)})
    if not message:
        raise HTTPException(404, "Mensaje no encontrado")
    
    if str(message.get("sender_id")) != current["id"]:
        raise HTTPException(403, "Solo puedes editar tus propios mensajes")
    
    # Opcional: limitar edición a mensajes recientes (ej: 15 minutos)
    created_at = message.get("created_at")
    if created_at:
        time_diff = (datetime.utcnow() - created_at).total_seconds()
        if time_diff > 900:  # 15 minutos
            raise HTTPException(400, "Solo puedes editar mensajes recientes (15 minutos)")
    
    updates = {}
    if "body" in payload:
        updates["body"] = payload["body"].strip()
        updates["edited_at"] = datetime.utcnow()
    
    if not updates:
        return to_id(message)
    
    await db.messages.update_one({"_id": _oid(message_id)}, {"$set": updates})
    updated = await db.messages.find_one({"_id": _oid(message_id)})
    return to_id(updated)

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    """Eliminar un mensaje (solo el autor)"""
    message = await db.messages.find_one({"_id": _oid(message_id)})
    if not message:
        raise HTTPException(404, "Mensaje no encontrado")
    
    if str(message.get("sender_id")) != current["id"]:
        raise HTTPException(403, "Solo puedes eliminar tus propios mensajes")
    
    await db.messages.delete_one({"_id": _oid(message_id)})
    return None