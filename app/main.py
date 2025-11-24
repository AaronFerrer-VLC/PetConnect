from fastapi import FastAPI
from .config import get_settings
from fastapi.middleware.cors import CORSMiddleware
from .routers import users, pets, services, bookings, messages, auth, sitters, reviews, payments, websocket, reports
from .config import get_settings
from starlette.staticfiles import StaticFiles

settings = get_settings()

# --- importa el router de billing según proveedor ---
if settings.billing_provider == "stripe":
    from .routers import billing_stripe as billing
else:
    from .routers import billing_mock as billing
# ----------------------------------------------------

app = FastAPI(title=settings.app_name)
app.mount("/media", StaticFiles(directory=get_settings().media_dir), name="media")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos
    allow_headers=["*"],  # Permitir todos los headers
    expose_headers=["*"],  # Exponer todos los headers
)

@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.env, "billing_provider": settings.billing_provider}

# Routers
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(pets.router, prefix="/pets", tags=["pets"])
app.include_router(services.router, prefix="/services", tags=["services"])
app.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(sitters.router, prefix="/sitters", tags=["sitters"])
app.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])

# Endpoint de desarrollo (solo en dev)
if settings.env == "dev":
    from .routers import dev
    app.include_router(dev.router, prefix="/dev", tags=["dev"])
