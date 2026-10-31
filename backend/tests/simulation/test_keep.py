"""A regra de mão mantível por castabilidade (política ``castable``)."""

import pytest

from deckstats.simulation.engine import SimulationOptions, run_simulation
from deckstats.simulation.keep import (
    bottom_cards,
    castable_spells,
    effective_lands,
    is_keepable,
    mana_value,
)
from deckstats.simulation.mana import LandType, ManaModel, SpellType, parse_cost

FOREST = -1  # índice 0 da tabela de terrenos
ISLAND = -2  # índice 1
WASTES = -3  # índice 2 (sem cor: não paga nada)

LAND_TYPES = (
    LandType("Forest", frozenset("G"), False),
    LandType("Island", frozenset("U"), False),
    LandType("Fetch", frozenset(), False),
)

SPELLS = (
    SpellType("Rampant Growth", 2, parse_cost("{1}{G}"), ramp=True),  # 0
    SpellType("Cultivate", 3, parse_cost("{2}{G}"), ramp=True),  # 1
    SpellType("Opt", 1, parse_cost("{U}"), cantrip=True),  # 2
    SpellType("Ponder", 1, parse_cost("{U}"), cantrip=True),  # 3
    SpellType("Brainstorm", 1, parse_cost("{U}"), cantrip=True),  # 4
    SpellType(
        "Dragon",
        6,
        parse_cost("{4}{G}{G}"),
    ),  # 5
    SpellType(
        "Titan",
        7,
        parse_cost("{5}{G}{G}"),
    ),  # 6
    SpellType("Blue Ramp", 2, parse_cost("{1}{U}"), ramp=True),  # 7
    SpellType("Bear", 2, parse_cost("{1}{G}")),  # 8
    SpellType("Sol Ring", 1, parse_cost("{1}"), ramp=True),  # 9
)
RAMP2, RAMP3, OPT, PONDER, BRAIN, DRAGON, TITAN, BLUE_RAMP, BEAR, SOL = range(10)

MODEL = ManaModel(
    land_types=LAND_TYPES,
    targets=(),
    histogram_colors=("G", "U"),
    plan_turn=4,
    needed_colors=frozenset("G"),
    spells=SPELLS,
)

CASTABLE = SimulationOptions(keep_policy="castable")
SIMPLE = SimulationOptions(keep_policy="simple")


def keep(hand: list[int], options: SimulationOptions = CASTABLE) -> bool:
    return is_keepable(hand, options, MODEL)


# --- o exemplo: 2 terrenos e uma rampa ------------------------------------------------------


def test_two_lands_and_a_castable_ramp_is_a_keep() -> None:
    hand = [FOREST, FOREST, RAMP2, DRAGON, DRAGON, TITAN, TITAN]

    assert keep(hand) is True


def test_two_lands_and_a_ramp_that_needs_a_third_land_is_not() -> None:
    hand = [FOREST, FOREST, RAMP3, DRAGON, DRAGON, TITAN, TITAN]

    assert keep(hand) is False


def test_the_simple_policy_cannot_tell_those_two_hands_apart() -> None:
    cheap = [FOREST, FOREST, RAMP2, DRAGON, DRAGON, TITAN, TITAN]
    needs_third = [FOREST, FOREST, RAMP3, DRAGON, DRAGON, TITAN, TITAN]

    assert keep(cheap, SIMPLE) is True
    assert keep(needs_third, SIMPLE) is True


def test_the_third_land_makes_the_same_ramp_castable() -> None:
    hand = [FOREST, FOREST, FOREST, RAMP3, DRAGON, DRAGON, TITAN]

    assert keep(hand) is True


# --- cores -------------------------------------------------------------------------------------------


def test_a_spell_of_a_missing_color_is_not_castable() -> None:
    hand = [FOREST, FOREST, BLUE_RAMP, DRAGON, DRAGON, TITAN, TITAN]

    assert [s.name for s in castable_spells(hand, MODEL)] == []
    assert keep(hand) is False


def test_the_right_colors_make_it_castable() -> None:
    hand = [FOREST, ISLAND, BLUE_RAMP, DRAGON, DRAGON, TITAN, TITAN]

    assert [s.name for s in castable_spells(hand, MODEL)] == ["Blue Ramp"]
    assert keep(hand) is True


def test_a_land_that_makes_no_mana_does_not_pay_for_anything() -> None:
    hand = [FOREST, WASTES, RAMP2, DRAGON, DRAGON, TITAN, TITAN]

    assert castable_spells(hand, MODEL) == []


# --- crédito de terreno efetivo ---------------------------------------------------------------------------


def test_castable_ramp_counts_as_an_extra_land() -> None:
    hand = [FOREST, FOREST, RAMP2, DRAGON, DRAGON, TITAN, TITAN]

    assert effective_lands(hand, CASTABLE, MODEL) == 3.0


def test_uncastable_ramp_earns_no_credit() -> None:
    hand = [FOREST, FOREST, RAMP3, DRAGON, DRAGON, TITAN, TITAN]

    assert effective_lands(hand, CASTABLE, MODEL) == 2.0


def test_ramp_credit_is_capped() -> None:
    hand = [FOREST, FOREST, RAMP2, SOL, BEAR, DRAGON, TITAN]  # duas rampas castáveis

    assert effective_lands(hand, SimulationOptions(ramp_credit_cap=1), MODEL) == 3.0
    assert effective_lands(hand, SimulationOptions(ramp_credit_cap=2), MODEL) == 4.0
    assert effective_lands(hand, SimulationOptions(ramp_credit_cap=0), MODEL) == 2.0


def test_cantrips_count_as_half_a_land_up_to_two_of_them() -> None:
    hand = [ISLAND, ISLAND, OPT, PONDER, BRAIN, DRAGON, TITAN]

    assert effective_lands(hand, CASTABLE, MODEL) == 3.0  # 2 + 0,5 x 2 (o terceiro não conta)


def test_two_lands_and_cantrips_is_a_keep_but_one_cantrip_is_not_enough() -> None:
    assert keep([ISLAND, ISLAND, OPT, PONDER, DRAGON, DRAGON, TITAN]) is True
    assert keep([ISLAND, ISLAND, OPT, DRAGON, DRAGON, TITAN, TITAN]) is True  # 2,5 >= 2,5
    strict = SimulationOptions(keep_policy="castable", keep_min_effective=3.0)
    assert keep([ISLAND, ISLAND, OPT, DRAGON, DRAGON, TITAN, TITAN], strict) is False


def test_the_cantrip_weight_can_be_turned_off() -> None:
    options = SimulationOptions(keep_policy="castable", cantrip_weight=0.0)
    hand = [ISLAND, ISLAND, OPT, PONDER, DRAGON, DRAGON, TITAN]

    assert effective_lands(hand, options, MODEL) == 2.0
    assert keep(hand, options) is False


# --- limites -------------------------------------------------------------------------------------------------


def test_too_many_real_lands_is_flood_even_with_ramp() -> None:
    hand = [FOREST] * 6 + [RAMP2]

    assert keep(hand) is False


def test_real_lands_below_the_minimum_are_never_enough() -> None:
    hand = [FOREST, SOL, OPT, PONDER, BEAR, DRAGON, TITAN]  # 1 terreno + créditos

    assert keep(hand) is False


def test_three_lands_and_a_cheap_castable_play_is_a_keep() -> None:
    assert keep([FOREST, FOREST, FOREST, BEAR, DRAGON, TITAN, TITAN]) is True


def test_three_lands_with_no_cheap_castable_play_is_not() -> None:
    assert keep([FOREST, FOREST, FOREST, DRAGON, TITAN, DRAGON, TITAN]) is False


def test_a_cheap_spell_that_cannot_be_cast_does_not_count_as_the_play() -> None:
    # 3 Forest e só uma magia azul barata: não há jogada castável
    assert keep([FOREST, FOREST, FOREST, OPT, DRAGON, TITAN, TITAN]) is False
    assert keep([FOREST, FOREST, FOREST, OPT, DRAGON, TITAN, TITAN], SIMPLE) is True


def test_the_keep_play_limit_is_a_parameter() -> None:
    hand = [FOREST, FOREST, FOREST, BEAR, DRAGON, TITAN, TITAN]  # a única jogada castável custa 2
    strict = SimulationOptions(keep_policy="castable", keep_max_spell_mv=1)

    assert keep(hand) is True
    assert keep(hand, strict) is False  # o Bear (MV 2) passa do limite de 1


# --- tabela de magias e fundo da biblioteca ------------------------------------------------------------------


def test_mana_value_reads_the_spell_table() -> None:
    assert mana_value(FOREST, MODEL) == -1
    assert mana_value(DRAGON, MODEL) == 6
    assert mana_value(5, None) == 5  # códigos legados: o próprio valor de mana


def test_the_simple_policy_reads_mana_values_from_the_table() -> None:
    # 2 terrenos + Opt (MV 1): mantém; 2 terrenos + só magias caras: não
    assert keep([FOREST, FOREST, OPT, DRAGON, TITAN, DRAGON, TITAN], SIMPLE) is True
    assert keep([FOREST, FOREST, DRAGON, TITAN, DRAGON, TITAN, DRAGON], SIMPLE) is False


def test_bottoming_uses_the_spell_table_to_find_the_most_expensive_card() -> None:
    kept, bottomed = bottom_cards([FOREST, FOREST, OPT, DRAGON, TITAN, BEAR, SOL], 2, MODEL)

    assert [MODEL.spells[c].name for c in bottomed] == ["Titan", "Dragon"]
    assert sorted(kept) == sorted([FOREST, FOREST, OPT, BEAR, SOL])


def test_castable_needs_the_mana_model() -> None:
    with pytest.raises(ValueError, match="modelo de mana"):
        is_keepable([FOREST, FOREST, 1], CASTABLE)
    with pytest.raises(ValueError, match="modelo de mana"):
        run_simulation([FOREST] * 36 + [2] * 63, SimulationOptions(keep_policy="castable"))
