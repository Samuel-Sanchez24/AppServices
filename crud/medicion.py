from sqlalchemy.orm import Session
from models.medicion import Medicion

def listar(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Medicion).order_by(Medicion.id).offset(skip).limit(limit).all()

def obtener(db: Session, medicion_id: int):
    return db.get(Medicion, medicion_id)

def crear(db: Session, data):
    obj = Medicion(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def actualizar(db: Session, obj, data):
    # ninguna columna admite NULL, por eso también se excluyen los None
    for campo, valor in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(obj, campo, valor)
    db.commit(); db.refresh(obj)
    return obj

def eliminar(db: Session, obj):
    db.delete(obj); db.commit()