from pydantic import BaseModel, Field
from datetime import datetime

class MessageCreate(BaseModel):
    thread_id: str = Field(..., description="ID that groups messages between two users")
    sender_id: str
    receiver_id: str
    body: str

class MessageOut(BaseModel):
    id: str
    thread_id: str
    sender_id: str
    receiver_id: str
    body: str
    created_at: datetime