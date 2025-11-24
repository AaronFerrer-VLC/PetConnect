from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional, Dict, Any, List
from datetime import datetime
from ..db import get_db
from ..security import get_current_user
from ..utils import to_id, to_object_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Usar función centralizada
_oid = to_object_id

class ReviewCreate(BaseModel):
    booking_id: str
    sitter_id: Optional[str] = None  # Para reseñas del dueño al cuidador
    owner_id: Optional[str] = None   # Para reseñas del cuidador al dueño
    pet_id: Optional[str] = None    # Para reseñas del cuidador al perro
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    review_type: str = Field(default="sitter", description="sitter|owner|pet")  # Tipo de reseña

@router.get("")
async def list_reviews(
    sitter_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    pet_id: Optional[str] = None,
    booking_id: Optional[str] = None,
    review_type: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Lista reseñas. Puede filtrar por sitter_id, owner_id, pet_id, booking_id y review_type.
    """
    try:
        q: Dict[str, Any] = {}
        
        if sitter_id:
            if not ObjectId.is_valid(sitter_id):
                return []
            q["sitter_id"] = ObjectId(sitter_id)
        
        if owner_id:
            if not ObjectId.is_valid(owner_id):
                return []
            q["owner_id"] = ObjectId(owner_id)
            if review_type:
                q["review_type"] = review_type
        
        if pet_id:
            if not ObjectId.is_valid(pet_id):
                return []
            q["pet_id"] = ObjectId(pet_id)
            if review_type:
                q["review_type"] = review_type
        
        if booking_id:
            if not ObjectId.is_valid(booking_id):
                return []
            q["booking_id"] = ObjectId(booking_id)
            if review_type:
                q["review_type"] = review_type
        
        if review_type and not sitter_id and not owner_id and not pet_id and not booking_id:
            q["review_type"] = review_type
        
        out: List[Dict[str, Any]] = []
        cursor = db.reviews.find(q).sort("created_at", -1)
        async for r in cursor:
            try:
                # Convertir ObjectId a string manualmente
                review_dict = {}
                for key, value in r.items():
                    if key == "_id":
                        review_dict["id"] = str(value)
                    elif isinstance(value, ObjectId):
                        review_dict[key] = str(value)
                    elif isinstance(value, datetime):
                        review_dict[key] = value.isoformat()
                    else:
                        review_dict[key] = value
                out.append(review_dict)
            except Exception as e:
                logger.error(f"Error procesando reseña: {e}", exc_info=True)
                continue
        
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en list_reviews: {e}", exc_info=True)
        # Devolver lista vacía en lugar de error 500
        return []

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_review(payload: ReviewCreate,
                        db: AsyncIOMotorDatabase = Depends(get_db),
                        me=Depends(get_current_user)):
    try:
        # Validar booking_id
        if not payload.booking_id:
            raise HTTPException(status_code=400, detail="booking_id es requerido")
        
        booking_oid = _oid(payload.booking_id, "booking_id")
        b = await db.bookings.find_one({"_id": booking_oid})
        if not b:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")
        
        # Manejar owner_id y caretaker_id que pueden ser ObjectId o string
        owner_id = b.get("owner_id")
        caretaker_id = b.get("caretaker_id")
        
        if not owner_id or not caretaker_id:
            raise HTTPException(status_code=400, detail="Datos de reserva incompletos")
        
        owner_id_str = str(owner_id)
        caretaker_id_str = str(caretaker_id)
        me_id_str = str(me.get("id", ""))
        
        if not me_id_str or me_id_str == "None":
            raise HTTPException(status_code=401, detail="Usuario no identificado")
        
        # Validar que me["id"] es un ObjectId válido
        try:
            author_oid = ObjectId(me_id_str)
        except Exception:
            raise HTTPException(status_code=400, detail="ID de usuario inválido")
        
        # Determinar tipo de reseña y validar permisos
        review_type = payload.review_type or "sitter"
        
        if review_type == "sitter":
            # Dueño reseña al cuidador
            if owner_id_str != me_id_str:
                raise HTTPException(status_code=403, detail="Solo el dueño puede reseñar al cuidador")
            # Siempre usar el caretaker_id de la reserva
            try:
                target_id = _oid(caretaker_id_str, "caretaker_id")
            except Exception:
                raise HTTPException(status_code=400, detail="ID de cuidador inválido")
        elif review_type == "owner":
            # Cuidador reseña al dueño
            if caretaker_id_str != me_id_str:
                raise HTTPException(status_code=403, detail="Solo el cuidador puede reseñar al dueño")
            # Siempre usar el owner_id de la reserva
            try:
                target_id = _oid(owner_id_str, "owner_id")
            except Exception:
                raise HTTPException(status_code=400, detail="ID de dueño inválido")
        elif review_type == "pet":
            # Cuidador reseña al perro
            if caretaker_id_str != me_id_str:
                raise HTTPException(status_code=403, detail="Solo el cuidador puede reseñar al perro")
            pet_id = b.get("pet_id")
            if not pet_id:
                raise HTTPException(status_code=400, detail="La reserva no incluye un perro")
            # Siempre usar el pet_id de la reserva
            try:
                target_id = _oid(str(pet_id), "pet_id")
            except Exception:
                raise HTTPException(status_code=400, detail="ID de mascota inválido")
        else:
            raise HTTPException(status_code=400, detail="Tipo de reseña inválido. Debe ser: sitter, owner o pet")
        
        booking_status = b.get("status")
        if booking_status != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"La reserva debe estar completada. Estado actual: {booking_status}"
            )

        # Verificar si ya existe una reseña de este tipo para esta reserva
        # Buscar por booking_id, review_type y author_id para evitar duplicados
        existing_review = await db.reviews.find_one({
            "booking_id": booking_oid,
            "review_type": review_type,
            "author_id": author_oid
        })
        if existing_review:
            raise HTTPException(
                status_code=409,
                detail="Ya has enviado una reseña de este tipo para esta reserva"
            )

        # Validar rating
        rating = int(payload.rating)
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="La puntuación debe estar entre 1 y 5")

        doc = {
            "booking_id": booking_oid,
            "review_type": review_type,
            "author_id": author_oid,
            "author": me.get("name") or me.get("email") or "Usuario",
            "rating": rating,
            "comment": (payload.comment or "").strip() if payload.comment else "",
            "created_at": datetime.utcnow(),
        }
        
        # Añadir el ID del objetivo según el tipo
        if review_type == "sitter":
            doc["sitter_id"] = target_id
        elif review_type == "owner":
            doc["owner_id"] = target_id
        elif review_type == "pet":
            doc["pet_id"] = target_id
        
        res = await db.reviews.insert_one(doc)
        created = await db.reviews.find_one({"_id": res.inserted_id})
        if not created:
            raise HTTPException(status_code=500, detail="Error al crear la reseña")
        
        return to_id(created)
    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error en create_review: {error_msg}", exc_info=True)
        # Devolver error más descriptivo (sin exponer detalles internos en producción)
        raise HTTPException(status_code=500, detail="Error al crear la reseña")

@router.patch("/{review_id}", response_model=Dict[str, Any])
async def update_review(
    review_id: str,
    payload: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
    me=Depends(get_current_user)
):
    """Actualizar una reseña (solo el autor)"""
    try:
        review = await db.reviews.find_one({"_id": _oid(review_id)})
        if not review:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        
        # Convertir author_id a string para comparación
        review_author_id = str(review.get("author_id", ""))
        me_id = str(me.get("id", ""))
        
        if review_author_id != me_id:
            raise HTTPException(status_code=403, detail="Solo puedes editar tus propias reseñas")
    
        updates: Dict[str, Any] = {}
        if "rating" in payload:
            rating = int(payload["rating"])
            if rating < 1 or rating > 5:
                raise HTTPException(status_code=400, detail="La puntuación debe estar entre 1 y 5")
            updates["rating"] = rating
        if "comment" in payload:
            updates["comment"] = (payload["comment"] or "").strip()
        
        if not updates:
            return to_id(review)
        
        updates["updated_at"] = datetime.utcnow()
        await db.reviews.update_one({"_id": _oid(review_id)}, {"$set": updates})
        updated = await db.reviews.find_one({"_id": _oid(review_id)})
        if not updated:
            raise HTTPException(status_code=404, detail="Reseña no encontrada después de actualizar")
        return to_id(updated)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"Error en update_review: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al actualizar la reseña: {error_msg}")

@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    me=Depends(get_current_user)
):
    """Eliminar una reseña (solo el autor)"""
    try:
        review = await db.reviews.find_one({"_id": _oid(review_id)})
        if not review:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        
        # Convertir author_id a string para comparación
        review_author_id = str(review.get("author_id", ""))
        me_id = str(me.get("id", ""))
        
        if review_author_id != me_id:
            raise HTTPException(status_code=403, detail="Solo puedes eliminar tus propias reseñas")
        
        await db.reviews.delete_one({"_id": _oid(review_id)})
        return None
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"Error en delete_review: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al eliminar la reseña: {error_msg}")
