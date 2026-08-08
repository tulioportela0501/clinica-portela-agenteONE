"""
seed_data.py
Popula o banco com dados iniciais de teste (serviços e profissionais).
Rode uma vez: python src/seed_data.py
Ajuste os valores para os serviços reais da Clínica Portela.
"""

from database import init_db, get_session
from models import Service, Professional

def run():
    init_db()

    with get_session() as db:
        if db.query(Service).count() == 0:
            db.add_all([
                Service(nome="Limpeza de Pele", descricao="Higienização + extração", duracao_minutos=60, preco=180.00),
                Service(nome="Avaliação Estética", descricao="Avaliação inicial", duracao_minutos=45, preco=100.00),
                Service(nome="Procedimento X", descricao="Descrição do procedimento X", duracao_minutos=60, preco=250.00),
            ])
            print("Serviços cadastrados.")
        else:
            print("Serviços já existiam, nada foi alterado.")

        if db.query(Professional).count() == 0:
            db.add_all([
                Professional(nome="Dra. Exemplo", especialidade="Esteticista", ativo=True),
            ])
            print("Profissionais cadastrados.")
        else:
            print("Profissionais já existiam, nada foi alterado.")

if __name__ == "__main__":
    run()
