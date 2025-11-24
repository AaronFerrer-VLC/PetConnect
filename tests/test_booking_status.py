import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta
from app.main import app

# Deshabilitar rate limiting en la app para tests
app.state.limiter = None

@pytest.mark.asyncio
async def test_booking_status_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Crear owner y caretaker
        r = await ac.post("/users", json={"name":"Owner","email":"owner@ex.com","is_caretaker":False})
        owner = r.json(); owner_id = owner["id"]
        r = await ac.post("/users", json={"name":"Caretaker","email":"ct@ex.com","is_caretaker":True})
        caretaker = r.json(); caretaker_id = caretaker["id"]

        # Mascota del owner
        r = await ac.post("/pets", json={"name":"Luna","species":"perro","owner_id": owner_id})
        pet_id = r.json()["id"]

        # Servicio del caretaker
        r = await ac.post("/services", json={"caretaker_id": caretaker_id,"title":"Paseos","price_per_hour":12})
        service_id = r.json()["id"]

        # Reserva
        now = datetime.utcnow()
        r = await ac.post("/bookings", json={
            "owner_id": owner_id,
            "caretaker_id": caretaker_id,
            "service_id": service_id,
            "pet_id": pet_id,
            "start": (now + timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=2)).isoformat()
        })
        booking = r.json(); booking_id = booking["id"]
        assert booking["status"] == "pending"

        # Aceptar
        r = await ac.patch(f"/bookings/{booking_id}/status", json={"status":"accepted"})
        assert r.status_code == 200 and r.json()["status"] == "accepted"

        # Completar
        r = await ac.patch(f"/bookings/{booking_id}/status", json={"status":"completed"})
        assert r.status_code == 200 and r.json()["status"] == "completed"
