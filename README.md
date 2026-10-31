# DeckStats

Análise estatística de decks de Magic: The Gathering (Commander): curva de mana, simulações Monte Carlo de consistência, classificação de cartas por função (ramp, draw, remoção...) e, mais adiante, estimativa de arquétipo e bracket com Machine Learning.

> **Status:** em desenvolvimento inicial (Fase 0 do roadmap). Ainda não há funcionalidades de análise.

O projeto **não** recomenda cartas, não monta decks e não substitui ferramentas como EDHRec ou Moxfield. O foco é análise, estatística e engenharia de ML/MLOps. É um projeto de estudo e portfólio, com código aberto.

## Estrutura

```text
backend/    API FastAPI (Python 3.12, uv)
frontend/   React + TypeScript (a criar na Fase 6)
ml/         código de inferência e features
training/   pipelines de treino
workers/    tarefas assíncronas
shared/     contratos compartilhados
infra/      observabilidade e deploy
docker/     Dockerfiles
data/raw/   dados baixados (ignorados pelo git)
scripts/    utilitários
docs/       notas de trabalho (ignorado pelo git)
```

## Requisitos

- Python 3.12+ e [uv](https://docs.astral.sh/uv/)
- Docker e Docker Compose
- Node 20+ (a partir da Fase 6)

## Como rodar

### Dados de cartas

Os CSVs do [MTGJSON](https://mtgjson.com) não ficam no repositório (cerca de 600 MB descompactados):

```bash
python scripts/download_mtgjson.py
```

### Backend (local)

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn deckstats.main:app --reload
```

A documentação OpenAPI fica em http://localhost:8000/docs.

### Com Docker

```bash
cp .env.example .env
docker compose up --build
```

Sobe a API (8000), Postgres (5433, para não colidir com um Postgres local) e Redis (6379).

### Catálogo de cartas

Com o Postgres do Compose no ar (`docker compose up -d db`) e os CSVs baixados:

```bash
cd backend
uv run alembic upgrade head
uv run python -m deckstats.catalog.cli load --data-dir ../data/raw/mtgjson
```

Carrega cerca de 34 mil cartas em ~40 s; repetir o comando é seguro. Para a demo sem Postgres, gere um arquivo SQLite (~27 MB):

```bash
uv run python -m deckstats.catalog.cli export-sqlite --data-dir ../data/raw/mtgjson --output ../data/catalog.sqlite
```

### Analisar um deck

Com a API no ar (`uv run uvicorn deckstats.main:app --reload`) e o catálogo carregado:

```bash
curl -s localhost:8000/analyses -H 'content-type: application/json'   -d '{"decklist": "Commander
1 Atraxa, Praetors'"'"' Voice

Deck
99 Forest", "options": {"count_mdfc_lands": true}}'
```

A lista pode vir de Arena, MTGO, Moxfield ou Archidekt (texto colado). A resposta traz estatísticas (terrenos, curva, MV, cores, tipos), as cartas resolvidas e uma lista de `issues` (cartas não encontradas com sugestões, regras de Commander violadas...).

### Qualidade

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest        # exige cobertura mínima de 80%
```

Os testes de integração com Postgres rodam quando `DECKSTATS_TEST_DATABASE_URL` aponta para um banco **descartável** (as tabelas são apagadas). O Compose cria `deckstats_test` em volumes novos:

```bash
DECKSTATS_TEST_DATABASE_URL=postgresql+psycopg://deckstats:deckstats@localhost:5433/deckstats_test uv run pytest
```

Para ativar os hooks de commit: `pip install pre-commit && pre-commit install`.

## Aviso

DeckStats não é afiliado à Wizards of the Coast. Magic: The Gathering é marca registrada da Wizards of the Coast LLC. Dados de cartas via MTGJSON.

## Licença

[MIT](LICENSE)
