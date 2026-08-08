"""
config.py
Configurações centrais do Agente da Clínica Portela.
Carrega variáveis de ambiente e define constantes usadas
pelos demais módulos (database, booking, pricing, clinic).
"""

import os
from datetime import time
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Telegram / OpenAI
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")

# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
# Fase 1-5: SQLite local. Fase 6: trocar por PostgreSQL/MySQL só mudando essa
# string de conexão (SQLAlchemy abstrai o resto).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/clinica.db")

# ---------------------------------------------------------------------------
# Horário de funcionamento da clínica
# ---------------------------------------------------------------------------
# 0 = segunda, 6 = domingo (padrão Python weekday())
HORARIO_FUNCIONAMENTO = {
    0: (time(8, 0), time(18, 0)),   # segunda
    1: (time(8, 0), time(18, 0)),   # terça
    2: (time(8, 0), time(18, 0)),   # quarta
    3: (time(8, 0), time(18, 0)),   # quinta
    4: (time(8, 0), time(18, 0)),   # sexta
    5: (time(8, 0), time(12, 0)),   # sábado
    # domingo fechado -> não incluir a chave 6
}

# Duração padrão do "slot" de agenda em minutos (granularidade da grade
# de horários). Serviços mais longos ocupam mais de um slot.
SLOT_MINUTOS = 30

# Tempo (em minutos) que um horário fica "reservado temporariamente"
# enquanto o paciente está confirmando os dados, antes de expirar.
RESERVA_TEMPORARIA_MINUTOS = 10

NOME_CLINICA = "Clínica Portela"
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")
