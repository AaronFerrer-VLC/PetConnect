from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import get_settings

_settings = get_settings()
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

async def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(_settings.mongodb_uri)
        _db = _client[_settings.db_name]
        # Create indexes you need
        await _db.users.create_index("email", unique=True)
        await _db.pets.create_index([("owner_id", 1)])
        await _db.services.create_index([("caretaker_id", 1)])
        await _db.bookings.create_index([("owner_id", 1), ("caretaker_id", 1)])
        await _db.messages.create_index([("thread_id", 1)])
    return _db