from itertools import combinations
from math import isclose

import pytest

from deckstats.deck.odds import (
    MAX_LANDS,
    MAX_TURN,
    SENSITIVITY_RADIUS,
    TARGET_PROBABILITIES,
    LandCountAnalysis,
    at_least,
    cards_seen,
    compute_land_odds,
    critical_turn,
    hypergeometric_pmf,
    land_count_analysis,
)


def brute_force_at_least(k: int, population: int, successes: int, draws: int) -> float:
    """Gabarito independente: enumera todas as mãos e conta as que têm >= k terrenos."""
    deck = [1] * successes + [0] * (population - successes)
    hands = list(combinations(range(population), draws))
    good = sum(1 for hand in hands if sum(deck[i] for i in hand) >= k)
    return good / len(hands)


@pytest.mark.parametrize("population", [6, 9, 12])
def test_matches_exhaustive_enumeration(population: int) -> None:
    for successes in range(population + 1):
        for draws in range(population + 1):
            for k in range(0, min(successes, draws) + 2):
                expected = brute_force_at_least(k, population, successes, draws)
                assert isclose(at_least(k, population, successes, draws), expected, abs_tol=1e-12)


def test_known_value_by_hand() -> None:
    # 10 cartas, 3 terrenos, 2 compras: 1 - C(7,2)/C(10,2) = 24/45
    assert isclose(at_least(1, 10, 3, 2), 24 / 45)


def test_pmf_sums_to_one() -> None:
    total = sum(hypergeometric_pmf(k, 99, 36, 11) for k in range(0, 12))

    assert isclose(total, 1.0, abs_tol=1e-12)


def test_pmf_outside_the_support_is_zero() -> None:
    assert hypergeometric_pmf(-1, 10, 3, 2) == 0.0
    assert hypergeometric_pmf(3, 10, 3, 2) == 0.0  # só 2 compras
    assert hypergeometric_pmf(0, 10, 9, 5) == 0.0  # com 9 terrenos, 5 compras sempre pegam algum


def test_at_least_edge_cases() -> None:
    assert at_least(0, 99, 36, 11) == 1.0
    assert at_least(-3, 99, 36, 11) == 1.0
    assert at_least(1, 99, 0, 11) == 0.0  # sem terrenos
    assert at_least(12, 99, 36, 11) == 0.0  # mais terrenos que cartas vistas
    assert at_least(1, 99, 99, 11) == 1.0  # só terrenos
    assert at_least(1, 99, 36, 0) == 0.0  # nenhuma compra


def test_probability_never_exceeds_one_and_is_monotone() -> None:
    values = [at_least(4, 99, 36, 7 + turn) for turn in range(1, 11)]

    assert all(0.0 <= v <= 1.0 for v in values)
    assert values == sorted(values)  # mais cartas vistas, mais chance

    by_lands = [at_least(4, 99, lands, 11) for lands in range(20, 45)]
    assert by_lands == sorted(by_lands)  # mais terrenos, mais chance


def test_small_tail_is_computed_accurately() -> None:
    # 1 - cauda inferior perderia precisão aqui; a soma direta da cauda superior não.
    p = at_least(10, 99, 36, 11)

    assert 0 < p < 1e-3
    assert isclose(p, sum(hypergeometric_pmf(i, 99, 36, 11) for i in (10, 11)))


@pytest.mark.parametrize(
    ("population", "successes", "draws"),
    [(-1, 0, 0), (10, 11, 2), (10, -1, 2), (10, 3, 11), (10, 3, -1)],
)
def test_invalid_parameters_are_rejected(population: int, successes: int, draws: int) -> None:
    with pytest.raises(ValueError, match="parâmetros inválidos"):
        at_least(1, population, successes, draws)


# --- turno crítico -----------------------------------------------------------


def test_critical_turn_mixes_commander_and_average() -> None:
    result = critical_turn([4.0], 3.17, commander_weight=0.6)

    assert result is not None
    assert isclose(result.raw, 0.6 * 4.0 + 0.4 * 3.17)
    assert result.turn == 4
    assert result.commander_mana_value == 4.0
    assert result.average_mana_value == 3.17
    assert result.commander_weight == 0.6


def test_expensive_commander_pulls_the_critical_turn_up() -> None:
    cheap = critical_turn([3.0], 3.0)
    pricey = critical_turn([7.0], 3.0)

    assert cheap is not None and pricey is not None
    assert cheap.turn == 3
    assert pricey.turn == 5  # 0,6 * 7 + 0,4 * 3 = 5,4


def test_weight_changes_the_result_for_expensive_commanders() -> None:
    low = critical_turn([7.0], 3.0, commander_weight=0.3)
    high = critical_turn([7.0], 3.0, commander_weight=0.9)

    assert low is not None and high is not None
    assert (low.turn, high.turn) == (4, 7)


@pytest.mark.parametrize(("raw_average", "expected_turn"), [(2.4, 2), (2.5, 3), (2.6, 3)])
def test_rounding_is_half_up_not_bankers(raw_average: float, expected_turn: int) -> None:
    # peso 0: o turno é só o MV médio; round(2.5) do Python daria 2
    result = critical_turn([5.0], raw_average, commander_weight=0.0)

    assert result is not None
    assert result.turn == expected_turn


def test_two_commanders_use_the_mean_of_their_costs() -> None:
    result = critical_turn([2.0, 4.0], 3.0, commander_weight=1.0)

    assert result is not None
    assert result.commander_mana_value == 3.0
    assert result.turn == 3


def test_without_a_commander_only_the_average_counts() -> None:
    result = critical_turn([], 3.4)

    assert result is not None
    assert result.commander_weight == 0.0
    assert result.commander_mana_value is None
    assert result.turn == 3


def test_without_costed_cards_only_the_commander_counts() -> None:
    result = critical_turn([5.0], None)

    assert result is not None
    assert result.commander_weight == 1.0
    assert result.turn == 5


def test_nothing_to_go_on_gives_no_critical_turn() -> None:
    assert critical_turn([], None) is None


def test_critical_turn_is_clamped_to_the_table() -> None:
    assert critical_turn([0.0], 0.0).turn == 1  # type: ignore[union-attr]
    assert critical_turn([16.0], 9.0).turn == MAX_TURN  # type: ignore[union-attr]


@pytest.mark.parametrize("weight", [-0.1, 1.1])
def test_weight_must_be_between_zero_and_one(weight: float) -> None:
    with pytest.raises(ValueError, match="entre 0 e 1"):
        critical_turn([4.0], 3.0, commander_weight=weight)


# --- tabela por turno ---------------------------------------------------------


def test_cards_seen_by_turn() -> None:
    assert cards_seen(1, 99, on_the_play=False) == 8
    assert cards_seen(4, 99, on_the_play=False) == 11
    assert cards_seen(1, 99, on_the_play=True) == 7  # sem compra no turno 1
    assert cards_seen(4, 99, on_the_play=True) == 10
    assert cards_seen(10, 5, on_the_play=False) == 5  # nunca mais que a biblioteca


def test_land_odds_table_shape_and_values() -> None:
    odds = compute_land_odds(
        library_size=99, lands=36, commander_mana_values=[4.0], average_mana_value=3.17
    )

    assert odds is not None
    assert (odds.library_size, odds.lands_in_library, odds.on_the_play) == (99, 36, False)
    assert [t.turn for t in odds.by_turn] == list(range(1, MAX_TURN + 1))
    assert all(sorted(t.p_at_least) == list(range(1, MAX_LANDS + 1)) for t in odds.by_turn)

    turn4 = odds.by_turn[3]
    assert turn4.cards_seen == 11
    assert isclose(turn4.expected_lands, 11 * 36 / 99)
    assert isclose(turn4.p_land_drops, at_least(4, 99, 36, 11))
    assert turn4.p_land_drops == turn4.p_at_least[4]
    assert odds.critical_turn is not None and odds.critical_turn.turn == 4
    assert odds.at_critical_turn is turn4


def test_land_drop_probability_falls_with_the_turn() -> None:
    odds = compute_land_odds(
        library_size=99, lands=36, commander_mana_values=[4.0], average_mana_value=3.0
    )

    assert odds is not None
    drops = [t.p_land_drops for t in odds.by_turn]
    assert drops == sorted(drops, reverse=True)


def test_on_the_play_sees_one_card_less_and_is_less_likely() -> None:
    draw = compute_land_odds(
        library_size=99, lands=36, commander_mana_values=[4.0], average_mana_value=3.0
    )
    play = compute_land_odds(
        library_size=99,
        lands=36,
        commander_mana_values=[4.0],
        average_mana_value=3.0,
        on_the_play=True,
    )

    assert draw is not None and play is not None
    assert play.on_the_play is True
    assert play.by_turn[3].cards_seen == draw.by_turn[3].cards_seen - 1
    assert play.by_turn[3].p_land_drops < draw.by_turn[3].p_land_drops


def test_more_lands_than_cards_are_capped_to_the_library() -> None:
    odds = compute_land_odds(
        library_size=10, lands=15, commander_mana_values=[], average_mana_value=None
    )

    assert odds is not None
    assert odds.lands_in_library == 10
    assert odds.by_turn[0].p_at_least[1] == 1.0
    assert odds.critical_turn is None and odds.at_critical_turn is None


def test_empty_library_has_no_odds() -> None:
    assert (
        compute_land_odds(
            library_size=0, lands=0, commander_mana_values=[], average_mana_value=None
        )
        is None
    )


# --- problema inverso: quantos terrenos o deck precisa -------------------------


def analysis(
    lands: int = 36, turn: int = 4, library: int = 99, on_the_play: bool = False
) -> LandCountAnalysis:
    return land_count_analysis(
        library_size=library, lands=lands, turn=turn, on_the_play=on_the_play
    )


def test_current_probability_matches_the_hypergeometric() -> None:
    result = analysis(lands=36, turn=4)

    assert result.turn == 4
    assert result.cards_seen == 11
    assert result.current_lands == 36
    assert isclose(result.current_probability, at_least(4, 99, 36, 11))


def test_sensitivity_is_centered_on_the_current_deck() -> None:
    result = analysis(lands=36)

    deltas = [point.delta for point in result.sensitivity]
    assert deltas == list(range(-SENSITIVITY_RADIUS, SENSITIVITY_RADIUS + 1))
    assert [point.lands for point in result.sensitivity] == [36 + d for d in deltas]
    current = next(point for point in result.sensitivity if point.delta == 0)
    assert isclose(current.p_land_drops, result.current_probability)


def test_more_lands_never_lower_the_chance() -> None:
    probabilities = [point.p_land_drops for point in analysis().sensitivity]

    assert probabilities == sorted(probabilities)
    assert probabilities[0] < probabilities[-1]


def test_sensitivity_is_clipped_to_valid_land_counts() -> None:
    low = analysis(lands=2)
    high = analysis(lands=98, library=99)

    assert min(point.lands for point in low.sensitivity) == 0
    assert max(point.lands for point in high.sensitivity) == 99


def test_required_lands_are_the_smallest_that_reach_each_target() -> None:
    result = analysis(lands=36, turn=4)

    assert [req.target for req in result.required] == list(TARGET_PROBABILITIES)
    for requirement in result.required:
        assert requirement.lands is not None
        assert at_least(4, 99, requirement.lands, 11) >= requirement.target
        assert at_least(4, 99, requirement.lands - 1, 11) < requirement.target
        assert requirement.delta == requirement.lands - 36


def test_higher_targets_need_more_lands() -> None:
    requirements = analysis().required
    needed = [req.lands for req in requirements if req.lands is not None]

    assert len(needed) == len(requirements)  # nenhuma meta ficou inalcançável
    assert needed == sorted(needed)
    assert len(set(needed)) == len(needed)


def test_a_deck_with_plenty_of_lands_has_negative_deltas() -> None:
    result = analysis(lands=70)

    assert all(req.delta is not None and req.delta < 0 for req in result.required)


def test_unreachable_targets_report_none() -> None:
    # biblioteca de 3 cartas e turno 5: nem uma biblioteca só de terrenos dá 5 terrenos
    result = analysis(lands=2, turn=5, library=3)

    assert [req.lands for req in result.required] == [None, None, None]
    assert [req.delta for req in result.required] == [None, None, None]
    assert result.current_probability == 0.0


def test_on_the_play_needs_at_least_as_many_lands() -> None:
    draw = analysis(on_the_play=False)
    play = analysis(on_the_play=True)

    assert play.cards_seen == draw.cards_seen - 1
    assert play.current_probability < draw.current_probability
    for on_draw, on_play in zip(draw.required, play.required, strict=True):
        assert on_draw.lands is not None and on_play.lands is not None
        assert on_play.lands >= on_draw.lands


def test_compute_land_odds_attaches_the_analysis_for_the_critical_turn() -> None:
    odds = compute_land_odds(
        library_size=99, lands=36, commander_mana_values=[4.0], average_mana_value=3.17
    )

    assert odds is not None and odds.land_count is not None
    assert odds.critical_turn is not None
    assert odds.land_count.turn == odds.critical_turn.turn == 4
    assert odds.at_critical_turn is not None
    assert isclose(odds.land_count.current_probability, odds.at_critical_turn.p_land_drops)


def test_no_land_count_analysis_without_a_critical_turn() -> None:
    odds = compute_land_odds(
        library_size=99, lands=36, commander_mana_values=[], average_mana_value=None
    )

    assert odds is not None
    assert odds.land_count is None
