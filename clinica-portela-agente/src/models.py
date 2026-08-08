"""
models.py
Definição das tabelas do banco de dados (SQLAlchemy ORM).

Tabelas:
- Patient        -> pacientes
- Professional    -> profissionais da clínica
- Service         -> serviços/procedimentos e valores
- Appointment     -> agendamentos
- ClinicCalendar  -> feriados e dias especiais (fechado/horário diferente)
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Time,
    ForeignKey, Enum, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"       # reservado temporariamente, aguardando confirmação
    CONFIRMED = "CONFIRMED"   # confirmado pelo paciente
    CANCELLED = "CANCELLED"   # cancelado
    COMPLETED = "COMPLETED"   # atendimento realizado
    NO_SHOW = "NO_SHOW"       # paciente não compareceu


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    nome = Column(String(150), nullable=False)
    telefone = Column(String(30), nullable=False)
    email = Column(String(150), nullable=True)
    telegram_chat_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointments = relationship("Appointment", back_populates="patient")


class Professional(Base):
    __tablename__ = "professionals"

    id = Column(Integer, primary_key=True)
    nome = Column(String(150), nullable=False)
    especialidade = Column(String(150), nullable=True)
    ativo = Column(Boolean, default=True)

    appointments = relationship("Appointment", back_populates="professional")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    duracao_minutos = Column(Integer, nullable=False, default=60)
    preco = Column(Float, nullable=False)
    ativo = Column(Boolean, default=True)

    appointments = relationship("Appointment", back_populates="service")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # Impede dois agendamentos ativos no mesmo profissional/data/hora.
        UniqueConstraint(
            "professional_id", "data", "hora_inicio",
            name="uq_professional_slot"
        ),
    )

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    professional_id = Column(Integer, ForeignKey("professionals.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)

    data = Column(Date, nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fim = Column(Time, nullable=False)

    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="appointments")
    professional = relationship("Professional", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")


class ClinicCalendar(Base):
    __tablename__ = "clinic_calendar"

    id = Column(Integer, primary_key=True)
    data = Column(Date, nullable=False, unique=True)
    tipo = Column(String(50), nullable=False)       # ex: "Feriado", "Recesso"
    descricao = Column(String(200), nullable=True)
    aberto = Column(Boolean, default=False)
    hora_abertura = Column(Time, nullable=True)      # se aberto=True e horário especial
    hora_fechamento = Column(Time, nullable=True)
