"""
pricing_service.py
Consulta de serviços/procedimentos e valores diretamente do banco de dados
(nunca do PDF/RAG, porque preço muda com frequência).
"""

from database import get_session
from models import Service


def listar_servicos(apenas_ativos: bool = True):
    """Retorna lista de dicts com todos os serviços cadastrados."""
    with get_session() as db:
        query = db.query(Service)
        if apenas_ativos:
            query = query.filter(Service.ativo == True)  # noqa: E712
        servicos = query.order_by(Service.nome).all()
        return [
            {
                "id": s.id,
                "nome": s.nome,
                "descricao": s.descricao,
                "duracao_minutos": s.duracao_minutos,
                "preco": s.preco,
            }
            for s in servicos
        ]


def get_price(nome_servico: str):
    """
    Busca um serviço pelo nome (busca parcial, case-insensitive).
    Retorna dict com service/price/duration ou None se não encontrar.
    """
    with get_session() as db:
        servico = (
            db.query(Service)
            .filter(Service.ativo == True)  # noqa: E712
            .filter(Service.nome.ilike(f"%{nome_servico}%"))
            .first()
        )
        if not servico:
            return None
        return {
            "service": servico.nome,
            "service_id": servico.id,
            "price": servico.preco,
            "duration": servico.duracao_minutos,
            "descricao": servico.descricao,
        }


def formatar_preco_para_resposta(nome_servico: str) -> str:
    """Gera a frase pronta que o agente envia ao paciente."""
    resultado = get_price(nome_servico)
    if not resultado:
        return (
            f"Não encontrei um serviço chamado '{nome_servico}' na tabela de valores. "
            "Pode me confirmar o nome do procedimento?"
        )
    return (
        f"{resultado['service']} tem valor de R$ {resultado['price']:.2f} "
        f"e duração aproximada de {resultado['duration']} minutos."
    )
