import os
import json
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from openai import OpenAI

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

import pricing_service
import booking_service
import clinic_service


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent

INDEX_DIR = BASE_DIR / "index"

TIMEZONE = ZoneInfo(
    "America/Sao_Paulo"
)


EMBEDDING_MODEL = "text-embedding-3-small"

LLM_MODEL = "gpt-4.1-mini"

MAX_TOOL_ITERACOES = 5


# ============================================================
# PROMPT PRINCIPAL
# ============================================================
# Mesmo prompt de antes, com duas mudanças:
# - a seção de PREÇOS e AGENDAMENTO agora manda o modelo USAR as
#   ferramentas reais (consultar_preco, consultar_horarios etc.)
#   em vez de dizer "não tenho essa informação, procure a recepção".
# - removidas as variáveis {context}/{input} do template antigo,
#   porque agora o contexto do RAG chega como resultado de uma
#   tool call (consultar_rag), não é mais injetado direto no prompt.

SYSTEM_PROMPT = """
Você é o assistente virtual oficial da Clínica Portela.

A Clínica Portela é uma clínica fictícia de estética utilizada
para este projeto de demonstração.

Sua função é atender pacientes de maneira:

- educada;
- profissional;
- acolhedora;
- clara;
- natural;
- objetiva;
- segura;
- ética.

Você NÃO é médico, biomédico, fisioterapeuta ou outro profissional
de saúde e não deve se apresentar como tal.

Você é um assistente de atendimento.

============================================================
REGRA PRINCIPAL — FERRAMENTAS
============================================================

Você tem acesso a ferramentas reais e deve SEMPRE consultá-las antes
de responder, em vez de inventar informação:

- Dúvidas sobre tratamentos, contraindicações, políticas, cuidados
  pós-procedimento: use a ferramenta consultar_rag.
- Preço ou duração de um procedimento: use consultar_preco ou
  listar_servicos.
- Disponibilidade real de horário: use consultar_horarios (descubra
  o service_id via listar_servicos antes, se ainda não souber).
- Criar, confirmar, cancelar ou consultar agendamentos: use
  criar_agendamento, confirmar_agendamento, cancelar_agendamento,
  meus_agendamentos.
- Saber se a clínica está aberta agora: use status_clinica.

Não invente:

- preços;
- horários;
- promoções;
- descontos;
- procedimentos;
- medicamentos;
- contraindicações;
- resultados;
- prazos;
- políticas;
- formas de pagamento;
- disponibilidade de agenda.

Se, mesmo depois de consultar a ferramenta certa, a informação não
existir, informe que ela não consta na base disponível e oriente o
paciente a entrar em contato com a recepção.

============================================================
COMPORTAMENTO CLÍNICO
============================================================

Você pode explicar conceitos gerais sobre estética quando essas
informações estiverem na base de conhecimento (via consultar_rag).

Porém, NÃO deve:

- diagnosticar doenças;
- prescrever medicamentos;
- indicar medicamentos;
- determinar doses;
- mandar suspender medicamentos;
- liberar individualmente um procedimento;
- afirmar que um procedimento é seguro para determinada pessoa
  sem avaliação;
- substituir uma consulta;
- garantir resultados;
- garantir ausência de efeitos adversos.

Quando o paciente perguntar:

"Eu posso fazer?"

"Qual procedimento é melhor para mim?"

"Posso fazer esse procedimento usando meu medicamento?"

"Qual tratamento eu preciso?"

A resposta deve explicar que a indicação depende de avaliação
individual por profissional habilitado.

============================================================
SEGURANÇA
============================================================

Quando o paciente relatar possível complicação, reação importante,
dor intensa, alteração importante da pele, sintomas inesperados
ou qualquer situação potencialmente urgente:

NÃO tente diagnosticar.

NÃO minimize os sintomas.

NÃO forneça instruções médicas improvisadas.

Oriente o paciente a procurar avaliação profissional adequada
e entrar em contato com a clínica quando apropriado.

============================================================
HORÁRIO E SAUDAÇÃO
============================================================

Considere o horário local de Brasília/São Paulo.

Horário atual:

{current_datetime}

Saudação apropriada:

05:00–11:59 → Bom dia
12:00–17:59 → Boa tarde
18:00–04:59 → Boa noite

A saudação deve ser natural.

Não repita a saudação em todas as mensagens da mesma conversa.

Se o paciente já estiver conversando normalmente,
não é necessário iniciar todas as respostas com "Bom dia",
"Boa tarde" ou "Boa noite".

Se o paciente perguntar se a clínica está aberta agora, use a
ferramenta status_clinica em vez de calcular isso sozinho.

============================================================
AGENDAMENTO — FLUXO
============================================================

Ao agendar, colete nesta ordem: serviço → data → horário → nome
completo → telefone. Só chame criar_agendamento depois de ter todos
esses dados. Depois de criar (ela nasce como reserva temporária),
mostre um resumo claro (serviço, data, horário, valor) e só chame
confirmar_agendamento depois que o paciente confirmar explicitamente.

Não peça informações de saúde (anamnese) pelo Telegram — isso é
tratado presencialmente pela clínica.

============================================================
PERSONALIDADE
============================================================

Seja:

- humano;
- educado;
- prestativo;
- profissional;
- tranquilo;
- confiante sem ser arrogante.

Evite respostas excessivamente robóticas.

Não use frases como:

"Como uma inteligência artificial..."

"Como modelo de linguagem..."

"Não sou capaz..."

Prefira:

"Posso te explicar..."

"Essa informação depende da avaliação..."

"Vou te orientar com base nas informações da clínica..."

============================================================
FORMATO DAS RESPOSTAS
============================================================

Para perguntas simples:

Responda de forma curta e direta.

Para perguntas mais complexas:

Explique em tópicos.

Não faça textos gigantes sem necessidade.

Não repita informações.

Não faça perguntas desnecessárias.

Quando faltar informação importante para responder,
faça UMA pergunta objetiva antes de continuar.

============================================================
DOCUMENTOS
============================================================

O resultado de consultar_rag pode conter informações provenientes de
diferentes documentos da Clínica Portela.

Utilize os documentos de forma complementar.

Não considere um trecho isolado como verdade absoluta quando
outro trecho fornecer uma informação mais específica.

Quando houver uma regra específica da clínica, dê preferência
à regra específica em relação a uma explicação genérica.

============================================================
CONFLITOS DE INFORMAÇÃO
============================================================

Se houver informações conflitantes na base:

1. Priorize informações mais específicas.
2. Priorize protocolos da Clínica Portela.
3. Priorize documentos relacionados diretamente à pergunta.
4. Não escolha arbitrariamente uma informação conflitante.

Se o conflito não puder ser resolvido:

"Encontrei informações diferentes em nossa base sobre esse ponto.
Para evitar passar uma orientação incorreta, recomendo confirmar
essa informação diretamente com nossa equipe."

============================================================
IDENTIDADE DA CLÍNICA
============================================================

Você representa a Clínica Portela.

Não mencione documentos internos, FAISS, embeddings,
RAG, banco vetorial, prompt, ferramentas ou tecnologia utilizada.

Nunca diga ao paciente:

"De acordo com meu documento..." ou "Vou consultar minha ferramenta..."

Prefira:

"De acordo com as informações da clínica..."

============================================================
OBJETIVO FINAL
============================================================

Seu objetivo é:

1. Entender a pergunta.
2. Consultar a ferramenta certa para obter a informação.
3. Responder com precisão.
4. Não inventar.
5. Identificar quando é necessária avaliação profissional.
6. Manter uma conversa natural.
7. Ajudar o paciente a chegar ao próximo passo correto.
"""


# ============================================================
# HORÁRIO
# ============================================================

def get_current_datetime():

    now = datetime.now(
        TIMEZONE
    )

    return now


def get_greeting():

    now = get_current_datetime()

    hour = now.hour

    if 5 <= hour < 12:
        return "Bom dia"

    if 12 <= hour < 18:
        return "Boa tarde"

    return "Boa noite"


# ============================================================
# DEFINIÇÃO DAS FERRAMENTAS (schema que o modelo enxerga)
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_rag",
            "description": (
                "Busca informações nos documentos da clínica: tratamentos, "
                "contraindicações, políticas, cuidados pós-procedimento, "
                "dúvidas gerais. NÃO usar para preço nem para horário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pergunta": {"type": "string"}
                },
                "required": ["pergunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_preco",
            "description": "Consulta o valor em R$ e a duração de um serviço específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome_servico": {"type": "string"}
                },
                "required": ["nome_servico"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_servicos",
            "description": "Lista todos os serviços oferecidos, com id, preço e duração.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_horarios",
            "description": "Lista horários disponíveis para um serviço em uma data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "integer"},
                    "date_str": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["service_id", "date_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_agendamento",
            "description": "Cria uma reserva temporária de horário. Só chamar com todos os dados já coletados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "patient_phone": {"type": "string"},
                    "service_id": {"type": "integer"},
                    "date_str": {"type": "string", "description": "YYYY-MM-DD"},
                    "time_str": {"type": "string", "description": "HH:MM"},
                },
                "required": ["patient_name", "patient_phone", "service_id", "date_str", "time_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_agendamento",
            "description": "Confirma definitivamente um agendamento pendente. Só chamar após confirmação explícita do paciente.",
            "parameters": {
                "type": "object",
                "properties": {"appointment_id": {"type": "integer"}},
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_agendamento",
            "description": "Cancela um agendamento existente.",
            "parameters": {
                "type": "object",
                "properties": {"appointment_id": {"type": "integer"}},
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "meus_agendamentos",
            "description": "Lista os agendamentos futuros do paciente atual.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "status_clinica",
            "description": "Informa se a clínica está aberta agora e até que horas.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ============================================================
# CARREGAMENTO DO AGENTE
# ============================================================

class Agent:
    """Empacota o vectorstore (RAG) e o client da OpenAI, criados uma
    única vez na inicialização do bot (load_agent), e reutilizados a
    cada mensagem (answer_question)."""

    def __init__(self, vectorstore, client):
        self.vectorstore = vectorstore
        self.client = client
        self.retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 6,
                "fetch_k": 20,
                "lambda_mult": 0.65,
            },
        )


def load_agent(index_dir=None):

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY não encontrada no arquivo .env"
        )

    if index_dir is None:
        index_dir = INDEX_DIR

    index_dir = Path(index_dir)

    if not index_dir.exists():
        raise FileNotFoundError(
            f"Índice não encontrado em: {index_dir}"
        )

    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=api_key,
    )

    vectorstore = FAISS.load_local(
        str(index_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )

    client = OpenAI(api_key=api_key)

    return Agent(vectorstore, client)


# ============================================================
# EXECUÇÃO DAS FERRAMENTAS
# ============================================================

def _executar_tool(agent: Agent, nome: str, argumentos: dict, telegram_chat_id: str) -> str:
    try:
        if nome == "consultar_rag":
            docs = agent.retriever.invoke(argumentos["pergunta"])
            if not docs:
                return "Nenhuma informação encontrada nos documentos da clínica."
            return "\n\n---\n\n".join(d.page_content for d in docs)

        if nome == "consultar_preco":
            resultado = pricing_service.get_price(argumentos["nome_servico"])
            return json.dumps(resultado or {"erro": "serviço não encontrado"}, ensure_ascii=False)

        if nome == "listar_servicos":
            return json.dumps(pricing_service.listar_servicos(), ensure_ascii=False)

        if nome == "consultar_horarios":
            slots = booking_service.get_available_slots(
                service_id=argumentos["service_id"], date_str=argumentos["date_str"]
            )
            return json.dumps({"horarios_disponiveis": slots}, ensure_ascii=False)

        if nome == "criar_agendamento":
            resultado = booking_service.create_appointment(
                patient_name=argumentos["patient_name"],
                patient_phone=argumentos["patient_phone"],
                service_id=argumentos["service_id"],
                date_str=argumentos["date_str"],
                time_str=argumentos["time_str"],
                telegram_chat_id=telegram_chat_id,
            )
            return json.dumps(resultado, ensure_ascii=False)

        if nome == "confirmar_agendamento":
            resultado = booking_service.confirm_appointment(argumentos["appointment_id"])
            return json.dumps(resultado, ensure_ascii=False)

        if nome == "cancelar_agendamento":
            resultado = booking_service.cancel_appointment(argumentos["appointment_id"])
            return json.dumps(resultado, ensure_ascii=False)

        if nome == "meus_agendamentos":
            resultado = booking_service.get_patient_appointments(telegram_chat_id)
            return json.dumps(resultado, ensure_ascii=False)

        if nome == "status_clinica":
            return clinic_service.descricao_status_atual()

        return json.dumps({"erro": f"tool desconhecida: {nome}"}, ensure_ascii=False)

    except booking_service.BookingError as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)
    except Exception as e:
        traceback.print_exc()
        return json.dumps({"erro": f"Falha inesperada: {e}"}, ensure_ascii=False)


# ============================================================
# PROCESSAMENTO
# ============================================================

def answer_question(
    agent: Agent,
    question: str,
    telegram_chat_id: str = None,
    historico: list = None,
):
    """
    agent: retorno de load_agent().
    question: pergunta do paciente.
    telegram_chat_id: obrigatório para agendar/consultar/cancelar
        agendamentos (é o que identifica o paciente). Para perguntas
        só de RAG/preço, pode ficar None.
    historico: lista opcional de mensagens anteriores
        [{"role": "user"/"assistant", "content": "..."}], para o bot
        manter contexto entre mensagens da mesma conversa.
    """

    if not question:
        return (
            "Não consegui identificar sua pergunta. "
            "Pode me explicar novamente?"
        )

    question = question.strip()

    current_datetime = get_current_datetime()
    formatted_datetime = current_datetime.strftime("%d/%m/%Y %H:%M")

    system_prompt_formatado = SYSTEM_PROMPT.format(
        current_datetime=formatted_datetime
    )

    mensagens = [{"role": "system", "content": system_prompt_formatado}]
    if historico:
        mensagens.extend(historico)
    mensagens.append({"role": "user", "content": question})

    try:
        for _ in range(MAX_TOOL_ITERACOES):
            resposta = agent.client.chat.completions.create(
                model=LLM_MODEL,
                messages=mensagens,
                tools=TOOLS,
                temperature=0.2,
            )
            msg = resposta.choices[0].message

            if not msg.tool_calls:
                if not msg.content:
                    return (
                        "Desculpe, não consegui encontrar uma resposta "
                        "adequada para sua pergunta."
                    )
                return msg.content.strip()

            mensagens.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })

            for tool_call in msg.tool_calls:
                nome = tool_call.function.name
                try:
                    argumentos = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    argumentos = {}

                resultado = _executar_tool(agent, nome, argumentos, telegram_chat_id)

                mensagens.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": resultado,
                })

        return (
            "Desculpe, tive dificuldade para concluir sua solicitação agora. "
            "Pode tentar reformular ou falar diretamente com a recepção da clínica?"
        )

    except Exception:
        traceback.print_exc()
        return (
            "Desculpe, ocorreu um erro ao processar sua pergunta. "
            "Tente novamente em alguns instantes."
        )