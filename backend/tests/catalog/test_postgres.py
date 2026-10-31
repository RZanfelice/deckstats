"""Testes contra um Postgres real (JSONB, upsert do dialeto e pg_trgm).

Rodam só quando DECKSTATS_TEST_DATABASE_URL aponta para um banco descartável:
as tabelas são apagadas e recriadas. Nunca aponte para o banco de desenvolvimento.
"""

import os
from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from deckstats.catalog.loader import load_catalog
from deckstats.catalog.models import CardFace, OracleCard
from deckstats.catalog.records import SourceVersion
from deckstats.catalog.repository import SqlCardRepository
from deckstats.db import Base
from tests.catalog.factories import card, face

DATABASE_URL = os.environ.get("DECKSTATS_TEST_DATABASE_URL")
VERSION = SourceVersion(version="5.3.0", date=date(2026, 5, 10))

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DECKSTATS_TEST_DATABASE_URL não definida")


@pytest.fixture
def session() -> Iterator[Session]:
    assert DATABASE_URL
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_upsert_is_idempotent_and_stores_lists_as_jsonb(session: Session) -> None:
    cards = [card("fire", "Fire // Ice", [face("Fire"), face("Ice", 1)], color_identity=["R", "U"])]

    load_catalog(session, cards, VERSION)
    session.commit()
    load_catalog(session, cards, VERSION)
    session.commit()

    assert session.scalar(select(func.count()).select_from(OracleCard)) == 1
    assert session.scalar(select(func.count()).select_from(CardFace)) == 2
    stored = session.get(OracleCard, "fire")
    assert stored is not None
    assert stored.color_identity == ["R", "U"]
    assert stored.faces[0].produced_mana == ["C"]


def test_trigram_suggestions_rank_by_similarity(session: Session) -> None:
    load_catalog(
        session,
        [
            card("study", "Rhystic Study"),
            card("tutor", "Rhystic Tutor"),
            card("cult", "Cultivate"),
            card("silly", "Rhystic Silliness", is_funny=True),
            card("fire", "Fire // Brimstone", [face("Fire"), face("Brimstone", 1)]),
        ],
        VERSION,
    )
    session.commit()
    repo = SqlCardRepository(session)

    suggestions = repo.suggest("Rhystic Studdy")

    assert suggestions[0] == "Rhystic Study"
    assert "Rhystic Silliness" not in suggestions
    assert "Cultivate" not in suggestions
    assert repo.suggest("Brimstne") == ["Fire // Brimstone"]  # sugestão vinda do nome da face


def test_resolve_works_on_postgres(session: Session) -> None:
    load_catalog(session, [card("sol", "Sol Ring"), card("lim", "Lim-Dûl's Vault")], VERSION)
    session.commit()

    results = SqlCardRepository(session).resolve(["sol ring", "Lim-Dul's Vault", "Cultivte"])

    assert [r.card.name if r.card else None for r in results] == [
        "Sol Ring",
        "Lim-Dûl's Vault",
        None,
    ]
