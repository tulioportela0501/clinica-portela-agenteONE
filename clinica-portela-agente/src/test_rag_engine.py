"""
test_rag_engine.py
Testa o roteador de intenção (rag_engine.py) isolado, sem Telegram.

Uso (dentro de src/, com o venv ativado):
    python test_rag_engine.py

Testa 3 tipos de pergunta pra ver se o roteamento está funcionando:
1. Pergunta de preço -> deve chamar consultar_preco / listar_servicos
2. Pergunta de horário -> deve chamar listar_servicos + consultar_horarios
3. Pergunta de conhecimento -> deve chamar consultar_rag (usa seus documentos)
"""

from datetime import date, timedelta

import rag_engine

print("Carregando agente (isso pode levar alguns segundos)...")
agent = rag_engine.load_agent()
print("Agente carregado.\n")

CHAT_ID_TESTE = "teste-rag-001"
DATA_TESTE = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")


def perguntar(pergunta, historico=None):
    print(f"\n>>> PACIENTE: {pergunta}")
    resposta = rag_engine.answer_question(
        agent, pergunta, telegram_chat_id=CHAT_ID_TESTE, historico=historico
    )
    print(f"<<< AGENTE: {resposta}")
    return resposta


# 1. Pergunta de preço
perguntar("Quanto custa a limpeza de pele?")

# 2. Pergunta de horário (o modelo deve descobrir o service_id sozinho)
perguntar(f"Tem horário disponível para limpeza de pele amanhã ({DATA_TESTE})?")

# 3. Pergunta que deveria ir pro RAG (ajuste para algo que exista nos seus documentos)
perguntar("Quais são os cuidados após o procedimento?")

print("\nTeste concluído.")
