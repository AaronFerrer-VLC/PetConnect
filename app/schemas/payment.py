from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import Optional

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
    booking_id: str
    amount: float
    payment_method: PaymentMethod = PaymentMethod.card
    
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

