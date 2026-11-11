# DeckStats

Análise estatística de decks de Magic: The Gathering (Commander): curva de mana, simulações Monte Carlo de consistência, classificação de cartas por função (ramp, draw, remoção...) e, mais adiante, estimativa de arquétipo e bracket com Machine Learning.

> **Status:** em desenvolvimento ativo. Backend (API, catálogo, simulação, classificação por regras) e interface web funcionam localmente; a classificação ainda **não usa Machine Learning** e o projeto ainda não tem deploy público.

O projeto **não** recomenda cartas, não monta decks e não substitui ferramentas como EDHRec ou Moxfield. O foco é análise, estatística e engenharia de ML/MLOps. É um projeto de estudo e portfólio, com código aberto.

## O que já funciona

- **Catálogo de cartas:** ingestão dos CSVs do [MTGJSON](https://mtgjson.com) em PostgreSQL (~34 mil cartas, migrações com Alembic, índices de trigrama para sugerir nomes parecidos) e exportação para SQLite para uma demo sem Postgres.
- **Análise de deck:** parser de listas coladas como texto (Arena, MTGO, Moxfield, Archidekt) e estatísticas de terrenos, curva de mana, valor de mana médio, cores e tipos. Avisa sobre cartas não encontradas (com sugestões) e regras de Commander violadas.
- **Probabilidade de terrenos:** modelo hipergeométrico por turno, turno crítico do deck, tabela de sensibilidade (quantos terrenos para atingir 70%, 80% e 90%) e o problema inverso.
- **Simulação Monte Carlo de consistência de mana:** mão inicial, mulligan London, terrenos por turno, cores, conjuração do comandante e rampa. Todas as probabilidades vêm com intervalo de confiança de Wilson a 95%.
- **Políticas de mão mantível:** uma regra simples (faixa de terrenos e uma magia barata) e outra por *castabilidade* (o que dá para conjurar com os terrenos da mão, com crédito para rampa e cantrips). Um módulo compara duas políticas nas **mesmas partidas** (sementes pareadas) e reporta a diferença com erro padrão, para separar efeito real de ruído.
- **Classificação de cartas por função** (ramp, card draw, remoção, board wipe, contramágica etc.), com taxonomia multi-label versionada e um classificador por regras de texto (`rules-1.0.0`). A análise de um deck já devolve a contagem por categoria.
- **Interface web** (React + TypeScript): formulário para colar a lista, resumo, avisos, gráficos (curva, cores, tipos, categorias, chance de terrenos) e painel de simulação de mana. Textos em PT-BR e tipos gerados a partir do OpenAPI do backend.
- **Qualidade:** cerca de 700 testes no backend com cobertura de ~99% (mínimo exigido: 80%), ruff, mypy, testes no frontend e CI no GitHub Actions (lint, tipos, testes, build e imagem Docker).

## Decisões técnicas

- **Estatística antes de ML.** Cada probabilidade tem incerteza declarada (intervalo de Wilson) e as comparações entre políticas usam as mesmas sementes e erro padrão, para não confundir ruído com diferença real.
- **Classificação começa por regras (v0).** Serve de linha de base mensurável antes de qualquer modelo. `Combo Piece` fica de fora de propósito, porque depende de uma base externa de combos.
- **Avaliação do classificador.** Há um conjunto-semente de 162 cartas rotuladas, usado para medir precisão, recall e F1 por categoria e listar os desacordos. Os rótulos foram escritos de forma independente das regras, mas **ainda precisam de revisão humana**, então este repositório não divulga métricas finais.
- **O que a simulação mede e o que não mede.** Mede mana (terrenos, cores, comandante), não vitórias. Uma política mais exigente troca mulligans por mana mais estável, e a comparação mostra os dois lados.
- **MLOps antes do produto:** CI, migrações, contêineres e testes de integração com Postgres desde o início. Análise anônima, sem contas e sem import por URL (só texto colado).

## Roadmap

- [x] Catálogo de cartas e busca por nome
- [x] Parser, estatísticas e probabilidade de terrenos
- [x] Simulação Monte Carlo e políticas de mão mantível
- [x] Classificação por regras (v0) e interface web
- [ ] Revisão humana do conjunto de validação e ajuste das regras
- [ ] Classificação com Machine Learning, validada contra o conjunto rotulado
- [ ] Estimativa de arquétipo e bracket
- [ ] Rastreamento de experimentos, monitoramento e deploy de uma demo enxuta

## Estrutura

```text
backend/    API FastAPI (Python 3.12, uv): catálogo, deck, simulação, classificação
frontend/   React + TypeScript + Vite (interface)
docker/     Dockerfiles e inicialização do Postgres
data/raw/   dados baixados (ignorados pelo git)
scripts/    utilitários
.github/    CI (GitHub Actions)
```

## Requisitos

- Python 3.12+ e [uv](https://docs.astral.sh/uv/)
- Docker e Docker Compose
- Node 22+ (frontend)

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

### Frontend (local)

```bash
docker compose up -d        # API em http://localhost:8000
cd frontend
npm install
npm run dev                 # http://localhost:5173, com proxy /api -> API
npm test
npm run gen:api             # regenera os tipos a partir do OpenAPI do backend
```

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

### Simulação e classificação

```bash
# Simulação Monte Carlo de consistência de mana (mão inicial, mulligan, terrenos, comandante, cores)
curl -s -X POST "localhost:8000/simulations/text?iterations=10000"   -H 'content-type: text/plain' --data-binary @deck.txt

# Classifica o catálogo por categoria (ramp, card_draw, removal...) e mede contra o conjunto rotulado
cd backend
uv run python -m deckstats.classification.cli classify
uv run python -m deckstats.classification.cli report
```

A análise (`/analyses`) já devolve a contagem por categoria do deck.

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
