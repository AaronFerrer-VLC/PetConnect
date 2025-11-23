# app/routers/sitters.py
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..db import get_db
from ..utils import to_id, haversine_distance, geocode_city, is_within_radius

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

        sitter_data = {
            "id": sid,
            "name": u.get("name"),
            "city": _city_of(u),
            "photo": u.get("photo") or (u.get("profile") or {}).get("photos", [None])[0],
            "services": services_types,
            "min_price": minp,
            "rating_avg": None,
            "rating_count": 0,
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

@router.get("/{sitter_id}")
async def get_sitter(
    sitter_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not ObjectId.is_valid(sitter_id):
        raise HTTPException(status_code=400, detail="Invalid sitter id")

    u = await db.users.find_one({"_id": ObjectId(sitter_id), "is_caretaker": True})
    if not u:
        raise HTTPException(status_code=404, detail="Cuidador no encontrado")

    # servicios habilitados del cuidador
    svcs = await db.services.find({"caretaker_id": sitter_id, "enabled": True}).to_list(100)
    doc = to_id(u)
    doc["city"] = _city_of(u)
    doc["services"] = [to_id(s) for s in svcs]
    return doc

