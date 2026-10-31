"""A simulação conjurando rampa: +1 de mana genérica a partir do turno seguinte."""

from dataclasses import replace

import pytest

from deckstats.deck.model import Deck
from deckstats.simulation.compare import compare_variants
from deckstats.simulation.engine import SimulationOptions, _play_with_mana, run_simulation
from deckstats.simulation.mana import (
    LandType,
    ManaModel,
    ManaResult,
    ManaTally,
    SpellType,
    parse_cost,
)
from deckstats.simulation.model import build_simulation_input
from tests.deck.builders import deck, entry, land, make_card

FOREST = -1
ISLAND = -2
RAMP_SOURCE = 2  # índice da fonte "+1 genérico" na tabela de terrenos

SPELLS = (
    SpellType("Ramp 2", 2, parse_cost("{1}{G}"), ramp=True),  # 0
    SpellType("Ramp 3", 3, parse_cost("{2}{G}"), ramp=True),  # 1
    SpellType("Blue Ramp", 2, parse_cost("{1}{U}"), ramp=True),  # 2
    SpellType("Filler", 5, parse_cost("{4}{G}"), ramp=False),  # 3
    SpellType("Ramp 1", 1, parse_cost("{G}"), ramp=True),  # 4
)
RAMP2, RAMP3, BLUE_RAMP, FILLER, RAMP1 = range(5)

MODEL = ManaModel(
    land_types=(
        LandType("Forest", frozenset("G"), False),
        LandType("Island", frozenset("U"), False),
        LandType("Ramp", frozenset("C"), False),
    ),
    targets=(),
    histogram_colors=("G", "U", "C"),
    plan_turn=4,
    needed_colors=frozenset("G"),
    spells=SPELLS,
    ramp_source=RAMP_SOURCE,
)
TURNS = 6


def play(hand: list[int], library: list[int], *, cast_ramp: bool = True) -> ManaResult:
    options = SimulationOptions(iterations=1, max_turn=TURNS, cast_ramp=cast_ramp)
    tally = ManaTally(MODEL, TURNS)
    hits = dict.fromkeys(range(1, TURNS + 1), 0)
    _play_with_mana(hand, library, options, MODEL, tally, hits)
    return tally.result(1)


def sources(result: ManaResult) -> list[int]:
    """Quantas fontes de mana havia em cada turno (a partida é uma só, então p é 0 ou 1)."""
    return [
        max((x for x, estimate in result.sources[turn].items() if estimate.p == 1.0), default=0)
        for turn in range(1, TURNS + 1)
    ]


PADDING = [FILLER] * 5
LANDS = [FOREST] * 10


# --- o básico: +1 a partir do turno seguinte ----------------------------------------------------------------


def test_ramp_adds_one_source_from_the_turn_after_it_was_cast() -> None:
    result = play([FOREST, FOREST, RAMP2, *PADDING[:4]], LANDS)

    # Turno 2: 2 terrenos, conjura a rampa depois de medir. Turno 3: 3 terrenos + 1.
    assert sources(result) == [1, 2, 4, 5, 6, 7]


def test_without_casting_the_same_game_has_only_lands() -> None:
    result = play([FOREST, FOREST, RAMP2, *PADDING[:4]], LANDS, cast_ramp=False)

    assert sources(result) == [1, 2, 3, 4, 5, 6]


def test_the_mana_spent_on_the_ramp_is_not_counted_in_the_turn_it_is_cast() -> None:
    result = play([FOREST, FOREST, RAMP2, *PADDING[:4]], LANDS)

    assert sources(result)[1] == 2  # no turno 2 ainda são só os 2 terrenos


def test_a_one_mana_ramp_can_be_cast_on_turn_one() -> None:
    result = play([FOREST, RAMP1, *PADDING], LANDS)

    assert sources(result) == [1, 3, 4, 5, 6, 7]


def test_a_ramp_that_costs_three_waits_for_the_third_land() -> None:
    result = play([FOREST, FOREST, RAMP3, *PADDING[:4]], LANDS)

    # Só com 3 terrenos (turno 3) dá para pagar {2}{G}; passa a valer no turno 4.
    assert sources(result) == [1, 2, 3, 5, 6, 7]


def test_a_ramp_of_a_missing_color_is_never_cast() -> None:
    result = play([FOREST, FOREST, BLUE_RAMP, *PADDING[:4]], LANDS)

    assert sources(result) == [1, 2, 3, 4, 5, 6]


def test_the_right_colors_make_it_castable() -> None:
    result = play([FOREST, ISLAND, BLUE_RAMP, *PADDING[:4]], LANDS)

    assert sources(result) == [1, 2, 4, 5, 6, 7]


def test_a_ramp_drawn_later_is_cast_when_it_arrives() -> None:
    # A rampa vem do topo da biblioteca no turno 2; é conjurada ali e conta a partir do 3.
    result = play([FOREST, *PADDING], [FOREST, RAMP2, *LANDS])

    assert sources(result) == [1, 2, 4, 5, 6, 7]


# --- várias rampas --------------------------------------------------------------------------------------------


def test_the_ramp_already_in_play_pays_for_the_next_one() -> None:
    # Turno 2: 2 terrenos pagam uma rampa. Turno 3: 3 terrenos + 1 rampa = 4 de mana pagam a outra.
    result = play([FOREST, FOREST, RAMP2, RAMP2, *PADDING[:3]], LANDS)

    assert sources(result) == [1, 2, 4, 6, 7, 8]


def test_two_cheap_ramps_are_cast_together_when_the_mana_allows() -> None:
    result = play([FOREST, FOREST, RAMP1, RAMP1, *PADDING[:3]], LANDS)

    # Turno 1: 1 terreno paga uma rampa de custo 1. Turno 2: 2 terrenos + 1 rampa pagam a outra.
    assert sources(result) == [1, 3, 5, 6, 7, 8]


def test_the_combined_cost_must_be_payable() -> None:
    # Duas rampas de custo 2 não cabem juntas em 2 terrenos: só uma por vez.
    result = play([FOREST, FOREST, RAMP2, RAMP2, *PADDING[:3]], [FOREST, *LANDS])

    assert sources(result)[2] == 4  # uma rampa já valendo no turno 3 (3 terrenos + 1)


def test_cards_that_are_not_ramp_are_ignored() -> None:
    result = play([FOREST, FOREST, FILLER, FILLER, *PADDING[:3]], LANDS)

    assert sources(result) == [1, 2, 3, 4, 5, 6]


# --- onde a rampa aparece nas medições ----------------------------------------------------------------------------


def test_ramp_counts_as_a_colorless_source() -> None:
    result = play([FOREST, FOREST, RAMP2, *PADDING[:4]], LANDS)

    assert result.color_sources["C"][2][1].p == 0.0
    assert result.color_sources["C"][3][1].p == 1.0
    assert result.color_sources["G"][3][3].p == 1.0  # os 3 Forest continuam dando G


def test_ramp_pays_generic_costs_but_not_colored_ones() -> None:
    model = replace(MODEL, targets=_targets())
    options = SimulationOptions(iterations=1, max_turn=TURNS, cast_ramp=True)
    tally = ManaTally(model, TURNS)
    hits = dict.fromkeys(range(1, TURNS + 1), 0)

    _play_with_mana([FOREST, FOREST, RAMP2, *PADDING[:4]], LANDS, options, model, tally, hits)

    costs = {c.cost: c for c in tally.result(1).costs}
    # No turno 3 há 3 terrenos Forest + 1 rampa: {2}{G}{G}{G}? não; {3}{G} sim; {U} nunca.
    assert costs["{3}{G}"].by_turn[3].p == 1.0
    assert costs["{3}{G}"].by_turn[2].p == 0.0
    assert costs["{U}"].by_turn[6].p == 0.0


def _targets() -> tuple:  # type: ignore[type-arg]
    from deckstats.simulation.mana import Target

    return (
        Target("quatro", "custom", "{3}{G}", parse_cost("{3}{G}"), 4),
        Target("azul", "custom", "{U}", parse_cost("{U}"), 1),
    )


# --- no motor completo ------------------------------------------------------------------------------------------------


def commander_deck(ramp: int) -> Deck:
    commander = make_card(
        "Chief", mana_value=4.0, mana_cost="{2}{G}{G}", colors=("G",), can_be_commander=True
    )
    rock = make_card(
        "Rock", mana_value=2.0, mana_cost="{2}", types=("Artifact",), identity=(),
        text="{T}: Add {C}.", produced_mana=("C",),
    )  # fmt: skip
    return deck(
        entry(commander, 1, "commander"),
        entry(land("Forest", identity=("G",), produces=("G",)), 36),
        entry(rock, ramp) if ramp else entry(make_card("Bear", mana_value=2.0), 1),
        entry(make_card("Dragon", mana_value=6.0, mana_cost="{4}{G}{G}", colors=("G",)), 62 - ramp),
    )


def test_a_deck_without_ramp_behaves_identically_with_the_option_on() -> None:
    sim = build_simulation_input(commander_deck(0))
    options = SimulationOptions(iterations=1_000, seed=2, paired_seeds=True)

    off = run_simulation(sim.cards, replace(options, cast_ramp=False), sim.mana)
    on = run_simulation(sim.cards, replace(options, cast_ramp=True), sim.mana)

    assert sim.mana.ramp_source is None
    assert on == off


def test_casting_ramp_never_changes_the_hand_or_the_land_drops() -> None:
    sim = build_simulation_input(commander_deck(10))
    options = SimulationOptions(iterations=2_000, seed=3, paired_seeds=True)

    off = run_simulation(sim.cards, replace(options, cast_ramp=False), sim.mana)
    on = run_simulation(sim.cards, replace(options, cast_ramp=True), sim.mana)

    assert on.first_hand_keepable == off.first_hand_keepable
    assert on.mulligans == off.mulligans
    assert on.land_drops == off.land_drops


def test_casting_ramp_never_lowers_the_mana_in_any_game() -> None:
    sim = build_simulation_input(commander_deck(10))

    rows = compare_variants(
        sim.cards,
        sim.mana,
        SimulationOptions(iterations=2_000, seed=4),
        baseline={"cast_ramp": False},
        candidate={"cast_ramp": True},
        replicates=3,
    )

    by_metric = {r.metric: r for r in rows}
    assert by_metric["4 fontes de mana no turno 4"].difference > 0.05
    assert by_metric["4 fontes de mana no turno 4"].significant
    assert all(r.difference >= 0 for r in rows if "fonte" in r.metric or "comandante" in r.metric)


def test_the_builder_adds_the_ramp_source_only_when_there_is_ramp() -> None:
    with_ramp = build_simulation_input(commander_deck(10)).mana
    without = build_simulation_input(commander_deck(0)).mana

    assert with_ramp.ramp_source is not None
    assert with_ramp.land_types[with_ramp.ramp_source].colors == frozenset("C")
    assert without.ramp_source is None


@pytest.mark.parametrize("cast_ramp", [False, True])
def test_the_option_is_off_by_default_in_the_engine(cast_ramp: bool) -> None:
    assert SimulationOptions().cast_ramp is False
    assert SimulationOptions(cast_ramp=cast_ramp).cast_ramp is cast_ramp


def test_a_color_the_ramp_needs_is_preferred_when_choosing_the_land() -> None:
    from deckstats.simulation.engine import _choose_land

    # O comandante só quer G; a rampa na mão quer U. Com U na lista de cores necessárias,
    # a Island passa na frente do segundo Forest.
    chosen = _choose_land([FOREST, ISLAND], {"G"}, 2, MODEL, needed=frozenset("GU"))

    assert chosen == ISLAND
    assert _choose_land([FOREST, ISLAND], {"G"}, 2, MODEL) == FOREST
