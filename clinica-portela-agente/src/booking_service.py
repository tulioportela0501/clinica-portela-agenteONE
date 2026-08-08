"""
booking_service.py
Núcleo do sistema de agendamento: gera horários disponíveis, cria reservas,
confirma, cancela e reagenda — sempre evitando conflito de horário.

Estratégia contra dois pacientes no mesmo horário:
1. A tabela `appointments` tem uma UniqueConstraint(professional_id, data, hora_inicio)
   -> o próprio banco recusa um segundo INSERT no mesmo slot (proteção real,
      não só validação em Python — importante se rodar mais de um processo).
2. Ao criar, o agendamento nasce com status PENDING (reserva temporária).
   Se não for confirmado em RESERVA_TEMPORARIA_MINUTOS, ele é liberado.
3. get_available_slots já exclui slots com PENDING ou CONFIRMED.
"""

from datetime import datetime, date, time, timedelta
from typing import List, Optional

from sqlalchemy.exc import IntegrityError

from database import get_session
from models import Appointment, AppointmentStatus, Patient, Service, Professional
from config import SLOT_MINUTOS, RESERVA_TEMPORARIA_MINUTOS
import clinic_service


class BookingError(Exception):
    """Erro de negócio (ex: horário indisponível, clínica fechada)."""


def _gerar_slots_do_dia(dia: date, duracao_minutos: int) -> List[time]:
    """Gera todos os horários de início possíveis no dia, respeitando
    o horário de funcionamento e a duração do serviço."""
    horario = clinic_service.get_horario_do_dia(dia)
    if not horario:
        return []

    abertura, fechamento = horario
    slots = []

    atual = datetime.combine(dia, abertura)
    fim_expediente = datetime.combine(dia, fechamento)
    duracao = timedelta(minutes=duracao_minutos)

    while atual + duracao <= fim_expediente:
        slots.append(atual.time())
        atual += timedelta(minutes=SLOT_MINUTOS)

    return slots


def _expirar_reservas_pendentes(db):
    """Libera reservas PENDING que passaram do tempo limite de confirmação."""
    limite = datetime.utcnow() - timedelta(minutes=RESERVA_TEMPORARIA_MINUTOS)
    pendentes_expirados = (
        db.query(Appointment)
        .filter(Appointment.status == AppointmentStatus.PENDING)
        .filter(Appointment.created_at < limite)
        .all()
    )
    for ag in pendentes_expirados:
        ag.status = AppointmentStatus.CANCELLED


def get_available_slots(
    service_id: int,
    date_str: str,
    professional_id: Optional[int] = None,
) -> List[str]:
    """
    Retorna lista de horários (strings "HH:MM") disponíveis para um
    serviço em uma data. Se professional_id não for passado, considera
    o primeiro profissional ativo disponível.
    """
    dia = datetime.strptime(date_str, "%Y-%m-%d").date()

    if dia < date.today():
        return []

    with get_session() as db:
        _expirar_reservas_pendentes(db)

        servico = db.query(Service).filter(Service.id == service_id, Service.ativo == True).first()  # noqa: E712
        if not servico:
            raise BookingError("Serviço não encontrado ou inativo.")

        if professional_id:
            profissionais = db.query(Professional).filter(
                Professional.id == professional_id, Professional.ativo == True  # noqa: E712
            ).all()
        else:
            profissionais = db.query(Professional).filter(Professional.ativo == True).all()  # noqa: E712

        if not profissionais:
            return []

        todos_slots_possiveis = _gerar_slots_do_dia(dia, servico.duracao_minutos)
        if not todos_slots_possiveis:
            return []

        # Horários já ocupados (PENDING ou CONFIRMED) por qualquer um dos profissionais
        ocupados = (
            db.query(Appointment.hora_inicio, Appointment.professional_id)
            .filter(Appointment.data == dia)
            .filter(Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]))
            .all()
        )
        ocupados_por_profissional = {}
        for hora, prof_id in ocupados:
            ocupados_por_profissional.setdefault(prof_id, set()).add(hora)

        disponiveis = set()
        for prof in profissionais:
            ocupados_prof = ocupados_por_profissional.get(prof.id, set())
            for slot in todos_slots_possiveis:
                if slot not in ocupados_prof:
                    disponiveis.add(slot)

        # Se for hoje, remove horários que já passaram
        if dia == date.today():
            agora = datetime.now().time()
            disponiveis = {s for s in disponiveis if s > agora}

        return sorted(h.strftime("%H:%M") for h in disponiveis)


def create_appointment(
    patient_name: str,
    patient_phone: str,
    service_id: int,
    date_str: str,
    time_str: str,
    patient_email: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    professional_id: Optional[int] = None,
) -> dict:
    """
    Cria um agendamento com status PENDING (reserva temporária).
    Levanta BookingError se o horário não estiver mais disponível.
    """
    dia = datetime.strptime(date_str, "%Y-%m-%d").date()
    hora_inicio = datetime.strptime(time_str, "%H:%M").time()

    with get_session() as db:
        _expirar_reservas_pendentes(db)

        servico = db.query(Service).filter(Service.id == service_id).first()
        if not servico:
            raise BookingError("Serviço não encontrado.")

        if not professional_id:
            profissional = db.query(Professional).filter(Professional.ativo == True).first()  # noqa: E712
            if not profissional:
                raise BookingError("Nenhum profissional disponível.")
            professional_id = profissional.id

        hora_fim = (
            datetime.combine(dia, hora_inicio) + timedelta(minutes=servico.duracao_minutos)
        ).time()

        # Busca ou cria o paciente
        paciente = None
        if telegram_chat_id:
            paciente = db.query(Patient).filter(Patient.telegram_chat_id == telegram_chat_id).first()
        if not paciente:
            paciente = Patient(
                nome=patient_name,
                telefone=patient_phone,
                email=patient_email,
                telegram_chat_id=telegram_chat_id,
            )
            db.add(paciente)
            db.flush()  # garante paciente.id disponível

        agendamento = Appointment(
            patient_id=paciente.id,
            professional_id=professional_id,
            service_id=service_id,
            data=dia,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            status=AppointmentStatus.PENDING,
        )
        db.add(agendamento)

        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise BookingError(
                "Esse horário acabou de ser reservado por outro paciente. "
                "Escolha outro horário."
            )

        return {
            "appointment_id": agendamento.id,
            "patient": paciente.nome,
            "service": servico.nome,
            "date": dia.strftime("%d/%m/%Y"),
            "time": hora_inicio.strftime("%H:%M"),
            "price": servico.preco,
            "status": agendamento.status.value,
        }


def confirm_appointment(appointment_id: int) -> dict:
    with get_session() as db:
        agendamento = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not agendamento:
            raise BookingError("Agendamento não encontrado.")
        if agendamento.status != AppointmentStatus.PENDING:
            raise BookingError(f"Este agendamento está com status '{agendamento.status.value}', não pode ser confirmado.")
        agendamento.status = AppointmentStatus.CONFIRMED
        return {"appointment_id": agendamento.id, "status": agendamento.status.value}


def cancel_appointment(appointment_id: int) -> dict:
    with get_session() as db:
        agendamento = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not agendamento:
            raise BookingError("Agendamento não encontrado.")
        agendamento.status = AppointmentStatus.CANCELLED
        return {"appointment_id": agendamento.id, "status": agendamento.status.value}


def reschedule_appointment(appointment_id: int, new_date_str: str, new_time_str: str) -> dict:
    with get_session() as db:
        agendamento = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not agendamento:
            raise BookingError("Agendamento não encontrado.")

        servico = db.query(Service).filter(Service.id == agendamento.service_id).first()
        nova_data = datetime.strptime(new_date_str, "%Y-%m-%d").date()
        nova_hora = datetime.strptime(new_time_str, "%H:%M").time()
        nova_hora_fim = (
            datetime.combine(nova_data, nova_hora) + timedelta(minutes=servico.duracao_minutos)
        ).time()

        agendamento.data = nova_data
        agendamento.hora_inicio = nova_hora
        agendamento.hora_fim = nova_hora_fim
        agendamento.status = AppointmentStatus.PENDING  # precisa reconfirmar

        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise BookingError("Esse novo horário já está ocupado. Escolha outro.")

        return {
            "appointment_id": agendamento.id,
            "date": nova_data.strftime("%d/%m/%Y"),
            "time": nova_hora.strftime("%H:%M"),
            "status": agendamento.status.value,
        }


def get_patient_appointments(telegram_chat_id: str, apenas_futuros: bool = True) -> List[dict]:
    with get_session() as db:
        paciente = db.query(Patient).filter(Patient.telegram_chat_id == telegram_chat_id).first()
        if not paciente:
            return []

        query = db.query(Appointment).filter(Appointment.patient_id == paciente.id)
        query = query.filter(Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]))
        if apenas_futuros:
            query = query.filter(Appointment.data >= date.today())

        agendamentos = query.order_by(Appointment.data, Appointment.hora_inicio).all()
        return [
            {
                "appointment_id": a.id,
                "service": a.service.nome,
                "date": a.data.strftime("%d/%m/%Y"),
                "time": a.hora_inicio.strftime("%H:%M"),
                "status": a.status.value,
            }
            for a in agendamentos
        ]
