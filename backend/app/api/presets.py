from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Preset
from app.db.session import get_db
from app.schemas import PresetOut

router = APIRouter()


@router.get("/presets", response_model=list[PresetOut])
def list_presets(db: Session = Depends(get_db)):
    return db.scalars(select(Preset).order_by(Preset.id)).all()
