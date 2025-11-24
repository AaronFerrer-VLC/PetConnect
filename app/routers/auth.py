from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..security import hash_password, verify_password, create_access_token
from ..utils import to_id, geocode_city

router = APIRouter()

class Signup(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=6)
    city: str | None = None
    is_caretaker: bool = False
    photo: str | None = None
    image: str | None = None  # compat
    bio: str | None = None
    gallery: list[str] | None = None
    max_pets: int | None = None
    accepts_sizes: list[str] | None = None
    lat: float | None = None
    lng: float | None = None
    address: str | None = None  # Dirección (solo para cuidadores)
    phone: str | None = None    # Teléfono (solo para cuidadores)

class Login(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: Signup, db: AsyncIOMotorDatabase = Depends(get_db)):
    exists = await db.users.find_one({"email": payload.email})
    if exists:
        raise HTTPException(409, "Email ya registrado")

    doc = payload.model_dump()
    # password hash
    doc["password_hash"] = hash_password(doc.pop("password"))

    # —— defaults que espera el front/dashboard/perfil ——
    doc.setdefault("plan", "free")
    doc.setdefault("subscription_status", "active (mock)")
    
    # Construir profile
    profile = {}
    if doc.get("bio"):
        profile["bio"] = doc.pop("bio")
    if doc.get("city"):
        profile["city"] = doc["city"]
    if doc.get("accepts_sizes"):
        profile["accepts_sizes"] = doc.pop("accepts_sizes")
    doc["profile"] = profile if profile else {}
    
    # Construir availability
    max_pets = doc.pop("max_pets", None) or (2 if doc.get("is_caretaker") else 1)
    availability = {
        "max_pets": max_pets,
        "blocked_dates": [],
        "weekly_open": {k: True for k in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}
    }
    doc["availability"] = availability
    
    # Galería y foto
    gallery = doc.pop("gallery", None)
    doc["gallery"] = gallery if gallery is not None else []
    doc.setdefault("photo", doc.get("photo") or doc.get("image"))
    
    # Geolocalización: si hay city pero no lat/lng, geocodificar
    if doc.get("city") and not doc.get("lat") and not doc.get("lng"):
        coords = geocode_city(doc["city"])
        if coords:
            doc["lat"] = coords[0]
            doc["lng"] = coords[1]
    
    # Limpiar campos que no van a la BD
    doc.pop("image", None)

    res = await db.users.insert_one(doc)
    # solemos devolver 201 con el usuario (no imprescindible para el front actual)
    return to_id(await db.users.find_one({"_id": res.inserted_id}))

@router.post("/login")
async def login(payload: Login, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(401, "Credenciales inválidas")
    token = create_access_token(str(user["_id"]))
    return {"access_token": token, "token_type": "bearer"}
