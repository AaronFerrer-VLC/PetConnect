# app/routers/dev.py
# Endpoint de desarrollo para crear datos de prueba
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timedelta
from ..db import get_db
from ..security import hash_password
from ..utils import geocode_city

router = APIRouter()

@router.post("/seed-data")
async def seed_data(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Crea datos de prueba: cuidadores, servicios, etc.
    Solo para desarrollo.
    """
    # Crear cuidadores de prueba
    caretakers_data = [
        {
            "name": "María García",
            "email": "maria@test.com",
            "password_hash": hash_password("abc12345"),
            "city": "Madrid",
            "is_caretaker": True,
            "plan": "free",
            "profile": {
                "city": "Madrid",
                "bio": "Amante de los animales con 5 años de experiencia cuidando perros y gatos.",
                "accepts_sizes": ["small", "medium", "large"],
                "has_yard": True,
            },
            "availability": {
                "max_pets": 2,
                "blocked_dates": [],
                "weekly_open": {k: True for k in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]},
            },
            "gallery": [],
        },
        {
            "name": "Juan Pérez",
            "email": "juan@test.com",
            "password_hash": hash_password("abc12345"),
            "city": "Barcelona",
            "is_caretaker": True,
            "plan": "pro",
            "profile": {
                "city": "Barcelona",
                "bio": "Cuidador profesional especializado en perros grandes.",
                "accepts_sizes": ["large", "giant"],
                "has_yard": False,
            },
            "availability": {
                "max_pets": 1,
                "blocked_dates": [],
                "weekly_open": {k: True for k in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]},
            },
            "gallery": [],
        },
        {
            "name": "Ana López",
            "email": "ana@test.com",
            "password_hash": hash_password("abc12345"),
            "city": "Valencia",
            "is_caretaker": True,
            "plan": "free",
            "profile": {
                "city": "Valencia",
                "bio": "Veterinaria de profesión, cuido mascotas con mucho cariño.",
                "accepts_sizes": ["small", "medium"],
                "has_yard": True,
            },
            "availability": {
                "max_pets": 3,
                "blocked_dates": [],
                "weekly_open": {k: True for k in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]},
            },
            "gallery": [],
        },
    ]

    created_caretakers = []
    for caretaker_data in caretakers_data:
        # Verificar si ya existe
        existing = await db.users.find_one({"email": caretaker_data["email"]})
        if existing:
            created_caretakers.append(str(existing["_id"]))
            continue

        # Geocodificar ciudad
        coords = geocode_city(caretaker_data["city"])
        if coords:
            caretaker_data["lat"] = coords[0]
            caretaker_data["lng"] = coords[1]

        res = await db.users.insert_one(caretaker_data)
        created_caretakers.append(str(res.inserted_id))

    # Crear servicios para los cuidadores
    services_data = []
    for caretaker_id in created_caretakers:
        caretaker = await db.users.find_one({"_id": ObjectId(caretaker_id)})
        if not caretaker:
            continue

        # Servicios para cada cuidador
        caretaker_services = [
            {
                "caretaker_id": caretaker_id,
                "type": "boarding",
                "price": 25.0,
                "description": "Alojamiento nocturno con paseos incluidos",
                "enabled": True,
            },
            {
                "caretaker_id": caretaker_id,
                "type": "daycare",
                "price": 15.0,
                "description": "Guardería de día",
                "enabled": True,
            },
            {
                "caretaker_id": caretaker_id,
                "type": "walking",
                "price": 10.0,
                "description": "Paseo de 30 minutos",
                "enabled": True,
            },
        ]

        for service in caretaker_services:
            # Verificar si ya existe
            existing = await db.services.find_one({
                "caretaker_id": caretaker_id,
                "type": service["type"],
            })
            if not existing:
                await db.services.insert_one(service)

    return {
        "message": "Datos de prueba creados",
        "caretakers_created": len(created_caretakers),
        "caretaker_ids": created_caretakers,
    }

