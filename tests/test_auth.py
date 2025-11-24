"""
Tests para endpoints de autenticación
"""
import pytest
from fastapi import status

def test_signup_success(client, clean_db):
    """Test de registro exitoso"""
    response = client.post("/auth/signup", json={
        "name": "Test User",
        "email": "newuser@example.com",
        "password": "password123",
        "city": "Madrid"
    })
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "id" in data
    assert data["email"] == "newuser@example.com"
    assert "password" not in data  # No debe exponer la contraseña

def test_signup_duplicate_email(client, clean_db):
    """Test de registro con email duplicado"""
    # Primer registro
    client.post("/auth/signup", json={
        "name": "User 1",
        "email": "duplicate@example.com",
        "password": "pass123"
    })
    
    # Segundo registro con mismo email
    response = client.post("/auth/signup", json={
        "name": "User 2",
        "email": "duplicate@example.com",
        "password": "pass456"
    })
    assert response.status_code == status.HTTP_409_CONFLICT

def test_signup_weak_password(client, clean_db):
    """Test de registro con contraseña débil"""
    response = client.post("/auth/signup", json={
        "name": "Test User",
        "email": "weak@example.com",
        "password": "123"  # Muy corta
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_signup_invalid_email(client, clean_db):
    """Test de registro con email inválido"""
    response = client.post("/auth/signup", json={
        "name": "Test User",
        "email": "not-an-email",
        "password": "password123"
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_login_success(client, clean_db):
    """Test de login exitoso"""
    # Primero crear usuario
    client.post("/auth/signup", json={
        "name": "Test User",
        "email": "login@example.com",
        "password": "password123"
    })
    
    # Luego hacer login
    response = client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "password123"
    })
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(client, clean_db):
    """Test de login con contraseña incorrecta"""
    # Crear usuario
    client.post("/auth/signup", json={
        "name": "Test User",
        "email": "wrongpass@example.com",
        "password": "correct123"
    })
    
    # Intentar login con contraseña incorrecta
    response = client.post("/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_login_nonexistent_user(client, clean_db):
    """Test de login con usuario inexistente"""
    response = client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "anypassword"
    })
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_signup_caretaker_with_phone(client, clean_db):
    """Test de registro de cuidador con teléfono válido"""
    response = client.post("/auth/signup", json={
        "name": "Test Caretaker",
        "email": "caretaker@example.com",
        "password": "password123",
        "is_caretaker": True,
        "phone": "+34600123456",
        "address": "Calle Test 123"
    })
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["is_caretaker"] is True

def test_signup_invalid_phone(client, clean_db):
    """Test de registro con teléfono inválido"""
    response = client.post("/auth/signup", json={
        "name": "Test User",
        "email": "invalidphone@example.com",
        "password": "password123",
        "phone": "123"  # Muy corto
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
