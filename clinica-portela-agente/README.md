# Agente de IA para a Clínica Portela

Assistente virtual em linguagem natural que responde perguntas sobre os
serviços, convênios e políticas da Clínica Portela, usando RAG sobre
documentos internos em PDF.

## Arquitetura

Usuário → Bot do Telegram → Motor RAG (FAISS + Gemini) → Resposta

## Tecnologias utilizadas

- Python
- python-telegram-bot
- LangChain
- FAISS (busca vetorial)
- Google Gemini (embeddings + geração de texto)
- Oracle Cloud Infrastructure (deploy)

## Instruções de instalação

```bash
git clone https://github.com/seu-usuario/clinica-portela-agente.git
cd clinica-portela-agente
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha suas chaves
python src/ingest.py   # gera o índice
python src/telegram_bot.py   # inicia o bot
```

## Exemplos de Perguntas e Respostas

> ⚠️ Os exemplos abaixo são ilustrativos. Substitua pelas respostas reais
> geradas pelo seu agente depois de testar localmente — é isso que a
> avaliação verifica.

### Exemplo 1
**Pergunta:** Quais especialidades a Clínica Portela atende?

**Resposta:** A Clínica Portela atende às especialidades de Clínica Geral,
Cardiologia, Dermatologia, Ginecologia e Obstetrícia, Ortopedia e
Traumatologia, Pediatria, Psiquiatria, Endocrinologia e Otorrinolaringologia.

### Exemplo 2
**Pergunta:** Vocês aceitam o convênio Unimed?

**Resposta:** Sim, aceitamos Unimed em todos os planos regionais. Consultas
em clínica geral, pediatria e ginecologia têm cobertura integral. Consultas
com outros especialistas podem exigir encaminhamento do clínico geral,
dependendo do seu plano.

### Exemplo 3
**Pergunta:** Qual o horário de funcionamento?

**Resposta:** Funcionamos de segunda a sexta-feira, das 7h às 19h, e aos
sábados das 8h às 12h. Não há atendimento aos domingos e feriados.

### Exemplo 4
**Pergunta:** Posso cancelar minha consulta em cima da hora?

**Resposta:** Cancelamentos devem ser feitos com no mínimo 24 horas de
antecedência para não gerar cobrança. Cancelamentos com menos de 24h ou
faltas sem aviso podem resultar em taxa de não comparecimento de R$ 50,00
em atendimentos particulares.

### Exemplo 5
**Pergunta:** Quanto custa uma consulta particular com clínico geral?

**Resposta:** A consulta particular com clínico geral custa R$ 180,00.
Retornos em até 30 dias são gratuitos.
