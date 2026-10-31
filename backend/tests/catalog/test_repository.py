from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.loader import load_catalog
from deckstats.catalog.records import SourceVersion
from deckstats.catalog.repository import NameResolution, SqlCardRepository
from deckstats.db import Base
from tests.catalog.factories import card, face

VERSION = SourceVersion(version="5.3.0", date=date(2026, 5, 10))


@pytest.fixture
def repo() -> Iterator[SqlCardRepository]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    cards = [
        card("sol", "Sol Ring", edhrec_rank=1),
        card("island", "Island"),
        card("vault", "Lim-Dûl's Vault"),
        card("fire", "Fire // Ice", [face("Fire"), face("Ice", 1)], layout="split"),
        card("flame", "Fire // Brimstone", [face("Fire"), face("Brimstone", 1)], edhrec_rank=50),
        card("sign", "Sign in Blood"),
        card(
            "silver",
            "Scheming Silvertongue // Sign in Blood",
            [face("Scheming Silvertongue"), face("Sign in Blood", 1)],
            layout="modal_dfc",
        ),
        card("fury-ok", "Unquenchable Fury", commander_legality="legal"),
        card("fury-no", "Unquenchable Fury", commander_legality="not_legal"),
        card("fury-ban", "Unquenchable Fury", commander_legality="banned"),
        card("fun-1", "Garbage Elemental", is_funny=True, commander_legality="legal"),
        card("fun-2", "Garbage Elemental", is_funny=False, commander_legality="legal"),
        card("pop-1", "Rhystic Study", edhrec_rank=9),
        card("pop-2", "Rhystic Study", edhrec_rank=3),
        card("silly", "Rhystic Silliness", is_funny=True),
        card("cult", "Cultivate"),
    ]
    with Session(engine) as session:
        load_catalog(session, cards, VERSION)
        session.commit()
        yield SqlCardRepository(session)


def resolve_one(repo: SqlCardRepository, name: str) -> NameResolution:
    return repo.resolve([name])[0]


@pytest.mark.parametrize("typed", ["Sol Ring", "sol ring", "  SOL   RING "])
def test_resolves_exact_name_ignoring_case_and_spacing(repo: SqlCardRepository, typed: str) -> None:
    result = resolve_one(repo, typed)

    assert result.card is not None
    assert result.card.name == "Sol Ring"
    assert result.matched_by == "name"
    assert result.alternatives == 0
    assert result.suggestions == []


def test_resolves_accented_name_without_accents(repo: SqlCardRepository) -> None:
    result = resolve_one(repo, "Lim-Dul's Vault")

    assert result.card is not None
    assert result.card.name == "Lim-Dûl's Vault"


@pytest.mark.parametrize("typed", ["Fire // Ice", "Fire / Ice", "fire//ice"])
def test_resolves_multiface_with_any_separator(repo: SqlCardRepository, typed: str) -> None:
    result = resolve_one(repo, typed)

    assert result.card is not None
    assert result.card.name == "Fire // Ice"
    assert [f.name for f in result.card.faces] == ["Fire", "Ice"]


def test_resolves_by_face_name_when_no_full_name_matches(repo: SqlCardRepository) -> None:
    result = resolve_one(repo, "Brimstone")

    assert result.card is not None
    assert result.card.name == "Fire // Brimstone"
    assert result.matched_by == "face"


def test_full_name_beats_a_face_with_the_same_name(repo: SqlCardRepository) -> None:
    result = resolve_one(repo, "Sign in Blood")

    assert result.card is not None
    assert result.card.oracle_id == "sign"
    assert result.matched_by == "name"


def test_face_shared_by_two_cards_picks_the_most_popular_and_reports_alternatives(
    repo: SqlCardRepository,
) -> None:
    result = resolve_one(repo, "Fire")

    assert result.card is not None
    assert result.card.oracle_id == "flame"  # tem edhrec_rank; "fire" não tem
    assert result.alternatives == 1


def test_same_name_prefers_legal_then_banned_then_not_legal(repo: SqlCardRepository) -> None:
    result = resolve_one(repo, "Unquenchable Fury")

    assert result.card is not None
    assert result.card.oracle_id == "fury-ok"
    assert result.alternatives == 2


def test_same_name_prefers_non_funny(repo: SqlCardRepository) -> None:
    result = resolve_one(repo, "Garbage Elemental")

    assert result.card is not None
    assert result.card.oracle_id == "fun-2"


def test_same_name_prefers_lower_edhrec_rank(repo: SqlCardRepository) -> None:
    result = resolve_one(repo, "Rhystic Study")

    assert result.card is not None
    assert result.card.oracle_id == "pop-2"


def test_unknown_name_returns_suggestions_instead_of_a_card(repo: SqlCardRepository) -> None:
    result = resolve_one(repo, "Cultivte")

    assert result.card is None
    assert result.matched_by == "none"
    assert result.suggestions[0] == "Cultivate"


def test_suggestions_skip_funny_cards(repo: SqlCardRepository) -> None:
    assert "Rhystic Silliness" not in repo.suggest("Rhystic Silliness")


def test_suggest_with_empty_query_returns_nothing(repo: SqlCardRepository) -> None:
    assert repo.suggest("   ") == []


def test_suggest_respects_limit(repo: SqlCardRepository) -> None:
    assert len(repo.suggest("Rhystic Stud", limit=1)) == 1


def test_resolve_keeps_input_order_and_duplicates(repo: SqlCardRepository) -> None:
    results = repo.resolve(["Island", "Sol Ring", "Island"])

    assert [r.query for r in results] == ["Island", "Sol Ring", "Island"]
    assert [r.card.name if r.card else None for r in results] == ["Island", "Sol Ring", "Island"]


def test_resolve_with_no_names_returns_nothing(repo: SqlCardRepository) -> None:
    assert repo.resolve([]) == []


def test_get_returns_the_card_with_its_faces(repo: SqlCardRepository) -> None:
    found = repo.get("fire")

    assert found is not None
    assert found.name == "Fire // Ice"
    assert found.layout == "split"
    assert [f.name for f in found.faces] == ["Fire", "Ice"]


def test_get_unknown_oracle_id_returns_none(repo: SqlCardRepository) -> None:
    assert repo.get("does-not-exist") is None
