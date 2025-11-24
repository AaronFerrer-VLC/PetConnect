# app/routers/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, Set
import json
from bson import ObjectId
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from ..db import get_db
from ..security import get_current_user_id
from ..utils import to_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Almacenar conexiones activas: {user_id: WebSocket}
active_connections: Dict[str, WebSocket] = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending to {user_id}: {e}", exc_info=True)
                self.disconnect(user_id)

    async def broadcast(self, message: dict, exclude_user_id: str = None):
        for user_id, connection in list(self.active_connections.items()):
            if user_id != exclude_user_id:
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(user_id)

manager = ConnectionManager()

async def get_user_from_token(websocket: WebSocket, token: str) -> str:
    """Extrae el user_id del token JWT"""
    try:
        from jose import jwt, JWTError
        from ..config import get_settings
        
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return None
        return str(user_id)
    except JWTError:
        await websocket.close(code=1008, reason="Invalid token")
        return None
    except Exception as e:
        await websocket.close(code=1008, reason="Invalid token")
        return None

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    Endpoint WebSocket para mensajería en tiempo real.
    El token se pasa como parámetro en la URL.
    """
    user_id = await get_user_from_token(websocket, token)
    if not user_id:
        return

    await manager.connect(websocket, user_id)
    
    try:
        # Enviar mensaje de bienvenida
        await websocket.send_json({
            "type": "connected",
            "message": "Conectado al chat",
            "user_id": user_id
        })

        from ..db import get_db
        db = await get_db()
        
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "send_message":
                # Crear mensaje en la base de datos
                thread_id = data.get("thread_id")
                receiver_id = data.get("receiver_id")
                body = data.get("body")

                if not all([thread_id, receiver_id, body]):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Faltan campos requeridos"
                    })
                    continue

                # Guardar mensaje en DB
                message_doc = {
                    "thread_id": thread_id,
                    "sender_id": user_id,
                    "receiver_id": receiver_id,
                    "body": body,
                    "created_at": datetime.utcnow(),
                    "read": False,
                }
                res = await db.messages.insert_one(message_doc)
                message_doc["_id"] = res.inserted_id
                message_out = to_id(message_doc)

                # Enviar al receptor si está conectado
                await manager.send_personal_message({
                    "type": "new_message",
                    "message": message_out,
                }, receiver_id)

                # Confirmar al emisor
                await websocket.send_json({
                    "type": "message_sent",
                    "message": message_out,
                })

            elif message_type == "mark_read":
                # Marcar mensajes como leídos
                thread_id = data.get("thread_id")
                if thread_id:
                    await db.messages.update_many(
                        {
                            "thread_id": thread_id,
                            "receiver_id": user_id,
                            "read": False
                        },
                        {"$set": {"read": True, "read_at": datetime.utcnow()}}
                    )
                    await websocket.send_json({
                        "type": "messages_read",
                        "thread_id": thread_id
                    })

            elif message_type == "typing":
                # Notificar que alguien está escribiendo
                thread_id = data.get("thread_id")
                receiver_id = data.get("receiver_id")
                is_typing = data.get("is_typing", False)
                
                await manager.send_personal_message({
                    "type": "typing",
                    "thread_id": thread_id,
                    "sender_id": user_id,
                    "is_typing": is_typing,
                }, receiver_id)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}", exc_info=True)
        manager.disconnect(user_id)

