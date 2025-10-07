from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from .config import get_settings
from .db import get_db
from .utils import to_id

settings = get_settings()
ALGO = "HS256"
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(p: str) -> str:
    return pwd.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)

def create_access_token(sub: str, hours: Optional[int] = None) -> str:
    exp = datetime.utcnow() + timedelta(hours=hours or settings.jwt_expires_hours)
    return jwt.encode({"sub": sub, "exp": exp}, settings.jwt_secret, algorithm=ALGO)

async def get_current_user_id(token: str = Depends(oauth2)) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token inválido")
        return str(sub)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

async def get_current_user(db: AsyncIOMotorDatabase = Depends(get_db),
                           user_id: str = Depends(get_current_user_id)):
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return to_id(doc)
