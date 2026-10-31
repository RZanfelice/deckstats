"""O motor com o modelo de mana por cor (M4 a M6)."""

from typing import Any

import pytest

from deckstats.catalog.records import CardRecord
from deckstats.deck.model import Deck
from deckstats.simulation.engine import (
    SimulationOptions,
    SimulationResult,
    _choose_land,
    run_simulation,
)
from deckstats.simulation.mana import LandType, ManaModel
from deckstats.simulation.model import LAND, SimulationInput, build_simulation_input
from tests.deck.builders import deck, entry, land, make_card

TAPPED = "This land enters tapped."


def commander(
    cost: str = "{1}{G}{G}", mv: float = 3.0, colors: tuple[str, ...] = ("G",)
) -> CardRecord:
    return make_card("Chief", mana_value=mv, mana_cost=cost, colors=colors, can_be_commander=True)


def green_deck(
    lands: int = 36, *, text: str | None = None, cost: str = "{1}{G}{G}", mv: float = 3.0
) -> Deck:
    return deck(
        entry(commander(cost, mv), 1, "commander"),
        entry(land("Forest", identity=("G",), produces=("G",), text=text), lands),
        entry(make_card("Spell", mana_value=3.0), 99 - lands),
    )


def simulate(
    d: Deck, iterations: int = 4_000, seed: int = 3, **options: Any
) -> tuple[SimulationResult, SimulationInput]:
    sim = build_simulation_input(d)
    opts = SimulationOptions(iterations=iterations, seed=seed, **options)
    return run_simulation(sim.cards, opts, sim.mana), sim


# --- equivalência com o caminho rápido ------------------------------------------------------------


def test_detailed_path_matches_the_fast_path_when_all_lands_are_alike() -> None:
    result, sim = simulate(green_deck(), iterations=3_000, seed=9)
    fast = run_simulation([LAND] * 36 + [3] * 63, SimulationOptions(iterations=3_000, seed=9))

    assert result.land_drops == fast.land_drops
    assert result.first_hand_keepable == fast.first_hand_keepable
    assert result.mulligans == fast.mulligans


def test_same_seed_gives_identical_mana_results() -> None:
    first, _ = simulate(green_deck(), iterations=1_500, seed=4)
    again, _ = simulate(green_deck(), iterations=1_500, seed=4)

    assert first == again


# --- M4: fontes de mana -----------------------------------------------------------------------------


def test_sources_equal_land_drops_when_every_land_is_untapped_and_produces_mana() -> None:
    result, _ = simulate(green_deck())

    assert result.mana is not None
    for turn in range(1, 7):
        assert result.mana.sources[turn][turn] == result.land_drops[turn]


def test_sources_probabilities_fall_as_more_sources_are_required() -> None:
    result, _ = simulate(green_deck())

    assert result.mana is not None
    row = [result.mana.sources[4][x].p for x in range(1, 11)]
    assert row == sorted(row, reverse=True)
    assert row[0] > row[-1]


def test_color_sources_count_lands_of_that_color() -> None:
    result, _ = simulate(green_deck())

    assert result.mana is not None
    assert "G" in result.mana.color_sources
    assert result.mana.color_sources["G"][3][1].p > 0.9
    # Nenhum terreno produz azul: a cor nem aparece na identidade deste comandante.
    assert "U" not in result.mana.color_sources


def test_colorless_sources_are_counted_separately() -> None:
    d = deck(
        entry(commander(), 1, "commander"),
        entry(land("Forest", identity=("G",), produces=("G",)), 20),
        entry(land("Wastes", produces=("C",)), 16),
        entry(make_card("Spell", mana_value=3.0), 63),
    )

    result, _ = simulate(d)

    assert result.mana is not None
    assert 0 < result.mana.color_sources["C"][4][1].p < result.mana.color_sources["G"][4][1].p


# --- M5/M6: custos ----------------------------------------------------------------------------------


def test_commander_cast_by_turn_equals_having_enough_untapped_lands() -> None:
    result, sim = simulate(green_deck())

    assert result.mana is not None
    commander_cost = next(c for c in result.mana.costs if c.source == "commander")
    assert commander_cost.cost == "{1}{G}{G}"
    assert commander_cost.mana_value == 3
    assert commander_cost.on_curve_turn == 3
    assert commander_cost.by_turn[1].p == 0.0
    assert commander_cost.by_turn[2].p == 0.0
    # mono-cor, tudo desvirado: pagar {1}{G}{G} é ter 3 terrenos no turno 3
    assert commander_cost.by_turn[3] == result.land_drops[3]


def test_cast_probability_never_falls_with_the_turn() -> None:
    result, _ = simulate(green_deck())

    assert result.mana is not None
    for cost in result.mana.costs:
        values = [cost.by_turn[t].p for t in range(1, 11)]
        assert values == sorted(values)


def test_missing_color_makes_the_commander_impossible() -> None:
    d = deck(
        entry(commander("{U}{U}", 2.0, ("U",)), 1, "commander"),
        entry(land("Forest", identity=("U", "G"), produces=("G",)), 36),
        entry(make_card("Spell", mana_value=2.0), 63),
    )

    result, _ = simulate(d)

    assert result.mana is not None
    cost = result.mana.costs[0]
    assert all(e.p == 0.0 for e in cost.by_turn.values())


def test_more_sources_of_the_color_make_the_commander_likelier() -> None:
    def build(islands: int) -> Deck:
        return deck(
            entry(commander("{U}{U}", 2.0, ("U",)), 1, "commander"),
            entry(land("Island", identity=("U", "G"), produces=("U",)), islands),
            entry(land("Forest", identity=("U", "G"), produces=("G",)), 36 - islands),
            entry(make_card("Spell", mana_value=2.0), 63),
        )

    few, _ = simulate(build(8), iterations=6_000)
    many, _ = simulate(build(24), iterations=6_000)

    assert few.mana is not None and many.mana is not None
    assert many.mana.costs[0].by_turn[3].p > few.mana.costs[0].by_turn[3].p + 0.2


def test_dual_lands_count_for_both_colors() -> None:
    d = deck(
        entry(commander("{U}{R}", 2.0, ("U", "R")), 1, "commander"),
        entry(land("Steam Vents", identity=("U", "R"), basic=False, produces=("R", "U")), 36),
        entry(make_card("Spell", mana_value=2.0), 63),
    )

    result, _ = simulate(d)

    assert result.mana is not None
    cost = result.mana.costs[0]
    assert cost.by_turn[2] == result.land_drops[2]  # duais pagam U e R: basta ter 2 terrenos


def test_tapped_lands_delay_the_commander_by_a_turn() -> None:
    tapped, _ = simulate(green_deck(text=TAPPED, cost="{G}", mv=1.0))
    normal, _ = simulate(green_deck(cost="{G}", mv=1.0))

    assert tapped.mana is not None and normal.mana is not None
    assert tapped.mana.costs[0].by_turn[1].p == 0.0
    assert tapped.mana.costs[0].by_turn[2].p > 0.5
    assert normal.mana.costs[0].by_turn[1].p > tapped.mana.costs[0].by_turn[1].p


def test_tapped_lands_still_count_as_land_drops() -> None:
    tapped, _ = simulate(green_deck(text=TAPPED))
    normal, _ = simulate(green_deck())

    assert tapped.land_drops == normal.land_drops


# --- alvos de custo ---------------------------------------------------------------------------------


def test_targets_include_the_commander_the_heaviest_card_per_color_and_custom_costs() -> None:
    d = deck(
        entry(commander("{1}{U}{G}", 3.0, ("U", "G")), 1, "commander"),
        entry(land("Island", identity=("U", "G"), produces=("U",)), 18),
        entry(land("Forest", identity=("U", "G"), produces=("G",)), 18),
        entry(make_card("Memory Deluge", mana_value=4.0, mana_cost="{2}{U}{U}", colors=("U",)), 1),
        entry(make_card("Opt", mana_value=1.0, mana_cost="{U}", colors=("U",)), 1),
        entry(make_card("Rancor", mana_value=1.0, mana_cost="{G}", colors=("G",)), 1),
        entry(make_card("Filler", mana_value=2.0), 60),
    )

    sim = build_simulation_input(d, extra_costs=["{3}{G}{G}"])

    by_source = {t.source: t for t in sim.mana.targets}
    assert by_source["commander"].cost_text == "{1}{U}{G}"
    assert by_source["deck_color:U"].label == "Memory Deluge"
    assert by_source["deck_color:G"].label == "Rancor"
    assert by_source["custom"].cost_text == "{3}{G}{G}"
    assert by_source["custom"].mana_value == 5


def test_color_target_ties_prefer_the_cheapest_card() -> None:
    d = deck(
        entry(commander("{1}{U}", 2.0, ("U",)), 1, "commander"),
        entry(land("Island", identity=("U",), produces=("U",)), 36),
        entry(
            make_card("Dig Through Time", mana_value=8.0, mana_cost="{6}{U}{U}", colors=("U",)), 1
        ),
        entry(make_card("Memory Deluge", mana_value=4.0, mana_cost="{2}{U}{U}", colors=("U",)), 1),
        entry(make_card("Filler", mana_value=2.0), 61),
    )

    sim = build_simulation_input(d)

    assert next(t for t in sim.mana.targets if t.source == "deck_color:U").label == "Memory Deluge"


def test_a_custom_cost_equal_to_an_existing_target_is_not_duplicated() -> None:
    d = green_deck()

    sim = build_simulation_input(d, extra_costs=["{1}{G}{G}"])

    assert [t.source for t in sim.mana.targets] == ["commander"]


def test_plan_turn_is_the_commander_mana_value_or_a_default() -> None:
    assert build_simulation_input(green_deck(mv=5.0, cost="{3}{G}{G}")).mana.plan_turn == 5
    no_commander = deck(
        entry(land("Forest", produces=("G",)), 36), entry(make_card("S", mana_value=2.0), 63)
    )
    assert build_simulation_input(no_commander).mana.plan_turn == 4


def test_lands_without_known_mana_are_reported_and_still_count_as_land_drops() -> None:
    d = deck(
        entry(commander(), 1, "commander"),
        entry(land("Forest", identity=("G",), produces=("G",)), 30),
        entry(
            land(
                "Evolving Wilds", basic=False, text="{T}, Sacrifice this land: Search your library"
            ),
            6,
        ),
        entry(make_card("Spell", mana_value=3.0), 63),
    )

    result, sim = simulate(d)

    assert sim.mana.unknown_mana_lands == ("Evolving Wilds",)
    assert result.mana is not None
    assert result.mana.unknown_mana_lands == ["Evolving Wilds"]
    # contam para as jogadas de terreno (36 terrenos), mas não geram mana
    fast = run_simulation([LAND] * 36 + [3] * 63, SimulationOptions(iterations=4_000, seed=3))
    assert result.land_drops == fast.land_drops
    assert result.mana.sources[3][3].p < result.land_drops[3].p


def test_land_types_are_deduplicated_by_colors_and_entry() -> None:
    d = deck(
        entry(commander(), 1, "commander"),
        entry(land("Forest", identity=("G",), produces=("G",)), 20),
        entry(land("Wild Forest", identity=("G",), produces=("G",)), 10),  # mesmo tipo
        entry(land("Tapped Forest", identity=("G",), produces=("G",), text=TAPPED), 6),
        entry(make_card("Spell", mana_value=3.0), 63),
    )

    sim = build_simulation_input(d)

    assert len(sim.mana.land_types) == 2
    assert sum(1 for card in sim.cards if card < 0) == 36


# --- política de terrenos ----------------------------------------------------------------------------


def policy_model(plan_turn: int, needed: str = "U") -> ManaModel:
    return ManaModel(
        land_types=(
            LandType("Island", frozenset("U"), False),  # código -1
            LandType("Tapped Island", frozenset("U"), True),  # código -2
            LandType("Forest", frozenset("G"), False),  # código -3
            LandType("Tapped Forest", frozenset("G"), True),  # código -4
        ),
        targets=(),
        histogram_colors=("U", "G"),
        plan_turn=plan_turn,
        needed_colors=frozenset(needed),
    )


def test_before_the_plan_turn_tapped_lands_are_played_first() -> None:
    chosen = _choose_land([-1, -2], {"U"}, turn=1, model=policy_model(plan_turn=4))

    assert chosen == -2


def test_from_the_plan_turn_on_untapped_lands_are_played_first() -> None:
    chosen = _choose_land([-1, -2], {"U"}, turn=4, model=policy_model(plan_turn=4))

    assert chosen == -1


def test_a_missing_needed_color_beats_the_timing_preference() -> None:
    # Já há Forest em jogo; falta U. Mesmo cedo (prefere virado), o Island desvirado vem antes
    # do Forest virado, porque o Island entrega a cor que falta.
    chosen = _choose_land([-1, -4], {"G"}, turn=1, model=policy_model(plan_turn=4))

    assert chosen == -1


def test_the_choice_is_deterministic() -> None:
    model = policy_model(plan_turn=3)

    picks = {_choose_land([-3, -1, -3, -1], set(), 2, model) for _ in range(5)}

    assert len(picks) == 1


@pytest.mark.parametrize("iterations", [1, 50])
def test_runs_with_few_iterations(iterations: int) -> None:
    result, _ = simulate(green_deck(), iterations=iterations)

    assert result.mana is not None
    assert result.iterations == iterations
