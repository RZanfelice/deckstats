"""Caso de uso: de um texto de lista de deck à simulação completa (M1 a M6)."""

from collections.abc import Sequence
from dataclasses import dataclass

from deckstats.catalog.repository import CardRepository
from deckstats.deck.analysis import Analysis, analyze_decklist
from deckstats.deck.stats import StatsOptions
from deckstats.simulation.engine import SimulationOptions, SimulationResult, run_simulation
from deckstats.simulation.model import build_simulation_input


class EmptyLibraryError(ValueError):
    """A lista não tem nenhuma carta reconhecida no deck principal."""


@dataclass(frozen=True, slots=True)
class Simulation:
    analysis: Analysis
    result: SimulationResult


def simulate_decklist(
    text: str,
    repository: CardRepository,
    options: SimulationOptions | None = None,
    *,
    count_mdfc_lands: bool = True,
    extra_costs: Sequence[str] = (),
) -> Simulation:
    analysis = analyze_decklist(text, repository, StatsOptions(count_mdfc_lands=count_mdfc_lands))
    if analysis.stats.main_cards == 0:
        raise EmptyLibraryError("nenhuma carta reconhecida no deck principal")
    sim = build_simulation_input(
        analysis.deck, count_mdfc_lands=count_mdfc_lands, extra_costs=extra_costs
    )
    return Simulation(analysis, run_simulation(sim.cards, options, sim.mana))
