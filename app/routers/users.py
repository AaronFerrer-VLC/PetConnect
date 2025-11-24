# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..db import get_db
from ..security import get_current_user
from ..utils import to_id
from ..schemas.user import UserOut, AvailabilityOut  # AvailabilityOut debe incluir weekly_open

router = APIRouter()

# --------- modelos de entrada ---------
class UserPatch(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    photo: Optional[str] = None
    profile: Optional[dict] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None
    phone: Optional[str] = None

class GalleryIn(BaseModel):
    images: List[str]

# --------- helpers ----------
WEEK_DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

def _oid(value: str, field_name: str = "id") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return ObjectId(value)

def _normalize_blocked_dates(dates: Optional[list[str]]) -> list[str]:
    if not dates:
        return []
    out: set[str] = set()
    for d in dates:
        if not isinstance(d, str) or len(d) != 10:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {d!r}. Use YYYY-MM-DD.")
        ymd = d.split("-")
        if len(ymd) != 3 or not all(part.isdigit() for part in ymd):
            raise HTTPException(status_code=400, detail=f"Invalid date format: {d!r}. Use YYYY-MM-DD.")
        out.add(d)
    return sorted(out)

def _normalize_weekly_open(wo: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    base = {k: True for k in WEEK_DAYS}
    if isinstance(wo, dict):
        for k, v in wo.items():
            if k in base:
                base[k] = bool(v)
    return base

def _normalize_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Devuelve el usuario con subdocumentos/valores normalizados."""
    if not doc:
        return doc
    out = to_id(doc)

    out.setdefault("plan", "free")
    out.setdefault("subscription_status", None)
    out["photo"] = out.get("photo") or None

    # profile
    profile = out.get("profile") or {}
    profile.setdefault("city", out.get("city") or profile.get("city") or None)
    profile.setdefault("bio", profile.get("bio") or "")
    profile.setdefault("accepts_sizes", profile.get("accepts_sizes") or [])
    profile.setdefault("home_type", profile.get("home_type") or None)
    profile.setdefault("has_yard", bool(profile.get("has_yard", False)))
    profile.setdefault("photos", profile.get("photos") or [])
    out["profile"] = profile

    # compat: ciudad "plana"
    out["city"] = out.get("city") or profile.get("city")

    # availability
    av = out.get("availability") or {}
    out["availability"] = {
        "max_pets": max(1, int(av.get("max_pets", 1))) if str(av.get("max_pets", 1)).isdigit() else 1,
        "blocked_dates": _normalize_blocked_dates(av.get("blocked_dates", [])),
        "weekly_open": _normalize_weekly_open(av.get("weekly_open")),
    }

    # galería
    out["gallery"] = out.get("gallery") or []
    
    # geolocalización
    out["lat"] = out.get("lat")
    out["lng"] = out.get("lng")
    
    return out

# -------------------- Usuarios --------------------

@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def create_user(payload: dict, db: AsyncIOMotorDatabase = Depends(get_db)):
    exists = await db.users.find_one({"email": payload.get("email")})
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")

    doc = dict(payload)
    # defaults completos
    doc.setdefault("plan", "free")
    doc.setdefault("profile", {})
    doc.setdefault(
        "availability",
        {
            "max_pets": 1,
            "blocked_dates": [],
            "weekly_open": {k: True for k in WEEK_DAYS},
        },
    )
    doc.setdefault("gallery", [])
    doc.setdefault("photo", doc.get("photo") or doc.get("image"))

    res = await db.users.insert_one(doc)
    doc = await db.users.find_one({"_id": res.inserted_id})
    return _normalize_user(doc)

@router.get("/me", response_model=UserOut)
async def get_me(db: AsyncIOMotorDatabase = Depends(get_db), current=Depends(get_current_user)):
    u = await db.users.find_one({"_id": _oid(current["id"])})
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _normalize_user(u)

@router.patch("/me", response_model=UserOut)
async def patch_me(
    body: UserPatch,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    u = await db.users.find_one({"_id": _oid(current["id"])})
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    updates: Dict[str, Any] = {}

    if body.name is not None:
        updates["name"] = body.name
    if body.city is not None:
        updates["city"] = body.city
        updates["profile.city"] = body.city
        # Geocodificar ciudad si no hay coordenadas
        if body.lat is None or body.lng is None:
            from ..utils import geocode_city
            coords = geocode_city(body.city)
            if coords:
                updates["lat"] = coords[0]
                updates["lng"] = coords[1]
    if body.lat is not None:
        updates["lat"] = body.lat
    if body.lng is not None:
        updates["lng"] = body.lng
    if body.photo is not None:
        updates["photo"] = body.photo
    if body.bio is not None:
        updates["profile.bio"] = body.bio
    if body.address is not None:
        updates["address"] = body.address
    if body.phone is not None:
        updates["phone"] = body.phone
    if body.profile:
        for k, v in body.profile.items():
            updates[f"profile.{k}"] = v

    if updates:
        await db.users.update_one({"_id": u["_id"]}, {"$set": updates})

    u2 = await db.users.find_one({"_id": u["_id"]})
    return _normalize_user(u2)

# -------------------- Disponibilidad --------------------

@router.get("/me/availability", response_model=AvailabilityOut)
async def get_my_availability(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    u = await db.users.find_one({"_id": _oid(current["id"])})
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _normalize_user(u)["availability"]

@router.patch("/me/availability", response_model=AvailabilityOut)
async def patch_my_availability(
    body: dict,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    u = await db.users.find_one({"_id": _oid(current["id"])})
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    av = u.get("availability") or {
        "max_pets": 1,
        "blocked_dates": [],
        "weekly_open": {k: True for k in WEEK_DAYS},
    }

    # max_pets
    if "max_pets" in body:
        try:
            av["max_pets"] = max(1, int(body["max_pets"]))
        except Exception:
            raise HTTPException(status_code=400, detail="max_pets debe ser entero >= 1")

    # blocked_dates (reemplaza lista completa)
    if "blocked_dates" in body:
        av["blocked_dates"] = _normalize_blocked_dates(body["blocked_dates"])

    # weekly_open (merge parcial)
    if "weekly_open" in body and isinstance(body["weekly_open"], dict):
        wo = _normalize_weekly_open(av.get("weekly_open"))
        for k, v in body["weekly_open"].items():
            if k in wo:
                wo[k] = bool(v)
        av["weekly_open"] = wo

    await db.users.update_one({"_id": u["_id"]}, {"$set": {"availability": av}})
    u2 = await db.users.find_one({"_id": u["_id"]})
    return _normalize_user(u2)["availability"]

# -------------------- Galería --------------------

@router.post("/me/gallery", response_model=List[str])
async def add_to_gallery(
    payload: GalleryIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    await db.users.update_one(
        {"_id": _oid(current["id"])},
        {"$addToSet": {"gallery": {"$each": payload.images}}},
    )
    u = await db.users.find_one({"_id": _oid(current["id"])})
    return _normalize_user(u)["gallery"]

@router.delete("/me/gallery", response_model=List[str])
async def remove_from_gallery(
    url: str = Query(..., description="URL/base64 a eliminar"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current=Depends(get_current_user),
):
    await db.users.update_one({"_id": _oid(current["id"])}, {"$pull": {"gallery": url}})
    u = await db.users.find_one({"_id": _oid(current["id"])})
    return _normalize_user(u)["gallery"]
