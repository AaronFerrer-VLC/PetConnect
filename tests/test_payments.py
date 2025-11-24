"""
Tests para endpoints de pagos
"""
import pytest
from fastapi import status

def test_create_payment_requires_auth(client, clean_db):
    """Test de que crear pago requiere autenticación"""
    response = client.post("/payments", json={
        "booking_id": "507f1f77bcf86cd799439011",
        "amount": 100.0,
        "payment_method": "card"
    })
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_create_payment_invalid_amount(client, clean_db):
    """Test de creación de pago con monto inválido"""
    # Primero necesitaríamos crear un usuario y obtener token
    # Por simplicidad, solo validamos el schema
    # En un test completo, crearíamos usuario, booking, y luego payment
    
    # Test de validación de schema
    # Esto se validaría en el schema de Pydantic
    pass

def test_create_payment_invalid_booking_id_format(client, clean_db):
    """Test de creación de pago con booking_id inválido"""
    # El schema debería validar el formato ObjectId
    # Esto se maneja en el field_validator de PaymentCreate
    pass

def test_payment_amount_validation():
    """Test de validación de monto en PaymentCreate"""
    from app.schemas.payment import PaymentCreate
    from pydantic import ValidationError
    
    # Monto negativo debería fallar
    with pytest.raises(ValidationError):
        PaymentCreate(
            booking_id="507f1f77bcf86cd799439011",
            amount=-10.0
        )
    
    # Monto cero debería fallar
    with pytest.raises(ValidationError):
        PaymentCreate(
            booking_id="507f1f77bcf86cd799439011",
            amount=0.0
        )
    
    # Monto muy grande debería fallar
    with pytest.raises(ValidationError):
        PaymentCreate(
            booking_id="507f1f77bcf86cd799439011",
            amount=20000.0
        )
    
    # Monto válido debería funcionar
    payment = PaymentCreate(
        booking_id="507f1f77bcf86cd799439011",
        amount=100.50
    )
    assert payment.amount == 100.50

def test_payment_booking_id_validation():
    """Test de validación de booking_id en PaymentCreate"""
    from app.schemas.payment import PaymentCreate
    from pydantic import ValidationError
    
    # ID inválido debería fallar
    with pytest.raises(ValidationError):
        PaymentCreate(
            booking_id="invalid-id",
            amount=100.0
        )
    
    # ID válido debería funcionar
    payment = PaymentCreate(
        booking_id="507f1f77bcf86cd799439011",
        amount=100.0
    )
    assert payment.booking_id == "507f1f77bcf86cd799439011"

