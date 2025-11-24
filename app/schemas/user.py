from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal, Dict

Size = Literal["small", "medium", "large", "giant"]

class Profile(BaseModel):
    city: Optional[str] = None
    bio: Optional[str] = None
    accepts_sizes: List[Size] = []
    home_type: Optional[str] = None
    has_yard: Optional[bool] = None
    photos: List[str] = []

class AvailabilityOut(BaseModel):
    max_pets: int = 1
    blocked_dates: list[str] = Field(default_factory=list)
    weekly_open: Dict[str, bool] = Field(
        default_factory=lambda: {"sun": True, "mon": True, "tue": True, "wed": True, "thu": True, "fri": True, "sat": True}
    )

class AvailabilityPatch(BaseModel):
    max_pets: Optional[int] = None
    blocked_dates: Optional[list[str]] = None

# Para /auth/signup ya llevas su propio modelo en el router de auth.
# Aquí dejamos un create "genérico" por si lo usas en /users.
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    city: Optional[str] = None
    is_caretaker: bool = False
    photo: Optional[str] = None   # base64/URL opcional
    bio: Optional[str] = None

class UserUpdateMe(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    photo: Optional[str] = None   # avatar

class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    is_caretaker: bool
    plan: Optional[str] = None
    subscription_status: Optional[str] = None

    # Campos de perfil/galería visibles en dashboard/perfil/sitio público
    photo: Optional[str] = None
    gallery: list[str] = []
    city: Optional[str] = None     # espejo rápido de profile.city
    profile: Profile = Profile()

    # Dirección y teléfono (solo para cuidadores)
    address: Optional[str] = None
    phone: Optional[str] = None

    # Disponibilidad resumida
    availability: AvailabilityOut = AvailabilityOut()

    # Geolocalización + metadatos útiles para búsquedas
    lat: Optional[float] = None
    lng: Optional[float] = None
    created_at: Optional[str] = None

