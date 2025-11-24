"""
Configuración de pytest para tests
"""
import pytest
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración de test database
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "petconnect_test")
TEST_MONGODB_URI = os.getenv("TEST_MONGODB_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017"))

# Deshabilitar rate limiting en la app antes de importarla
@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiting():
    """Deshabilita rate limiting para todos los tests"""
    from app.main import app
    app.state.limiter = None

@pytest.fixture(scope="session")
async def test_db():
    """Fixture para base de datos de test"""
    client = AsyncIOMotorClient(TEST_MONGODB_URI)
    db = client[TEST_DB_NAME]
    yield db
    # Limpiar después de los tests
    try:
        await client.drop_database(TEST_DB_NAME)
    except Exception:
        pass  # Ignorar errores al limpiar
    finally:
        client.close()

@pytest.fixture
async def clean_db(test_db):
    """Limpia la base de datos antes de cada test"""
    collections = await test_db.list_collection_names()
    for collection_name in collections:
        await test_db[collection_name].delete_many({})
    yield test_db

@pytest.fixture
def client():
    """Fixture para cliente de test de FastAPI"""
    # Importar aquí para evitar problemas de importación circular
    from app.main import app
    # Asegurar que rate limiting esté deshabilitado
    app.state.limiter = None
    return TestClient(app)

@pytest.fixture
def test_user_data():
    """Datos de usuario de prueba"""
    return {
        "name": "Test User",
        "email": "test@example.com",
        "password": "testpass123",
        "city": "Madrid",
        "is_caretaker": False
    }

@pytest.fixture
def test_caretaker_data():
    """Datos de cuidador de prueba"""
    return {
        "name": "Test Caretaker",
        "email": "caretaker@example.com",
        "password": "testpass123",
        "city": "Barcelona",
        "is_caretaker": True,
        "max_pets": 3,
        "address": "Calle Test 123",
        "phone": "+34600123456"
    }
