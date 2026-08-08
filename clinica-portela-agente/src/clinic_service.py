"""
clinic_service.py
Responde perguntas sobre o funcionamento "em tempo real" da clínica:
está aberta agora? qual o horário hoje? amanhã é feriado?

Isso substitui frases fixas tipo "Bom dia!" por respostas que realmente
sabem a data/hora atual e o calendário da clínica.
"""

from datetime import datetime, date, time as dtime

from database import get_session
from models import ClinicCalendar
from config import HORARIO_FUNCIONAMENTO, NOME_CLINICA


def get_horario_do_dia(dia: date):
    """
    Retorna (hora_abertura, hora_fechamento) para uma data específica,
    considerando primeiro o calendário especial (feriados) e depois
    o horário padrão de funcionamento.

    Retorna None se a clínica estiver fechada nesse dia.
    """
    with get_session() as db:
        especial = db.query(ClinicCalendar).filter(ClinicCalendar.data == dia).first()
        if especial:
            if not especial.aberto:
                return None
            if especial.hora_abertura and especial.hora_fechamento:
                return (especial.hora_abertura, especial.hora_fechamento)

    weekday = dia.weekday()
    return HORARIO_FUNCIONAMENTO.get(weekday)  # None se não estiver no dict (fechado)


def is_aberta_agora(agora: datetime = None) -> bool:
    """Verifica se a clínica está aberta neste exato momento."""
    agora = agora or datetime.now()
    horario = get_horario_do_dia(agora.date())
    if not horario:
        return False
    abertura, fechamento = horario
    return abertura <= agora.time() <= fechamento


def descricao_status_atual(agora: datetime = None) -> str:
    """Gera uma frase pronta para o agente responder sobre o status da clínica."""
    agora = agora or datetime.now()
    horario = get_horario_do_dia(agora.date())

    if not horario:
        return f"A {NOME_CLINICA} está fechada hoje."

    abertura, fechamento = horario
    if abertura <= agora.time() <= fechamento:
        return (
            f"A {NOME_CLINICA} está aberta agora, até as "
            f"{fechamento.strftime('%H:%M')}."
        )
    elif agora.time() < abertura:
        return (
            f"A {NOME_CLINICA} ainda não abriu hoje. Abre às "
            f"{abertura.strftime('%H:%M')}."
        )
    else:
        return f"A {NOME_CLINICA} já fechou por hoje. Volta a abrir amanhã."


def eh_feriado_ou_fechado(dia: date) -> bool:
    return get_horario_do_dia(dia) is None


def adicionar_feriado(dia: date, descricao: str, tipo: str = "Feriado"):
    """Uso administrativo: cadastra um feriado/dia fechado no calendário."""
    with get_session() as db:
        db.add(ClinicCalendar(data=dia, tipo=tipo, descricao=descricao, aberto=False))
