"""A simulação nas listas reais de precons e do Moxfield (pulado sem data/catalog.sqlite)."""

from collections.abc import Iterator
from math import sqrt
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.repository import SqlCardRepository
from deckstats.deck.analysis import analyze_decklist
from deckstats.simulation.engine import SimulationOptions, run_simulation
from deckstats.simulation.model import build_sim_deck

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
def test_simulated_land_drops_match_the_exact_odds_at_the_critical_turn(
    path: Path, repository: SqlCardRepository
) -> None:
    analysis = analyze_decklist(path.read_text(encoding="utf-8"), repository)
    assert analysis.land_odds is not None and analysis.land_odds.at_critical_turn is not None
    deck = build_sim_deck(analysis.deck)
    options = SimulationOptions(iterations=20_000, seed=11, apply_mulligan=False)

    result = run_simulation(deck, options)

    turn = analysis.land_odds.at_critical_turn.turn
    exact = analysis.land_odds.at_critical_turn.p_land_drops
    sigma = sqrt(exact * (1 - exact) / options.iterations)
    assert result.library_size == analysis.land_odds.library_size
    assert result.lands_in_library == analysis.land_odds.lands_in_library
    assert abs(result.land_drops[turn].p - exact) <= 4 * sigma


@pytest.mark.parametrize("path", sorted(DECKS.glob("*.txt")), ids=lambda p: p.name)
def test_real_decks_keep_most_opening_hands(path: Path, repository: SqlCardRepository) -> None:
    analysis = analyze_decklist(path.read_text(encoding="utf-8"), repository)

    result = run_simulation(build_sim_deck(analysis.deck), SimulationOptions(iterations=5_000))

    assert 0.5 < result.first_hand_keepable.p < 1.0
    assert result.mulligans is not None
    assert 5.0 <= result.mulligans.mean_final_hand_size <= 7.0
