"""As políticas de mão no motor completo: pareamento, construção das magias e comparação."""

from dataclasses import replace

import pytest

from deckstats.catalog.records import CardRecord
from deckstats.deck.model import Deck
from deckstats.simulation.compare import MetricComparison, compare_keep_policies, metrics_of
from deckstats.simulation.engine import SimulationOptions, run_simulation
from deckstats.simulation.model import SimulationInput, build_simulation_input, spell_roles
from tests.deck.builders import deck, entry, land, make_card

TAPPED = "This land enters tapped."


def spell(
    name: str,
    text: str,
    *,
    mv: float = 2.0,
    cost: str = "{1}{G}",
    types: tuple[str, ...] = ("Sorcery",),
    produced: tuple[str, ...] = (),
) -> CardRecord:
    return make_card(
        name,
        mana_value=mv,
        mana_cost=cost,
        colors=("G",),
        types=types,
        text=text,
        produced_mana=produced,
    )


RAMP_FETCH = "Search your library for a basic land card, put that card onto the battlefield tapped."
RAMP_ROCK = "{T}: Add {C}."
CANTRIP = "Scry 1. Draw a card."


def sample_deck(lands: int = 36) -> Deck:
    commander = make_card(
        "Chief", mana_value=4.0, mana_cost="{2}{G}{G}", colors=("G",), can_be_commander=True
    )
    return deck(
        entry(commander, 1, "commander"),
        entry(land("Forest", identity=("G",), produces=("G",)), lands),
        entry(spell("Rampant Growth", RAMP_FETCH), 1),
        entry(spell("Opt", CANTRIP, mv=1.0, cost="{G}", types=("Instant",)), 1),
        entry(make_card("Bear", mana_value=2.0, mana_cost="{1}{G}", colors=("G",)), 30),
        entry(
            make_card("Dragon", mana_value=6.0, mana_cost="{4}{G}{G}", colors=("G",)),
            99 - lands - 32,
        ),
    )


def build(lands: int = 36) -> SimulationInput:
    return build_simulation_input(sample_deck(lands))


# --- papéis das magias ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("card_kwargs", "ramp", "cantrip"),
    [
        (dict(text=RAMP_ROCK, types=("Artifact",), produced=("C",), mv=1.0, cost="{1}"), True, False),
        (dict(text=RAMP_FETCH), True, False),
        (dict(text="You may play an additional land on each of your turns.", types=("Enchantment",)), True, False),
        (dict(text="Add {B}{B}{B}.", types=("Instant",), produced=("B",), mv=1.0, cost="{B}"), False, False),  # ritual
        (dict(text=CANTRIP, types=("Instant",), mv=1.0, cost="{U}"), False, True),
        (dict(text="Draw three cards.", mv=4.0, cost="{2}{G}{G}"), False, False),  # caro demais
        (dict(text="At the beginning of your upkeep, draw a card.", types=("Enchantment",), mv=2.0), False, False),
        (dict(text="Destroy target creature.", types=("Instant",)), False, False),
        (dict(text="Flying"), False, False),
    ],
)  # fmt: skip
def test_spell_roles(card_kwargs: dict, ramp: bool, cantrip: bool) -> None:  # type: ignore[type-arg]
    card = spell("Test", **card_kwargs)

    assert spell_roles(card) == (ramp, cantrip)


def test_the_spell_table_deduplicates_equal_spells() -> None:
    d = deck(
        entry(land("Forest", produces=("G",)), 30),
        entry(spell("Bear A", "Flying"), 5),
        entry(spell("Bear B", "Flying"), 5),  # mesmo custo e papéis: mesma entrada
        entry(spell("Opt", CANTRIP, mv=1.0, cost="{G}", types=("Instant",)), 1),
    )

    sim = build_simulation_input(d)

    assert len(sim.mana.spells) == 2
    assert sorted(card for card in sim.cards if card >= 0) == [0] * 10 + [1]


def test_spell_codes_are_table_indices_and_lands_stay_negative() -> None:
    sim = build()

    assert all(0 <= card < len(sim.mana.spells) for card in sim.cards if card >= 0)
    assert sum(1 for card in sim.cards if card < 0) == 36
    names = {s.name: s for s in sim.mana.spells}
    assert names["Rampant Growth"].ramp is True
    assert names["Opt"].cantrip is True
    assert names["Dragon"].ramp is False and names["Dragon"].mana_value == 6


# --- pareamento ----------------------------------------------------------------------------------------------------


def test_paired_runs_are_reproducible() -> None:
    sim = build()
    options = SimulationOptions(iterations=1_000, seed=4, paired_seeds=True, keep_policy="castable")

    assert run_simulation(sim.cards, options, sim.mana) == run_simulation(
        sim.cards, options, sim.mana
    )


def test_paired_seeds_still_match_the_exact_odds() -> None:
    from math import sqrt

    from deckstats.deck.odds import at_least, cards_seen

    sim = build()
    options = SimulationOptions(iterations=15_000, seed=2, paired_seeds=True, apply_mulligan=False)

    result = run_simulation(sim.cards, options, sim.mana)

    for turn in range(1, 8):
        exact = at_least(turn, 99, 36, cards_seen(turn, 99, False))
        sigma = sqrt(exact * (1 - exact) / options.iterations)
        assert abs(result.land_drops[turn].p - exact) <= 4 * sigma


def test_castable_never_keeps_a_first_hand_that_simple_would_reject() -> None:
    sim = build()
    base = SimulationOptions(iterations=4_000, seed=5, paired_seeds=True)

    simple = run_simulation(sim.cards, replace(base, keep_policy="simple"), sim.mana)
    castable = run_simulation(sim.cards, replace(base, keep_policy="castable"), sim.mana)

    # Mesmas primeiras mãos nas duas execuções; castable é mais exigente.
    assert castable.first_hand_keepable.p <= simple.first_hand_keepable.p
    assert castable.mulligans is not None and simple.mulligans is not None
    assert castable.mulligans.at_least_one.p >= simple.mulligans.at_least_one.p
    assert castable.mulligans.mean_final_hand_size <= simple.mulligans.mean_final_hand_size


def test_the_policy_changes_nothing_when_no_hand_is_ever_rejected() -> None:
    sim = build()
    lenient = SimulationOptions(
        iterations=500, seed=1, paired_seeds=True, keep_min_lands=0, keep_max_lands=7,
        keep_min_effective=0.0, keep_max_spell_mv=99,
    )  # fmt: skip

    simple = run_simulation(sim.cards, replace(lenient, keep_policy="simple"), sim.mana)
    castable = run_simulation(sim.cards, replace(lenient, keep_policy="castable"), sim.mana)

    # Sem castável nada é mantível quando não há jogada castável; o resto das mãos é igual.
    assert simple.first_hand_lands == castable.first_hand_lands


def test_castable_works_on_a_deck_with_no_spells() -> None:
    d = deck(entry(land("Forest", identity=("G",), produces=("G",)), 99))
    sim = build_simulation_input(d)

    result = run_simulation(
        sim.cards, SimulationOptions(iterations=200, keep_policy="castable"), sim.mana
    )

    assert result.first_hand_keepable.p == 0.0  # sem nenhuma magia, nunca há jogada castável


# --- comparação ----------------------------------------------------------------------------------------------------------


def comparison(rows: list[MetricComparison], metric: str) -> MetricComparison:
    return next(r for r in rows if r.metric == metric)


def test_comparing_a_policy_with_itself_finds_no_difference() -> None:
    sim = build()
    base = SimulationOptions(iterations=600, seed=9)

    rows = compare_keep_policies(
        sim.cards, sim.mana, base, baseline="simple", candidate="simple", replicates=3
    )

    assert rows
    assert all(r.difference == 0.0 and r.standard_error == 0.0 for r in rows)
    assert not any(r.significant for r in rows)


def test_comparison_reports_the_trade_off() -> None:
    sim = build()
    base = SimulationOptions(iterations=2_000, seed=3)

    rows = compare_keep_policies(sim.cards, sim.mana, base, replicates=4)

    mulligan = comparison(rows, "fez mulligan")
    assert mulligan.difference > 0 and mulligan.significant  # castable faz mais mulligan
    hand = comparison(rows, "cartas na mão final")
    assert hand.difference < 0  # e termina com a mão um pouco menor
    names = {r.metric for r in rows}
    assert "terrenos sem perder jogada até o turno 4" in names
    assert any("comandante conjurado" in n and "na curva" in n for n in names)


def test_comparison_needs_at_least_two_replicates() -> None:
    sim = build()

    with pytest.raises(ValueError, match="pelo menos 2"):
        compare_keep_policies(sim.cards, sim.mana, SimulationOptions(iterations=100), replicates=1)


def test_metrics_of_a_result_without_the_mana_model() -> None:
    result = run_simulation([-1] * 36 + [2] * 63, SimulationOptions(iterations=200))

    values = metrics_of(result)

    assert "3 fontes de mana no turno 3" not in values
    assert 0.0 <= values["mão inicial mantível"] <= 1.0


def test_new_option_validation() -> None:
    with pytest.raises(ValueError, match="keep_min_effective"):
        SimulationOptions(keep_min_effective=-1)
    with pytest.raises(ValueError, match="ramp_credit_cap"):
        SimulationOptions(ramp_credit_cap=9)
    with pytest.raises(ValueError, match="cantrip_weight"):
        SimulationOptions(cantrip_weight=1.5)
