import os
import traceback

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain

load_dotenv()

PROMPT = """
Você é o assistente virtual da Clínica Portela.

Sua função é responder dúvidas dos pacientes utilizando APENAS as informações
presentes no contexto abaixo.

Se a resposta não estiver no contexto, responda exatamente:

"Não encontrei essa informação em nossa base de conhecimento. Entre em contato com a recepção da Clínica Portela."

Nunca invente informações, horários, preços, convênios ou procedimentos.

Responda sempre em português, de forma clara, educada e objetiva.

=========================
CONTEXTO
=========================
{context}

=========================
PERGUNTA
=========================
{input}

=========================
RESPOSTA
=========================
"""


def load_agent(index_dir="index"):
    """
    Carrega o índice FAISS e cria a cadeia RAG.
    """

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY não encontrada no arquivo .env"
        )

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=api_key
    )

    vectorstore = FAISS.load_local(
        index_dir,
        embeddings,
        allow_dangerous_deserialization=True
    )

    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 4
        }
    )

    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        api_key=api_key,
        temperature=0.2
    )

    prompt = ChatPromptTemplate.from_template(PROMPT)

    document_chain = create_stuff_documents_chain(
        llm=llm,
        prompt=prompt
    )

    chain = create_retrieval_chain(
        retriever=retriever,
        combine_docs_chain=document_chain
    )

    return chain


def answer_question(chain, question: str) -> str:
    """
    Processa uma pergunta utilizando o RAG.
    """

    try:

        response = chain.invoke(
            {
                "input": question
            }
        )

        return response["answer"]

    except Exception:
        traceback.print_exc()

        return (
            "Desculpe, ocorreu um erro ao processar sua pergunta. "
            "Tente novamente em alguns instantes."
        )