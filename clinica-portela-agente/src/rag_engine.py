import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

PROMPT_TEMPLATE = """Você é o assistente virtual da Clínica Portela.
Responda à pergunta do paciente usando APENAS as informações do contexto abaixo.
Se a resposta não estiver no contexto, diga educadamente que não tem essa
informação e sugira que o paciente entre em contato com a recepção.
Nunca invente horários, preços ou convênios que não estejam no contexto.
Responda sempre em português, de forma clara e cordial.

Contexto:
{context}

Pergunta: {question}

Resposta:"""

def load_agent(index_dir="index"):
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY")
    )
    vectorstore = FAISS.load_local(
        index_dir, embeddings, allow_dangerous_deserialization=True
    )
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.2
    )
    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=False
    )
    return qa_chain

def answer_question(qa_chain, question: str) -> str:
    try:
        result = qa_chain.invoke({"query": question})
        return result["result"]
    except Exception as e:
        print(f"Erro ao processar pergunta: {e}")
        return "Desculpe, tive um problema para processar sua pergunta. Tente novamente em instantes."