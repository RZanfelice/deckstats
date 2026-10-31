from math import sqrt
from typing import Any

import pytest

from deckstats.deck.odds import at_least, cards_seen
from deckstats.simulation.engine import (
    SimulationOptions,
    bottom_cards,
    is_keepable,
    run_simulation,
)
from deckstats.simulation.model import LAND


def library(lands: int, spell_mv: int = 3, size: int = 99) -> list[int]:
    return [LAND] * lands + [spell_mv] * (size - lands)


def hand(lands: int, *spells: int) -> list[int]:
    return [LAND] * lands + list(spells)


# --- validação contra a fórmula exata -----------------------------------------


@pytest.mark.parametrize(
    ("lands", "on_the_play"), [(30, False), (36, False), (36, True), (42, False)]
)
def test_land_drops_without_mulligan_match_the_hypergeometric(
    lands: int, on_the_play: bool
) -> None:
    options = SimulationOptions(
        iterations=20_000, seed=1, apply_mulligan=False, on_the_play=on_the_play
    )

    result = run_simulation(library(lands), options)

    for turn in range(1, 9):
        exact = at_least(turn, 99, lands, cards_seen(turn, 99, on_the_play))
        sigma = sqrt(exact * (1 - exact) / options.iterations)
        simulated = result.land_drops[turn].p
        assert abs(simulated - exact) <= 4 * sigma + 1e-9, (turn, simulated, exact)


def test_estimates_are_unbiased_and_intervals_are_calibrated_across_seeds() -> None:
    """Os 10 turnos de uma semente usam as mesmas partidas (erros correlacionados), então a
    calibração se mede entre sementes: o z-score médio fica perto de 0 e o IC de 95% contém o
    valor exato em cerca de 9,5 dos 10 turnos (uma semente isolada pode cair em 7)."""
    n = 10_000
    covered: list[int] = []
    z_scores: list[float] = []
    for seed in range(10):
        options = SimulationOptions(iterations=n, seed=seed, apply_mulligan=False)
        result = run_simulation(library(36), options)
        hits = 0
        for turn in range(1, 11):
            exact = at_least(turn, 99, 36, cards_seen(turn, 99, False))
            z_scores.append((result.land_drops[turn].p - exact) / sqrt(exact * (1 - exact) / n))
            hits += result.land_drops[turn].ci_low <= exact <= result.land_drops[turn].ci_high
        covered.append(hits)

    assert sum(covered) / len(covered) >= 8.8
    assert abs(sum(z_scores) / len(z_scores)) < 0.4


def test_first_hand_land_distribution_matches_the_expected_mean() -> None:
    result = run_simulation(library(36), SimulationOptions(iterations=20_000, seed=3))

    mean = sum(k * e.p for k, e in result.first_hand_lands.items())

    assert sum(e.p for e in result.first_hand_lands.values()) == pytest.approx(1.0)
    assert mean == pytest.approx(7 * 36 / 99, abs=0.05)


# --- propriedades --------------------------------------------------------------


def test_same_seed_gives_identical_results_and_other_seeds_differ() -> None:
    options = SimulationOptions(iterations=2_000, seed=5)

    first = run_simulation(library(36), options)
    again = run_simulation(library(36), options)
    other = run_simulation(library(36), SimulationOptions(iterations=2_000, seed=6))

    assert first == again
    assert first.land_drops != other.land_drops


def test_more_lands_raise_the_chance_of_hitting_land_drops() -> None:
    options = SimulationOptions(iterations=5_000, seed=2)

    few = run_simulation(library(30), options)
    many = run_simulation(library(42), options)

    assert many.land_drops[4].p > few.land_drops[4].p + 0.1


def test_land_drop_probability_never_rises_with_the_turn() -> None:
    options = SimulationOptions(iterations=5_000, seed=2, apply_mulligan=False)

    result = run_simulation(library(36), options)

    values = [result.land_drops[t].p for t in range(1, 11)]
    assert values == sorted(values, reverse=True)


def test_on_the_play_is_less_likely_to_hit_land_drops() -> None:
    draw = SimulationOptions(iterations=10_000, seed=4, apply_mulligan=False)
    play = SimulationOptions(iterations=10_000, seed=4, apply_mulligan=False, on_the_play=True)

    on_draw = run_simulation(library(36), draw)
    on_play = run_simulation(library(36), play)

    assert on_play.land_drops[4].p < on_draw.land_drops[4].p


def test_the_mulligan_policy_does_not_hurt_land_drops() -> None:
    with_policy = run_simulation(library(36), SimulationOptions(iterations=20_000, seed=8))
    without = run_simulation(
        library(36), SimulationOptions(iterations=20_000, seed=8, apply_mulligan=False)
    )

    assert with_policy.land_drops[3].p >= without.land_drops[3].p - 0.01


# --- mão inicial e mulligan ---------------------------------------------------------


def test_mulligan_probability_is_one_minus_keepable() -> None:
    result = run_simulation(library(36), SimulationOptions(iterations=5_000, seed=1))

    assert result.mulligans is not None
    assert result.mulligans.at_least_one.p == pytest.approx(1 - result.first_hand_keepable.p)
    assert sum(e.p for e in result.mulligans.distribution.values()) == pytest.approx(1.0)
    assert result.mulligans.distribution[0].p == pytest.approx(result.first_hand_keepable.p)


def test_a_typical_deck_keeps_most_hands() -> None:
    result = run_simulation(library(36), SimulationOptions(iterations=10_000, seed=1))

    assert 0.7 < result.first_hand_keepable.p < 0.95


def test_no_mulligan_stats_when_the_policy_is_not_applied() -> None:
    result = run_simulation(library(36), SimulationOptions(iterations=500, apply_mulligan=False))

    assert result.mulligans is None
    assert result.first_hand_keepable.n == 500


def test_hand_without_a_cheap_spell_is_not_keepable() -> None:
    result = run_simulation(library(36, spell_mv=6), SimulationOptions(iterations=2_000, seed=1))

    assert result.first_hand_keepable.p == 0.0


@pytest.mark.parametrize(
    ("free", "max_mulligans", "expected_hand"),
    [(True, 3, 5.0), (False, 3, 4.0), (True, 1, 7.0), (False, 1, 6.0)],
)
def test_london_mulligan_bottoms_cards_and_the_first_one_is_free(
    free: bool, max_mulligans: int, expected_hand: float
) -> None:
    # Só terrenos: nunca é mantível (não há magia), então faz sempre o máximo de mulligans.
    options = SimulationOptions(iterations=200, free_mulligan=free, max_mulligans=max_mulligans)

    result = run_simulation([LAND] * 99, options)

    assert result.mulligans is not None
    assert result.mulligans.distribution[max_mulligans].p == 1.0
    assert result.mulligans.mean_final_hand_size == expected_hand


def test_a_deck_with_no_lands_never_makes_a_land_drop() -> None:
    result = run_simulation([3] * 99, SimulationOptions(iterations=500, seed=1))

    assert all(e.p == 0.0 for e in result.land_drops.values())
    assert result.first_hand_keepable.p == 0.0


def test_a_deck_of_only_lands_always_makes_land_drops_without_mulligan() -> None:
    options = SimulationOptions(iterations=500, seed=1, apply_mulligan=False)

    result = run_simulation([LAND] * 99, options)

    assert all(e.p == 1.0 for e in result.land_drops.values())


# --- regras unitárias -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cards", "expected"),
    [
        (hand(3, 1, 2, 5, 6), True),
        (hand(2, 3, 5, 6, 7, 7), True),  # 2 terrenos e uma magia de MV 3
        (hand(1, 1, 1, 1, 1, 1, 1), False),  # terrenos de menos
        (hand(6, 1), False),  # terrenos demais
        (hand(5, 2, 2), True),
        (hand(3, 4, 5, 6, 7), False),  # sem magia de MV <= 3
        (hand(3, 0, 6, 6, 6), True),  # MV 0 conta como barata
    ],
)
def test_is_keepable(cards: list[int], expected: bool) -> None:
    assert is_keepable(cards, SimulationOptions()) is expected


def test_keep_limits_are_parameters() -> None:
    strict = SimulationOptions(keep_min_lands=3, keep_max_lands=4)

    assert is_keepable(hand(2, 1, 1, 1, 1, 1), SimulationOptions()) is True
    assert is_keepable(hand(2, 1, 1, 1, 1, 1), strict) is False


def test_bottoming_prefers_a_land_when_there_are_too_many() -> None:
    kept, bottomed = bottom_cards(hand(5, 1, 6), 1)

    assert bottomed == [LAND]
    assert kept.count(LAND) == 4


def test_bottoming_otherwise_removes_the_most_expensive_spell() -> None:
    kept, bottomed = bottom_cards(hand(3, 1, 6, 4, 2), 2)

    assert bottomed == [6, 4]
    assert sorted(kept) == [LAND, LAND, LAND, 1, 2]


def test_bottoming_with_only_lands_removes_lands() -> None:
    kept, bottomed = bottom_cards([LAND, LAND, LAND], 2)

    assert bottomed == [LAND, LAND]
    assert kept == [LAND]


def test_bottoming_never_removes_more_than_the_hand_has() -> None:
    kept, bottomed = bottom_cards([2], 3)

    assert kept == []
    assert bottomed == [2]


def test_bottoming_zero_changes_nothing() -> None:
    assert bottom_cards(hand(3, 1, 2), 0) == (hand(3, 1, 2), [])


@pytest.mark.parametrize(
    "bad",
    [
        {"iterations": 0},
        {"max_mulligans": -1},
        {"max_mulligans": 7},
        {"keep_min_lands": 5, "keep_max_lands": 2},
        {"keep_max_lands": 8},
        {"max_turn": 0},
        {"max_turn": 11},
    ],
)
def test_invalid_options_are_rejected(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        SimulationOptions(**bad)
