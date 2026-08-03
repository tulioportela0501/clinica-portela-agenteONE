import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()


def build_index(docs_dir="documentos", index_dir="index"):
    if not os.path.isdir(docs_dir) or not os.listdir(docs_dir):
        raise FileNotFoundError(
            f"Nenhum PDF encontrado em '{docs_dir}/'. "
            "Adicione os documentos da Clínica Portela antes de rodar a ingestão."
        )

    print(f"Lendo documentos em '{docs_dir}/'...")
    loader = PyPDFDirectoryLoader(docs_dir)
    documents = loader.load()
    print(f"{len(documents)} página(s) carregada(s).")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(documents)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY")
    )

    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(index_dir)
    print(f"Índice criado com {len(chunks)} chunks em '{index_dir}/'.")


if __name__ == "__main__":
    build_index()
