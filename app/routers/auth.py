from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..db import get_db
from ..security import hash_password, verify_password, create_access_token
from ..utils import to_id, geocode_city
from ..middleware.rate_limit import apply_rate_limit
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Validadores personalizados
def validate_phone(phone: str) -> str:
    """Valida formato de teléfono (permite +, números, espacios, guiones)"""
    if not phone:
        return phone
    # Remover espacios y guiones para validar
    cleaned = re.sub(r'[\s\-]', '', phone)
    # Debe empezar con + seguido de números, o solo números
    if not re.match(r'^\+?\d{9,15}$', cleaned):
        raise ValueError("Formato de teléfono inválido. Use formato internacional (ej: +34600123456)")
    return phone

def validate_password_strength(password: str) -> str:
    """Valida que la contraseña tenga al menos 6 caracteres y no sea demasiado común"""
    if len(password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres")
    if len(password) > 72:  # Límite de bcrypt
        raise ValueError("La contraseña no puede exceder 72 caracteres")
    # Verificar que no sea solo números o solo letras (opcional, más estricto)
    if password.isdigit() or password.isalpha():
        logger.warning(f"Contraseña débil detectada (solo números o solo letras)")
    return password

class Signup(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, description="Nombre completo del usuario")
    email: EmailStr = Field(..., description="Email válido")
    password: str = Field(..., min_length=6, max_length=72, description="Contraseña (mín. 6 caracteres)")
    city: str | None = Field(None, max_length=100, description="Ciudad de residencia")
    is_caretaker: bool = Field(False, description="Indica si el usuario es cuidador")
    photo: str | None = Field(None, description="URL o base64 de foto de perfil")
    image: str | None = Field(None, description="Compatibilidad con campo anterior")
    bio: str | None = Field(None, max_length=1000, description="Biografía del usuario")
    gallery: list[str] | None = Field(None, max_length=10, description="Lista de URLs de fotos de galería")
    max_pets: int | None = Field(None, ge=1, le=20, description="Máximo de mascotas que puede cuidar")
    accepts_sizes: list[str] | None = Field(None, description="Tamaños de mascotas aceptados")
    lat: float | None = Field(None, ge=-90, le=90, description="Latitud")
    lng: float | None = Field(None, ge=-180, le=180, description="Longitud")
    address: str | None = Field(None, max_length=200, description="Dirección completa")
    phone: str | None = Field(None, max_length=20, description="Teléfono de contacto")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)
    
    @field_validator('phone')
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        if v:
            return validate_phone(v)
        return v
    
    @field_validator('accepts_sizes')
    @classmethod
    def validate_sizes(cls, v: list[str] | None) -> list[str] | None:
        if v:
            valid_sizes = {"small", "medium", "large", "giant"}
            invalid = [s for s in v if s not in valid_sizes]
            if invalid:
                raise ValueError(f"Tamaños inválidos: {invalid}. Válidos: {valid_sizes}")
        return v
    
    @model_validator(mode='after')
    def validate_caretaker_fields(self):
        """Valida que si es cuidador, tenga campos requeridos"""
        if self.is_caretaker:
            if self.max_pets is None:
                self.max_pets = 2  # Default
        return self

class Login(BaseModel):
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=1, description="Contraseña")

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: Request, payload: Signup, db: AsyncIOMotorDatabase = Depends(get_db)):
    # Rate limiting: máximo 5 registros por minuto por IP
    apply_rate_limit(request, "5/minute")
    
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
async def login(request: Request, payload: Login, db: AsyncIOMotorDatabase = Depends(get_db)):
    # Rate limiting: máximo 10 intentos de login por minuto por IP
    apply_rate_limit(request, "10/minute")
    
    user = await db.users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(401, "Credenciales inválidas")
    token = create_access_token(str(user["_id"]))
    return {"access_token": token, "token_type": "bearer"}
