from fastapi import FastAPI, Request
from .config import get_settings
from fastapi.middleware.cors import CORSMiddleware
from .routers import users, pets, services, bookings, messages, auth, sitters, reviews, payments, websocket, reports
from .config import get_settings
from starlette.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Configurar rate limiting
limiter = Limiter(key_func=get_remote_address)

# --- importa el router de billing según proveedor ---
if settings.billing_provider == "stripe":
    from .routers import billing_stripe as billing
else:
    from .routers import billing_mock as billing
# ----------------------------------------------------

app = FastAPI(title=settings.app_name)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/media", StaticFiles(directory=get_settings().media_dir), name="media")

# Configuración de CORS según entorno
if settings.env == "dev":
    # Desarrollo: más permisivo para facilitar desarrollo
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    cors_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    cors_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_headers = ["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"]
else:
    # Producción: restrictivo - solo orígenes específicos
    frontend_url = settings.frontend_base_url
    cors_origins = [frontend_url] if frontend_url else []
    cors_regex = None
    cors_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_headers = ["Authorization", "Content-Type", "Accept"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_regex,
    allow_credentials=True,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
    expose_headers=["Content-Type"],
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
