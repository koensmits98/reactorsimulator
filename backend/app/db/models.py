import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Preset(Base):
    __tablename__ = "presets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text)
    # A ready-to-use body for POST /api/simulations.
    parameters: Mapped[dict] = mapped_column(JSONB)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    # UUIDs are unguessable, so the id is safe to use in a shareable link.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    parameters: Mapped[dict] = mapped_column(JSONB)
    results: Mapped[dict] = mapped_column(JSONB)  # downsampled times, power, precursors
    peak_power: Mapped[float] = mapped_column(Float)
    final_power: Mapped[float] = mapped_column(Float)
