from pydantic import BaseModel
from typing import Optional, List

class SitterCard(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    photo: Optional[str] = None
    services: List[str] = []
    min_price: Optional[float] = None
    rating_avg: Optional[float] = None
    rating_count: Optional[int] = None
    accepts_sizes: List[str] = []
    has_yard: Optional[bool] = None
