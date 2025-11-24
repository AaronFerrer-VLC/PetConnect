"""
Middleware para aplicar rate limiting a endpoints específicos usando slowapi
"""
from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

def apply_rate_limit(request: Request, limit: str):
    """
    Aplica rate limiting a un endpoint específico.
    Uso: apply_rate_limit(request, "5/minute")
    
    Si el limiter no está configurado (por ejemplo, en tests), la función no hace nada.
    """
    # Obtener el limiter del state usando getattr para evitar errores si no existe
    limiter = getattr(request.app.state, "limiter", None)
    
    # Si no hay limiter configurado (por ejemplo, en tests), saltar rate limiting
    if limiter is None:
        return
    
    key = get_remote_address(request)
    
    # Usar el método hit() que incrementa el contador y lanza excepción si se excede
    try:
        limiter.hit(limit, key)
    except RateLimitExceeded:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiadas solicitudes. Límite: {limit}. Intenta más tarde."
        )

