from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from deckstats.catalog.loader import load_catalog
from deckstats.catalog.models import CardFace, DataVersion, OracleCard
from deckstats.catalog.records import SourceVersion
from deckstats.db import Base
from tests.catalog.factories import card, face

V1 = SourceVersion(version="5.3.0", date=date(2026, 5, 10))
V2 = SourceVersion(version="5.4.0", date=date(2026, 6, 10))


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_loads_cards_faces_and_version(session: Session) -> None:
    cards = [card("a", "Sol Ring"), card("b", "Fire // Ice", [face("Fire"), face("Ice", 1)])]

    result = load_catalog(session, cards, V1)
    session.commit()

    assert (result.cards, result.faces, result.removed) == (2, 3, 0)
    assert count(session, OracleCard) == 2
    assert count(session, CardFace) == 3
    version = session.scalars(select(DataVersion)).one()
    assert (version.version, version.card_count, version.face_count) == ("5.3.0", 2, 3)


def test_normalized_names_are_stored_for_cards_and_faces(session: Session) -> None:
    load_catalog(session, [card("b", "Fire // Ice", [face("Fire"), face("Ice", 1)])], V1)
    session.commit()

    assert session.scalars(select(OracleCard.name_normalized)).one() == "fire // ice"
    assert set(session.scalars(select(CardFace.name_normalized))) == {"fire", "ice"}


def test_loading_twice_is_idempotent(session: Session) -> None:
    cards = [card("a", "Sol Ring"), card("b", "Island")]

    load_catalog(session, cards, V1)
    session.commit()
    second = load_catalog(session, cards, V1)
    session.commit()

    assert (second.cards, second.faces, second.removed) == (2, 2, 0)
    assert count(session, OracleCard) == 2
    assert count(session, CardFace) == 2
    assert count(session, DataVersion) == 1


def test_reload_updates_changed_cards_and_recreates_faces(session: Session) -> None:
    load_catalog(session, [card("a", "Sol Ring", [face("Sol Ring", text="antigo")])], V1)
    session.commit()

    load_catalog(
        session, [card("a", "Sol Ring", [face("Sol Ring", text="novo")], edhrec_rank=1)], V2
    )
    session.commit()

    stored = session.get(OracleCard, "a")
    assert stored is not None
    assert stored.edhrec_rank == 1
    assert [f.text for f in stored.faces] == ["novo"]
    assert count(session, CardFace) == 1
    assert count(session, DataVersion) == 2


def test_cards_missing_from_a_new_load_are_removed_with_their_faces(session: Session) -> None:
    load_catalog(session, [card("a", "Sol Ring"), card("b", "Island")], V1)
    session.commit()

    result = load_catalog(session, [card("a", "Sol Ring")], V2)
    session.commit()

    assert result.removed == 1
    assert session.get(OracleCard, "b") is None
    assert count(session, CardFace) == 1


def test_batches_cover_every_card(session: Session) -> None:
    cards = [card(f"id-{i}", f"Card {i}") for i in range(7)]

    result = load_catalog(session, cards, V1, batch_size=3)

    assert result.cards == 7
    assert count(session, OracleCard) == 7
