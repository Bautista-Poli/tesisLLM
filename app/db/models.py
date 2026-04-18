"""
Modelos de Base de Datos (SQLAlchemy)
======================================
Define las tablas principales del sistema:
  - Paciente
  - Sede
  - Turno

Usa SQLAlchemy 2.x con soporte async (asyncpg / aiosqlite).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base declarativa
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------

class EstadoTurno(str, enum.Enum):
    PENDIENTE   = "pendiente"
    CONFIRMADO  = "confirmado"
    CANCELADO   = "cancelado"
    COMPLETADO  = "completado"


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class Paciente(Base):
    """
    Representa un paciente registrado en el sistema.

    Los datos personales mínimos se capturan durante la conversación.
    El campo `whatsapp_phone` se usa como identificador de sesión.
    """
    __tablename__ = "pacientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    dni: Mapped[str] = mapped_column(
        String(10), unique=True, index=True, nullable=False
    )
    nombre: Mapped[str | None] = mapped_column(String(120), nullable=True)
    whatsapp_phone: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    obra_social: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relación con turnos
    turnos: Mapped[list["Turno"]] = relationship(
        "Turno", back_populates="paciente", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Paciente dni={self.dni} phone={self.whatsapp_phone}>"


class Sede(Base):
    """
    Sucursal física donde se realizan los turnos.
    """
    __tablename__ = "sedes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(80), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Punto de extensión: horarios, teléfono, coordenadas GPS, etc.

    turnos: Mapped[list["Turno"]] = relationship("Turno", back_populates="sede")

    def __repr__(self) -> str:
        return f"<Sede nombre={self.nombre}>"


class Turno(Base):
    """
    Turno médico agendado por un paciente en una sede.

    El campo `datos_ocr_raw` está reservado para almacenar el resultado
    crudo del módulo de OCR (ej: texto extraído de una orden médica).
    """
    __tablename__ = "turnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    paciente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pacientes.id"), nullable=False, index=True
    )
    sede_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sedes.id"), nullable=False, index=True
    )

    estudio: Mapped[str] = mapped_column(String(120), nullable=False)
    estado: Mapped[EstadoTurno] = mapped_column(
        Enum(EstadoTurno), default=EstadoTurno.PENDIENTE, nullable=False
    )

    # Campos de fecha/hora — se completan al asignar el turno real
    fecha_hora: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Trazabilidad de la conversación
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- Módulo OCR (preparado para integración futura) ---
    # Imagen de la orden médica en base64 o path en almacenamiento
    imagen_orden_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # JSON crudo devuelto por el servicio de OCR
    datos_ocr_raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relaciones
    paciente: Mapped["Paciente"] = relationship("Paciente", back_populates="turnos")
    sede: Mapped["Sede"] = relationship("Sede", back_populates="turnos")

    def __repr__(self) -> str:
        return (
            f"<Turno id={self.id} estudio={self.estudio} "
            f"estado={self.estado} fecha={self.fecha_hora}>"
        )
