from fastapi import FastAPI
from .config import get_settings
from fastapi.middleware.cors import CORSMiddleware
from .routers import users, pets, services, bookings, messages, auth

settings = get_settings()
app = FastAPI(title=settings.app_name)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,   # da igual si no usas cookies, no estorba
    allow_methods=["*"],      # incluye OPTIONS para la preflight
    allow_headers=["*"],      # permite Authorization, Content-Type, etc.
)

@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.env}

# Routers
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(pets.router, prefix="/pets", tags=["pets"])
app.include_router(services.router, prefix="/services", tags=["services"])
app.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])