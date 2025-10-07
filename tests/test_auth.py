import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_signup_login_and_me():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # signup
        r = await ac.post("/auth/signup", json={
            "name":"Test User","email":"test@login.com","password":"abc12345","is_caretaker":False
        })
        assert r.status_code == 201

        # login
        r = await ac.post("/auth/login", json={"email":"test@login.com","password":"abc12345"})
        assert r.status_code == 200
        token = r.json()["access_token"]

        # me
        r = await ac.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "test@login.com"
