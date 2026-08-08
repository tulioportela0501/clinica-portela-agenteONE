"""
test_booking.py
Script de teste manual da Fase 2 — roda o ciclo completo de agendamento
no console, sem precisar do Telegram, e testa o cenário de conflito de
horário.

Uso (dentro de src/, com o venv ativado):
    python test_booking.py

Pode rodar quantas vezes quiser — cada execução usa um telegram_chat_id
diferente pra não confundir com testes anteriores, mas os horários que
já ficaram CONFIRMED continuam ocupados (é assim que o sistema tem que
se comportar mesmo).
"""

from datetime import date, timedelta

from booking_service import (
    get_available_slots,
    create_appointment,
    confirm_appointment,
    cancel_appointment,
    reschedule_appointment,
    get_patient_appointments,
    BookingError,
)

# Usa amanhã como data de teste, pra sempre cair num dia válido
DATA_TESTE = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
SERVICE_ID = 1  # ajuste se o serviço "Limpeza de Pele" não for o id 1


def linha(titulo):
    print("\n" + "=" * 60)
    print(titulo)
    print("=" * 60)


# 1. Paciente escolhe serviço + dia -> ver horários disponíveis
linha("1. Horários disponíveis")
slots = get_available_slots(service_id=SERVICE_ID, date_str=DATA_TESTE)
print(f"Data testada: {DATA_TESTE}")
print(f"Slots disponíveis: {slots}")

if not slots:
    print("Nenhum slot disponível nessa data — ajuste HORARIO_FUNCIONAMENTO "
          "em config.py ou escolha outro dia da semana.")
    raise SystemExit(1)

horario_escolhido = slots[0]

# 2. Paciente escolhe horário -> cria reserva temporária (PENDING)
linha("2. Criando reserva (PENDING)")
res = create_appointment(
    patient_name="Maria Silva",
    patient_phone="98999999999",
    service_id=SERVICE_ID,
    date_str=DATA_TESTE,
    time_str=horario_escolhido,
    telegram_chat_id="teste-123",
)
print(res)

# 3. Paciente confirma -> CONFIRMED
linha("3. Confirmando agendamento")
confirmado = confirm_appointment(res["appointment_id"])
print(confirmado)

# 4. Cenário de conflito: tentar marcar OUTRO paciente no mesmo horário
linha("4. Testando conflito de horário (deve dar erro)")
try:
    create_appointment(
        patient_name="João Souza",
        patient_phone="98988888888",
        service_id=SERVICE_ID,
        date_str=DATA_TESTE,
        time_str=horario_escolhido,
        telegram_chat_id="teste-456",
    )
    print("ERRO: não deveria ter permitido o conflito!")
except BookingError as e:
    print(f"OK, bloqueado corretamente: {e}")

# 5. Consultar agendamentos do paciente
linha("5. Consultando agendamentos da Maria")
print(get_patient_appointments("teste-123"))

# 6. Reagendar
linha("6. Reagendando para outro horário")
if len(slots) > 1:
    novo_horario = slots[1]
    reagendado = reschedule_appointment(
        res["appointment_id"], DATA_TESTE, novo_horario
    )
    print(reagendado)
else:
    print("Só havia 1 slot livre, pulando teste de reagendamento.")

# 7. Cancelar
linha("7. Cancelando agendamento")
cancelado = cancel_appointment(res["appointment_id"])
print(cancelado)

linha("8. Agendamentos da Maria depois do cancelamento (deve vir vazio)")
print(get_patient_appointments("teste-123"))

print("\nTeste concluído.")
