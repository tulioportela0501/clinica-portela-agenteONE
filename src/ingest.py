import os
import json
import shutil
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "documentos"
INDEX_DIR = BASE_DIR / "index"


EMBEDDING_MODEL = "text-embedding-3-small"


def validate_environment():
    """
    Verifica se as configurações básicas estão disponíveis.
    """

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY não encontrada no arquivo .env"
        )

    if not DOCS_DIR.exists():
        raise FileNotFoundError(
            f"Pasta de documentos não encontrada: {DOCS_DIR}"
        )

    pdfs = list(DOCS_DIR.glob("*.pdf"))

    if not pdfs:
        raise FileNotFoundError(
            f"Nenhum arquivo PDF encontrado em: {DOCS_DIR}"
        )

    return pdfs


def clean_text(text: str) -> str:
    """
    Faz uma limpeza básica no texto extraído dos PDFs.
    """

    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")

    lines = []

    for line in text.split("\n"):
        line = " ".join(line.split())

        if line:
            lines.append(line)

    return "\n".join(lines)


def prepare_documents(documents):
    """
    Limpa os documentos e adiciona metadados úteis para o RAG.
    """

    prepared = []

    for document in documents:

        text = clean_text(document.page_content)

        if not text.strip():
            continue

        source = document.metadata.get("source", "")

        filename = Path(source).name

        page = document.metadata.get("page")

        if page is not None:
            page_number = page + 1
        else:
            page_number = None

        document.page_content = text

        document.metadata.update(
            {
                "filename": filename,
                "documento": filename,
                "page_number": page_number,
                "source_type": "clinica_portela_pdf",
            }
        )

        prepared.append(document)

    return prepared


def build_index():

    pdfs = validate_environment()

    print()
    print("=" * 60)
    print("CLÍNICA PORTELA — CONSTRUÇÃO DA BASE DE CONHECIMENTO")
    print("=" * 60)
    print()

    print(f"PDFs encontrados: {len(pdfs)}")
    print()

    for pdf in sorted(pdfs):
        print(f"  ✓ {pdf.name}")

    print()

    loader = PyPDFDirectoryLoader(
        str(DOCS_DIR)
    )

    documents = loader.load()

    print(
        f"Total de páginas carregadas: {len(documents)}"
    )

    documents = prepare_documents(documents)

    print(
        f"Páginas com conteúdo válido: {len(documents)}"
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=180,
        length_function=len,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "? ",
            "! ",
            "; ",
            ", ",
            " ",
            "",
        ],
    )

    chunks = splitter.split_documents(documents)

    print(
        f"Total de chunks gerados: {len(chunks)}"
    )

    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    print()
    print("Gerando embeddings...")
    print()

    vectorstore = FAISS.from_documents(
        chunks,
        embeddings,
    )

    # Cria a pasta do índice se não existir
    INDEX_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vectorstore.save_local(
        str(INDEX_DIR)
    )

    # Cria um manifesto para facilitar manutenção
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "embedding_model": EMBEDDING_MODEL,
        "documents": len(pdfs),
        "pages": len(documents),
        "chunks": len(chunks),
        "chunk_size": 1200,
        "chunk_overlap": 180,
        "files": sorted(
            [pdf.name for pdf in pdfs]
        ),
    }

    manifest_path = INDEX_DIR / "manifest.json"

    with open(
        manifest_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 60)
    print("ÍNDICE CRIADO COM SUCESSO")
    print("=" * 60)
    print()
    print(f"Documentos: {len(pdfs)}")
    print(f"Páginas:    {len(documents)}")
    print(f"Chunks:     {len(chunks)}")
    print(f"Índice:     {INDEX_DIR}")
    print()
    print("Arquivos gerados:")
    print("  ✓ index.faiss")
    print("  ✓ index.pkl")
    print("  ✓ manifest.json")
    print()
    print("Base de conhecimento atualizada.")
    print()


if __name__ == "__main__":
    build_index()