import os

from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

load_dotenv()


def build_index(docs_dir="documentos", index_dir="index"):

    if not os.path.isdir(docs_dir):
        raise FileNotFoundError(
            f"A pasta '{docs_dir}' não existe."
        )

    loader = PyPDFDirectoryLoader(docs_dir)
    documents = loader.load()

    print(f"{len(documents)} páginas carregadas.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    chunks = splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY")
    )

    vectorstore = FAISS.from_documents(
        chunks,
        embeddings
    )

    vectorstore.save_local(index_dir)

    print(f"Índice criado com {len(chunks)} chunks.")


if __name__ == "__main__":
    build_index()