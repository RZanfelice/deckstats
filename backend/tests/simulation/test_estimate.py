import pytest

from deckstats.simulation.estimate import estimate


def test_proportion_and_sample_size() -> None:
    result = estimate(25, 100)

    assert result.p == 0.25
    assert result.n == 100


def test_wilson_interval_for_a_half() -> None:
    result = estimate(50, 100)

    assert result.ci_low == pytest.approx(0.4038, abs=1e-3)
    assert result.ci_high == pytest.approx(0.5962, abs=1e-3)


def test_interval_stays_inside_zero_and_one_at_the_extremes() -> None:
    none = estimate(0, 100)
    every = estimate(100, 100)

    assert none.ci_low == 0.0
    assert none.ci_high == pytest.approx(0.0370, abs=1e-3)
    assert every.ci_high == 1.0
    assert every.ci_low == pytest.approx(0.9630, abs=1e-3)


def test_interval_contains_the_estimate_and_narrows_with_more_samples() -> None:
    small = estimate(30, 100)
    large = estimate(3000, 10_000)

    assert small.ci_low <= small.p <= small.ci_high
    assert large.ci_low <= large.p <= large.ci_high
    assert (large.ci_high - large.ci_low) < (small.ci_high - small.ci_low) / 5


@pytest.mark.parametrize(("successes", "n"), [(0, 0), (-1, 10), (11, 10)])
def test_invalid_counts_are_rejected(successes: int, n: int) -> None:
    with pytest.raises(ValueError, match="contagem inválida"):
        estimate(successes, n)


@pytest.mark.parametrize("n", [1, 2, 7, 100, 199, 200, 1_000, 10_000, 30_000])
def test_interval_always_contains_the_estimate_even_at_the_extremes(n: int) -> None:
    for successes in {0, 1, n // 2, n - 1, n}:
        if not 0 <= successes <= n:
            continue
        result = estimate(successes, n)
        assert 0.0 <= result.ci_low <= result.p <= result.ci_high <= 1.0, (successes, n)
