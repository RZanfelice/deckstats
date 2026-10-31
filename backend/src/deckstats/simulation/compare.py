"""Compara duas políticas de mão mantível nas mesmas partidas.

Cada partida usa a própria semente (``paired_seeds``), então as duas políticas veem os mesmos
embaralhamentos; só muda onde cada uma decide parar. Repete com várias sementes-base e
reporta a diferença média de cada métrica com o erro padrão entre as repetições, que é o
que importa para saber se a diferença é maior que o ruído.

Cuidado ao interpretar: as métricas medem a mana depois da decisão (terrenos, comandante),
não vitórias. Uma política mais exigente faz mais mulligans (mão menor) em troca de mana mais
estável; esta comparação mostra os dois lados, mas não diz qual compensa mais.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from math import sqrt
from statistics import fmean, stdev
from typing import Any

from deckstats.simulation.engine import SimulationResult, run_simulation
from deckstats.simulation.mana import ManaModel
from deckstats.simulation.options import KeepPolicy, SimulationOptions


@dataclass(frozen=True, slots=True)
class MetricComparison:
    metric: str
    baseline: float
    candidate: float
    difference: float  # candidate - baseline, média entre as repetições
    standard_error: float  # erro padrão da diferença entre as repetições

    @property
    def significant(self) -> bool:
        """A diferença passa de 2 erros padrão (aproximadamente 95%)?"""
        return abs(self.difference) > 2 * self.standard_error


def _on_curve_turn(result: SimulationResult) -> int | None:
    if result.mana is None:
        return None
    commander = next((c for c in result.mana.costs if c.source == "commander"), None)
    return commander.on_curve_turn if commander else None


def metrics_of(result: SimulationResult) -> dict[str, float]:
    """Métricas escalares comparáveis de um resultado."""
    values: dict[str, float] = {
        "mão inicial mantível": result.first_hand_keepable.p,
        "fez mulligan": result.mulligans.at_least_one.p if result.mulligans else 0.0,
        "cartas na mão final": result.mulligans.mean_final_hand_size if result.mulligans else 7.0,
        "terrenos sem perder jogada até o turno 3": result.land_drops[3].p,
        "terrenos sem perder jogada até o turno 4": result.land_drops[4].p,
    }
    if result.mana is not None:
        values["3 fontes de mana no turno 3"] = result.mana.sources[3][3].p
        values["4 fontes de mana no turno 4"] = result.mana.sources[4][4].p
        turn = _on_curve_turn(result)
        commander = next((c for c in result.mana.costs if c.source == "commander"), None)
        if commander is not None and turn is not None:
            values[f"comandante conjurado no turno {turn} (na curva)"] = commander.by_turn[turn].p
            if turn + 1 in commander.by_turn:
                values[f"comandante conjurado até o turno {turn + 1}"] = commander.by_turn[
                    turn + 1
                ].p
    return values


def compare_variants(
    cards: Sequence[int],
    mana: ManaModel,
    base: SimulationOptions,
    *,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    replicates: int = 8,
    progress: Callable[[int], None] | None = None,
) -> list[MetricComparison]:
    """Roda duas variantes das opções com as mesmas sementes e resume as diferenças.

    ``baseline`` e ``candidate`` são sobreposições das opções base, por exemplo
    ``{"keep_policy": "simple"}`` e ``{"cast_ramp": True}``.
    """
    if replicates < 2:
        raise ValueError("replicates deve ser pelo menos 2 para estimar o erro padrão")
    base_values: dict[str, list[float]] = {}
    candidate_values: dict[str, list[float]] = {}
    for replicate in range(replicates):
        options = replace(base, paired_seeds=True, seed=base.seed + replicate)
        for overrides, store in ((baseline, base_values), (candidate, candidate_values)):
            result = run_simulation(cards, replace(options, **overrides), mana)
            for name, value in metrics_of(result).items():
                store.setdefault(name, []).append(value)
        if progress:
            progress(replicate + 1)

    comparisons: list[MetricComparison] = []
    for name, baseline_series in base_values.items():
        candidate_series = candidate_values[name]
        diffs = [c - b for b, c in zip(baseline_series, candidate_series, strict=True)]
        spread = stdev(diffs) if len(diffs) > 1 else 0.0
        comparisons.append(
            MetricComparison(
                metric=name,
                baseline=fmean(baseline_series),
                candidate=fmean(candidate_series),
                difference=fmean(diffs),
                standard_error=spread / sqrt(len(diffs)),
            )
        )
    return comparisons


def compare_keep_policies(
    cards: Sequence[int],
    mana: ManaModel,
    base: SimulationOptions,
    *,
    baseline: KeepPolicy = "simple",
    candidate: KeepPolicy = "castable",
    replicates: int = 8,
    progress: Callable[[int], None] | None = None,
) -> list[MetricComparison]:
    """Compara duas políticas de mão mantível nas mesmas partidas."""
    return compare_variants(
        cards,
        mana,
        base,
        baseline={"keep_policy": baseline},
        candidate={"keep_policy": candidate},
        replicates=replicates,
        progress=progress,
    )
