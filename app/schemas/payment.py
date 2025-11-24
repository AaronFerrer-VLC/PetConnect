from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime
from typing import Optional
import re

class PaymentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"

class PaymentMethod(str, Enum):
    card = "card"
    bank_transfer = "bank_transfer"

class PaymentCreate(BaseModel):
    booking_id: str = Field(..., description="ID de la reserva a pagar")
    amount: float = Field(..., gt=0, le=10000, description="Monto a pagar (debe ser positivo y menor a 10000)")
    payment_method: PaymentMethod = Field(PaymentMethod.card, description="Método de pago")
    
    @field_validator('booking_id')
    @classmethod
    def validate_booking_id(cls, v: str) -> str:
        """Valida que el booking_id tenga formato ObjectId válido"""
        if not re.match(r'^[0-9a-fA-F]{24}$', v):
            raise ValueError("Formato de booking_id inválido")
        return v
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Valida que el monto sea razonable"""
        if v <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        if v > 10000:
            raise ValueError("El monto no puede exceder 10000")
        # Redondear a 2 decimales
        return round(v, 2)
    
    class Config:
        use_enum_values = True  # Permite usar strings directamente

class PaymentOut(BaseModel):
    id: str
    booking_id: str
    owner_id: str
    caretaker_id: str
    amount: float
    platform_fee: float
    caretaker_payout: float
    status: PaymentStatus
    payment_method: PaymentMethod
    transaction_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

