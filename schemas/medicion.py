from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class MedicionCreate(BaseModel):
    estudiante_id: int
    variable: str = Field(min_length=1, max_length=50)
    valor: float
    unidad: str = Field(min_length=1, max_length=20)
    fecha_hora: datetime

class MedicionUpdate(BaseModel):
    estudiante_id: Optional[int] = None
    variable: Optional[str] = Field(None, min_length=1, max_length=50)
    valor: Optional[float] = None
    unidad: Optional[str] = Field(None, min_length=1, max_length=20)
    fecha_hora: Optional[datetime] = None

class MedicionResponse(MedicionCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)