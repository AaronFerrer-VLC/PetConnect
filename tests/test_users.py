# tests/test_users.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_create_and_list_users():
    transport = ASGITransport(app=app)  # 👈 transporte ASGI para FastAPI
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Crear usuario
        resp = await ac.post("/users", json={
            "name": "Ana",
            "email": "ana@test.com",
            "city": "Madrid",
            "is_caretaker": True
        })
        assert resp.status_code == 201

        # Listar
        resp = await ac.get("/users")
        assert resp.status_code == 200
        assert any(u["email"] == "ana@test.com" for u in resp.json())

