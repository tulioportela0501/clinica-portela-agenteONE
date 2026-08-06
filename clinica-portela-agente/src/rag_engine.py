import os

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain

load_dotenv()

PROMPT = """
Você é o assistente virtual da Clínica Portela.

Responda SOMENTE usando o contexto abaixo.

Se a resposta não estiver no contexto, responda exatamente:

"Não encontrei essa informação em nossa base de conhecimento. Entre em contato com a recepção da Clínica Portela."

Nunca invente informações.

<context>
{context}
</context>

Pergunta:
{input}
"""


def load_agent(index_dir="index"):

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY")
    )

    vectorstore = FAISS.load_local(
        index_dir,
        embeddings,
        allow_dangerous_deserialization=True
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.2
    )

    prompt = ChatPromptTemplate.from_template(PROMPT)

    document_chain = create_stuff_documents_chain(
        llm,
        prompt
    )

    chain = create_retrieval_chain(
        retriever,
        document_chain
    )

    return chain


def answer_question(chain, question):

    try:

        response = chain.invoke(
            {
                "input": question
            }
        )

        return response["answer"]

    except Exception as e:
        import traceback
        traceback.print_exc()
        return str(e)