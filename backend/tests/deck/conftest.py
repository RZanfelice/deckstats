from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from deckstats.catalog.loader import load_catalog
from deckstats.catalog.records import CardRecord, SourceVersion
from deckstats.catalog.repository import SqlCardRepository
from deckstats.db import Base
from tests.deck.builders import land, make_card, make_face

ATRAXA = make_card(
    "Atraxa, Praetors' Voice",
    mana_value=4.0,
    mana_cost="{G}{W}{U}{B}",
    colors=("G", "W", "U", "B"),
    can_be_commander=True,
    edhrec_rank=10,
)
EMERIA = make_card(
    "Emeria's Call // Emeria, Shattered Skyclave",
    layout="modal_dfc",
    mana_value=7.0,
    colors=("W",),
    faces=[
        make_face("Emeria's Call", mana_cost="{4}{W}{W}{W}", mana_value=7.0, colors=("W",), types=("Sorcery",)),
        make_face("Emeria, Shattered Skyclave", types=("Land",), position=1),
    ],
)  # fmt: skip


def catalog_cards() -> list[CardRecord]:
    return [
        ATRAXA,
        make_card("Elf Chief", mana_value=2.0, mana_cost="{1}{G}", colors=("G",), can_be_commander=True),
        make_card("Goblin Chief", colors=("R",), can_be_commander=True),
        make_card("Sol Ring", mana_value=1.0, mana_cost="{1}", types=("Artifact",), identity=()),
        make_card("Cultivate", mana_value=3.0, mana_cost="{2}{G}", colors=("G",), types=("Sorcery",)),
        make_card("Lightning Bolt", mana_value=1.0, mana_cost="{R}", colors=("R",), types=("Instant",)),
        make_card("Time Walk", mana_value=2.0, mana_cost="{1}{U}", colors=("U",), types=("Sorcery",), legality="banned"),
        land("Forest", identity=("G",), produces=("G",)),
        land("Island", identity=("U",), produces=("U",)),
        land("Command Tower", basic=False, produces=("W", "U", "B", "R", "G")),
        EMERIA,
        make_card("Unquenchable Fury", mana_value=2.0, colors=("R",), legality="legal", edhrec_rank=5, oracle_id="fury-ok"),
        make_card("Unquenchable Fury", mana_value=2.0, colors=("R",), legality="not_legal", oracle_id="fury-no"),
    ]  # fmt: skip


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        load_catalog(session, catalog_cards(), SourceVersion("5.3.0", date(2026, 5, 10)))
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def repository(engine: Engine) -> Iterator[SqlCardRepository]:
    with Session(engine) as session:
        yield SqlCardRepository(session)
