"""
database.py
Cria o engine, a sessão do SQLAlchemy e a função de inicialização
(criação das tabelas) usadas por todo o projeto.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models import Base

# check_same_thread=False é necessário para SQLite quando o bot roda
# em threads/async (python-telegram-bot usa asyncio internamente).
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Cria as tabelas se ainda não existirem. Chamar uma vez na inicialização do bot."""
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """
    Uso:
        with get_session() as db:
            db.query(...)

    Garante commit em caso de sucesso e rollback em caso de erro,
    evitando conexões presas.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
