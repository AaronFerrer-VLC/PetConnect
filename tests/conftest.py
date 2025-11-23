# tests/conftest.py
import os, sys, pytest, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.db import get_db

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def _override_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri)
    db = client[os.getenv("DB_NAME", "petconnect_test")]
    async def _get_db():
        return db
    app.dependency_overrides[get_db] = _get_db
    # Limpieza antes de cada test
    for col in ["users", "pets", "services", "bookings", "messages"]:
        await db[col].delete_many({})
    yield
    app.dependency_overrides.clear()
    client.close()
