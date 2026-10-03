from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.estudiante import Estudiante
from schemas.medicion import MedicionCreate, MedicionUpdate, MedicionResponse
from crud import medicion as crud_medicion

router = APIRouter(prefix="/mediciones", tags=["Mediciones"])

def _get_or_404(db, medicion_id):
    obj = crud_medicion.obtener(db, medicion_id)
    if not obj:
        raise HTTPException(404, "Medición no encontrada")
    return obj

def _check_estudiante(db, estudiante_id):
    if not db.get(Estudiante, estudiante_id):
        raise HTTPException(404, "Estudiante no existe")

@router.get("", response_model=list[MedicionResponse])
def listar(db: Session = Depends(get_db)):
    return crud_medicion.listar(db)

@router.get("/{medicion_id}", response_model=MedicionResponse)
def consultar(medicion_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, medicion_id)

@router.post("", response_model=MedicionResponse, status_code=201)
def crear(data: MedicionCreate, db: Session = Depends(get_db)):
    _check_estudiante(db, data.estudiante_id)
    return crud_medicion.crear(db, data)

@router.patch("/{medicion_id}", response_model=MedicionResponse)
def actualizar(medicion_id: int, data: MedicionUpdate, db: Session = Depends(get_db)):
    obj = _get_or_404(db, medicion_id)
    if data.estudiante_id is not None:
        _check_estudiante(db, data.estudiante_id)
    return crud_medicion.actualizar(db, obj, data)

@router.delete("/{medicion_id}", status_code=204)
def eliminar(medicion_id: int, db: Session = Depends(get_db)):
    crud_medicion.eliminar(db, _get_or_404(db, medicion_id))