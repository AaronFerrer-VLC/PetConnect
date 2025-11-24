# app/utils.py
from typing import Any, Dict, Optional, Tuple
import math
from bson import ObjectId
from datetime import datetime
from fastapi import HTTPException

def to_id(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convierte _id -> id (str) y todos los ObjectIds a strings.
    También convierte datetime a ISO format strings.
    Si doc es None, devuelve {}.
    Útil para content-type dinámico en respuestas internas.
    """
    if doc is None:
        return {}
    d = dict(doc)
    
    # Convertir _id a id
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    
    # Convertir todos los ObjectIds a strings
    for key, value in d.items():
        if isinstance(value, ObjectId):
            d[key] = str(value)
        elif isinstance(value, datetime):
            d[key] = value.isoformat()
        elif isinstance(value, dict):
            # Recursivamente convertir ObjectIds en diccionarios anidados
            d[key] = to_id(value)
        elif isinstance(value, list):
            # Convertir ObjectIds en listas
            d[key] = [
                str(item) if isinstance(item, ObjectId) 
                else item.isoformat() if isinstance(item, datetime)
                else to_id(item) if isinstance(item, dict)
                else item
                for item in value
            ]
    
    return d

# ==================== Geolocalización ====================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia en kilómetros entre dos puntos usando la fórmula de Haversine.
    """
    R = 6371  # Radio de la Tierra en kilómetros
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    """
    Geocodifica una ciudad a coordenadas (lat, lng).
    En producción usarías Google Geocoding API o similar.
    Por ahora, devolvemos coordenadas mockeadas de ciudades conocidas.
    """
    # Coordenadas mockeadas de ciudades españolas comunes
    city_coords = {
        "madrid": (40.4168, -3.7038),
        "barcelona": (41.3851, 2.1734),
        "valencia": (39.4699, -0.3763),
        "sevilla": (37.3891, -5.9845),
        "bilbao": (43.2627, -2.9253),
        "zaragoza": (41.6488, -0.8891),
        "málaga": (36.7213, -4.4214),
        "murcia": (37.9922, -1.1307),
        "palma": (39.5696, 2.6502),
        "las palmas": (28.1248, -15.4300),
        "granada": (37.1773, -3.5986),
        "vigo": (42.2406, -8.7207),
        "córdoba": (37.8882, -4.7794),
        "alicante": (38.3452, -0.4810),
        "oviedo": (43.3619, -5.8494),
    }
    
    city_lower = city.lower().strip()
    # Buscar coincidencia exacta o parcial
    for city_name, coords in city_coords.items():
        if city_name in city_lower or city_lower in city_name:
            return coords
    
    # Si no se encuentra, devolver coordenadas de Madrid por defecto
    return (40.4168, -3.7038)

def is_within_radius(
    center_lat: float,
    center_lng: float,
    point_lat: float,
    point_lng: float,
    radius_km: float
) -> bool:
    """Verifica si un punto está dentro de un radio dado"""
    distance = haversine_distance(center_lat, center_lng, point_lat, point_lng)
    return distance <= radius_km

# ==================== Utilidades de Base de Datos ====================

def to_object_id(value: str, field_name: str = "id") -> ObjectId:
    """
    Convierte un string a ObjectId con validación.
    Centraliza la lógica de conversión para evitar duplicación.
    """
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value}")
    return ObjectId(value)
