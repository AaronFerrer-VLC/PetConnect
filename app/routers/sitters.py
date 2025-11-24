# app/routers/sitters.py
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..db import get_db
from ..utils import to_id, haversine_distance, geocode_city, is_within_radius
from ..security import get_current_user_id

router = APIRouter()

def _city_of(u: Dict[str, Any]) -> Optional[str]:
    return (u.get("profile") or {}).get("city") or u.get("city")

@router.get("/search")
async def search_sitters(
    db: AsyncIOMotorDatabase = Depends(get_db),
    city: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="búsqueda por nombre/ciudad"),
    size: Optional[str] = Query(None, description="small|medium|large"),
    type: Optional[str] = Query(None, description="tipo de servicio"),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    lat: Optional[float] = Query(None, description="Latitud del centro de búsqueda"),
    lng: Optional[float] = Query(None, description="Longitud del centro de búsqueda"),
    radius_km: Optional[float] = Query(None, description="Radio de búsqueda en kilómetros"),
    sort_by: Optional[str] = Query("distance", description="distance|price|rating"),
):
    """
    Devuelve tarjetas 'SitterCard':
    { id, name, city, photo, services[], min_price, rating_avg?, rating_count? }
    """
    # 1) base: sólo cuidadores
    match: Dict[str, Any] = {"is_caretaker": True}

    if city:
        match["$or"] = [
            {"city": city},
            {"profile.city": city},
        ]
    if size:
        match.setdefault("$and", []).append(
            {"profile.accepts_sizes": {"$in": [size]}}
        )
    if q:
        # match 'light' por nombre o ciudad
        match.setdefault("$or", []).extend([
            {"name": {"$regex": q, "$options": "i"}},
            {"city": {"$regex": q, "$options": "i"}},
            {"profile.city": {"$regex": q, "$options": "i"}},
        ])

    users = await db.users.find(match).to_list(1000)

    if not users:
        return []

    sitter_ids = [str(u["_id"]) for u in users]

    # 2) servicios por cuidador (sólo habilitados)
    svcs = await db.services.find({
        "caretaker_id": {"$in": sitter_ids},
        "enabled": True,
    }).to_list(5000)

    # indexamos servicios por cuidador
    by_ct: Dict[str, List[Dict[str, Any]]] = {}
    for s in svcs:
        by_ct.setdefault(s["caretaker_id"], []).append(s)

    # Determinar centro de búsqueda geográfica
    search_lat = lat
    search_lng = lng
    if not search_lat or not search_lng:
        if city:
            coords = geocode_city(city)
            if coords:
                search_lat, search_lng = coords

    out: List[Dict[str, Any]] = []
    for u in users:
        sid = str(u["_id"])
        services_ct = by_ct.get(sid, [])

        # filtro de tipo y precio si vienen en query
        filtered = services_ct
        if type:
            filtered = [s for s in filtered if s.get("type") == type]
        if min_price is not None:
            filtered = [s for s in filtered if int(s.get("price", 0)) >= min_price]
        if max_price is not None:
            filtered = [s for s in filtered if int(s.get("price", 0)) <= max_price]

        # si aplicando filtros se queda vacío, lo ocultamos
        # PERO solo si se especificó un filtro de tipo/precio
        # Si no hay servicios pero no hay filtros, mostramos al cuidador de todas formas
        if (type or min_price is not None or max_price is not None) and not filtered:
            continue

        # Filtro geográfico por radio
        u_lat = u.get("lat")
        u_lng = u.get("lng")
        distance_km = None
        
        if search_lat and search_lng and u_lat and u_lng:
            distance_km = haversine_distance(search_lat, search_lng, u_lat, u_lng)
            
            # Filtrar por radio si se especifica
            if radius_km is not None and distance_km > radius_km:
                continue
        elif radius_km is not None and (search_lat or search_lng):
            # Si se especifica radio pero el cuidador no tiene coordenadas, saltar
            # PERO solo si hay una búsqueda geográfica activa
            continue

        minp = min((int(s.get("price", 0)) for s in services_ct), default=None)
        services_types = sorted({s.get("type") for s in services_ct if s.get("type")})

        # Calcular rating promedio y conteo de reseñas
        reviews = await db.reviews.find({"sitter_id": ObjectId(sid)}).to_list(100)
        rating_avg = None
        rating_count = 0
        if reviews:
            ratings = [r.get("rating", 0) for r in reviews if isinstance(r.get("rating"), (int, float))]
            if ratings:
                rating_avg = sum(ratings) / len(ratings)
                rating_count = len(ratings)

        sitter_data = {
            "id": sid,
            "name": u.get("name"),
            "city": _city_of(u),
            "photo": u.get("photo") or (u.get("profile") or {}).get("photos", [None])[0],
            "address": u.get("address"),  # Añadir dirección
            "bio": (u.get("profile") or {}).get("bio", ""),
            "services": services_types,
            "min_price": minp,
            "rating_avg": round(rating_avg, 1) if rating_avg is not None else None,
            "rating_count": rating_count,
            "accepts_sizes": (u.get("profile") or {}).get("accepts_sizes") or [],
        }
        
        # Agregar información geográfica
        if u_lat and u_lng:
            sitter_data["lat"] = u_lat
            sitter_data["lng"] = u_lng
        
        if distance_km is not None:
            sitter_data["distance_km"] = round(distance_km, 2)

        out.append(sitter_data)

    # Ordenar resultados
    if sort_by == "distance" and search_lat and search_lng:
        out.sort(key=lambda x: x.get("distance_km", float("inf")))
    elif sort_by == "price":
        out.sort(key=lambda x: x.get("min_price", float("inf")))
    elif sort_by == "rating":
        out.sort(key=lambda x: x.get("rating_avg", 0), reverse=True)

    return out

async def get_current_user_optional_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[str]:
    """Devuelve el user_id si hay token válido, None si no."""
    if not credentials:
        return None
    try:
        user_id = await get_current_user_id(token=credentials.credentials)
        return user_id
    except Exception:
        return None

@router.get("/{sitter_id}")
async def get_sitter(
    sitter_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_optional_id),
):
    if not ObjectId.is_valid(sitter_id):
        raise HTTPException(status_code=400, detail="Invalid sitter id")

    u = await db.users.find_one({"_id": ObjectId(sitter_id), "is_caretaker": True})
    if not u:
        raise HTTPException(status_code=404, detail="Cuidador no encontrado")

    # servicios habilitados del cuidador
    svcs = await db.services.find({"caretaker_id": sitter_id, "enabled": True}).to_list(100)
    
    # Calcular rating promedio y conteo de reseñas
    reviews = await db.reviews.find({"sitter_id": ObjectId(sitter_id), "review_type": "sitter"}).to_list(100)
    rating_avg = None
    rating_count = 0
    if reviews:
        ratings = [r.get("rating", 0) for r in reviews if isinstance(r.get("rating"), (int, float))]
        if ratings:
            rating_avg = sum(ratings) / len(ratings)
            rating_count = len(ratings)
    
    doc = to_id(u)
    doc["city"] = _city_of(u)
    doc["address"] = u.get("address")  # Siempre mostrar dirección si existe
    doc["services"] = [to_id(s) for s in svcs]
    doc["rating_avg"] = round(rating_avg, 1) if rating_avg is not None else None
    doc["rating_count"] = rating_count
    
    # Verificar si el usuario actual tiene acceso al teléfono
    # Solo mostrar teléfono si el usuario es dueño de una reserva pagada con este cuidador
    show_phone = False
    if current_user_id and ObjectId.is_valid(current_user_id):
        # Buscar si hay un pago completado donde el usuario actual es el dueño y este cuidador es el cuidador
        payment = await db.payments.find_one({
            "owner_id": ObjectId(current_user_id),
            "caretaker_id": ObjectId(sitter_id),
            "status": "completed"
        })
        if payment:
            show_phone = True
    
    if show_phone:
        doc["phone"] = u.get("phone")
    else:
        doc["phone"] = None  # No mostrar teléfono si no hay acceso
    
    return doc

