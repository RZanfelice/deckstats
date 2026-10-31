"""Listas reais de precons (MTGJSON setDecks) contra o catálogo real.

Pulado quando data/catalog.sqlite não existe (gere com `catalog export-sqlite`).
Cobre três formatos de export: Arena (seções + set/número), MTGO (comandante no
sideboard) e texto simples (comandante no topo, `1x`, comentários).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.repository import SqlCardRepository
from deckstats.deck.analysis import analyze_decklist

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "data" / "catalog.sqlite"
DECKS = Path(__file__).resolve().parents[1] / "fixtures" / "decks"

pytestmark = pytest.mark.skipif(not CATALOG.exists(), reason="data/catalog.sqlite não existe")


@pytest.fixture(scope="module")
def repository() -> Iterator[SqlCardRepository]:
    engine = create_engine(f"sqlite:///{CATALOG}")
    with Session(engine) as session:
        yield SqlCardRepository(session)
    engine.dispose()


@pytest.mark.parametrize("path", sorted(DECKS.glob("*.txt")), ids=lambda p: p.name)
def test_precon_resolves_completely_with_no_issues(
    path: Path, repository: SqlCardRepository
) -> None:
    analysis = analyze_decklist(path.read_text(encoding="utf-8"), repository)

    assert analysis.unresolved == []
    assert analysis.parse_errors == []
    assert analysis.stats.played_cards == 100
    assert [i.code for i in analysis.issues if i.severity != "info"] == []
    assert 1 <= len(analysis.deck.commanders) <= 2


def test_partner_precon_has_the_expected_commanders(repository: SqlCardRepository) -> None:
    text = (DECKS / "who-blast-from-the-past.arena.txt").read_text(encoding="utf-8")

    analysis = analyze_decklist(text, repository)

    assert sorted(e.card.name for e in analysis.deck.commanders) == [
        "Sarah Jane Smith",
        "The Fourth Doctor",
    ]
    assert analysis.commander_inferred is False


def test_mdfc_lands_are_counted_by_default_and_togglable(repository: SqlCardRepository) -> None:
    from deckstats.deck.stats import StatsOptions

    text = (DECKS / "sld-from-cute-to-brute.mtgo.txt").read_text(encoding="utf-8")

    on = analyze_decklist(text, repository)
    off = analyze_decklist(text, repository, StatsOptions(count_mdfc_lands=False))

    assert on.commander_inferred is True
    assert (on.stats.lands.lands, on.stats.lands.mdfc_lands, on.stats.lands.total) == (35, 4, 39)
    assert off.stats.lands.total == 35
