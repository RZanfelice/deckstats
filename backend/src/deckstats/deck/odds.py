"""Probabilidade de terrenos por turno (hipergeométrica) e o turno crítico do deck.

Modelo: a biblioteca é o deck sem o comandante (que fica na zona de comando) e
cada compra é uma retirada sem reposição. Em Commander com mais de 2 jogadores
todos compram no turno 1, então no turno T o jogador viu ``7 + T`` cartas; no
"play" (jogo de 2 jogadores, quem começa pula a compra) vê ``7 + T - 1``.

O que isto mede e o que não mede: é a chance de **comprar** terrenos. Não
considera mulligan, cores, nem o fato de que pedras e rampa precisam ser
conjuradas antes de produzir mana; isso é papel da simulação Monte Carlo.

Turno crítico: um único turno-alvo para o deck, mistura do custo do comandante
com o custo médio das demais cartas::

    bruto = w * MV(comandante) + (1 - w) * MV médio (sem terrenos)
    turno = bruto arredondado (meio para cima), entre 1 e MAX_TURN

É uma heurística transparente, não uma grandeza física: a resposta traz o valor
bruto, os dois insumos e o peso usado.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import comb, floor
from statistics import mean

DEFAULT_COMMANDER_WEIGHT = 0.6
OPENING_HAND = 7
MAX_TURN = 10
MAX_LANDS = 10
# Metas de "não perder nenhum terreno até o turno crítico" e quantos terrenos a mais/menos
# a tabela de sensibilidade mostra em torno do deck atual.
TARGET_PROBABILITIES = (0.7, 0.8, 0.9)
SENSITIVITY_RADIUS = 5


def hypergeometric_pmf(k: int, population: int, successes: int, draws: int) -> float:
    """P(X = k): k terrenos em ``draws`` cartas de uma biblioteca de ``population``."""
    _validate(population, successes, draws)
    if k < 0 or k > min(successes, draws):
        return 0.0
    return comb(successes, k) * comb(population - successes, draws - k) / comb(population, draws)


def at_least(k: int, population: int, successes: int, draws: int) -> float:
    """P(X >= k). Soma a cauda superior, mais precisa para probabilidades pequenas."""
    _validate(population, successes, draws)
    if k <= 0:
        return 1.0
    top = min(successes, draws)
    if k > top:
        return 0.0
    total = sum(hypergeometric_pmf(i, population, successes, draws) for i in range(k, top + 1))
    return min(1.0, total)


def _validate(population: int, successes: int, draws: int) -> None:
    if population < 0 or not 0 <= successes <= population or not 0 <= draws <= population:
        raise ValueError(
            f"parâmetros inválidos: população={population}, sucessos={successes}, compras={draws}"
        )


@dataclass(frozen=True, slots=True)
class CriticalTurn:
    raw: float
    turn: int
    commander_mana_value: float | None
    average_mana_value: float | None
    commander_weight: float


def critical_turn(
    commander_mana_values: Sequence[float],
    average_mana_value: float | None,
    commander_weight: float = DEFAULT_COMMANDER_WEIGHT,
) -> CriticalTurn | None:
    """Turno crítico do deck. ``None`` se não há comandante nem cartas com custo.

    Com dois comandantes usa a média dos custos. Sem comandante, vale só a média
    das cartas (peso efetivo 0); sem cartas com custo, só o comandante (peso 1).
    """
    if not 0 <= commander_weight <= 1:
        raise ValueError(
            f"o peso do comandante deve estar entre 0 e 1, recebido {commander_weight}"
        )
    commander = mean(commander_mana_values) if commander_mana_values else None
    if commander is None and average_mana_value is None:
        return None
    if commander is None:
        weight, raw = 0.0, float(average_mana_value or 0.0)
    elif average_mana_value is None:
        weight, raw = 1.0, float(commander)
    else:
        weight = commander_weight
        raw = weight * commander + (1 - weight) * average_mana_value
    turn = min(MAX_TURN, max(1, floor(raw + 0.5)))
    return CriticalTurn(
        raw=raw,
        turn=turn,
        commander_mana_value=commander,
        average_mana_value=average_mana_value,
        commander_weight=weight,
    )


@dataclass(frozen=True, slots=True)
class TurnOdds:
    turn: int
    cards_seen: int
    expected_lands: float
    # P(ter jogado todos os terrenos até este turno) = P(>= turno terrenos nas cartas vistas)
    p_land_drops: float
    # P(>= k terrenos nas cartas vistas), para k de 1 a MAX_LANDS
    p_at_least: dict[int, float]


@dataclass(frozen=True, slots=True)
class LandCountPoint:
    lands: int
    delta: int  # em relação aos terrenos atuais do deck
    p_land_drops: float


@dataclass(frozen=True, slots=True)
class LandRequirement:
    target: float
    # Menor número de terrenos que atinge a meta; None se nem uma biblioteca só de terrenos basta.
    lands: int | None
    # lands - terrenos atuais: positivo falta, negativo já passa da meta com folga.
    delta: int | None


@dataclass(frozen=True, slots=True)
class LandCountAnalysis:
    """Quantos terrenos o deck precisa para o turno crítico (o problema inverso)."""

    turn: int
    cards_seen: int
    current_lands: int
    current_probability: float
    sensitivity: list[LandCountPoint]
    required: list[LandRequirement]


@dataclass(frozen=True, slots=True)
class LandOdds:
    library_size: int
    lands_in_library: int
    on_the_play: bool
    critical_turn: CriticalTurn | None
    by_turn: list[TurnOdds]
    at_critical_turn: TurnOdds | None
    land_count: LandCountAnalysis | None


def cards_seen(turn: int, library_size: int, on_the_play: bool) -> int:
    seen = OPENING_HAND + turn - (1 if on_the_play else 0)
    return min(seen, library_size)


def land_count_analysis(
    *, library_size: int, lands: int, turn: int, on_the_play: bool
) -> LandCountAnalysis:
    """Chance de não perder nenhum terreno até ``turn`` conforme o número de terrenos.

    Para cada quantidade de terrenos ``K``, ``P(K) = P(>= turn terrenos nas cartas vistas)``.
    ``P`` cresce com ``K``, então a menor quantidade que atinge cada meta é achada varrendo
    ``K`` de 0 até a biblioteca inteira.
    """
    seen = cards_seen(turn, library_size, on_the_play)

    def probability(total_lands: int) -> float:
        return at_least(turn, library_size, total_lands, seen)

    low = max(0, lands - SENSITIVITY_RADIUS)
    high = min(library_size, lands + SENSITIVITY_RADIUS)
    sensitivity = [
        LandCountPoint(lands=total, delta=total - lands, p_land_drops=probability(total))
        for total in range(low, high + 1)
    ]

    required: list[LandRequirement] = []
    for target in TARGET_PROBABILITIES:
        needed = next((n for n in range(library_size + 1) if probability(n) >= target), None)
        required.append(
            LandRequirement(
                target=target,
                lands=needed,
                delta=None if needed is None else needed - lands,
            )
        )

    return LandCountAnalysis(
        turn=turn,
        cards_seen=seen,
        current_lands=lands,
        current_probability=probability(lands),
        sensitivity=sensitivity,
        required=required,
    )


def compute_land_odds(
    *,
    library_size: int,
    lands: int,
    commander_mana_values: Sequence[float],
    average_mana_value: float | None,
    commander_weight: float = DEFAULT_COMMANDER_WEIGHT,
    on_the_play: bool = False,
) -> LandOdds | None:
    """Probabilidades de terrenos por turno. ``None`` se a biblioteca está vazia."""
    if library_size <= 0:
        return None
    lands = min(lands, library_size)

    by_turn: list[TurnOdds] = []
    for turn in range(1, MAX_TURN + 1):
        seen = cards_seen(turn, library_size, on_the_play)
        by_turn.append(
            TurnOdds(
                turn=turn,
                cards_seen=seen,
                expected_lands=seen * lands / library_size,
                p_land_drops=at_least(turn, library_size, lands, seen),
                p_at_least={
                    k: at_least(k, library_size, lands, seen) for k in range(1, MAX_LANDS + 1)
                },
            )
        )

    critical = critical_turn(commander_mana_values, average_mana_value, commander_weight)
    return LandOdds(
        library_size=library_size,
        lands_in_library=lands,
        on_the_play=on_the_play,
        critical_turn=critical,
        by_turn=by_turn,
        at_critical_turn=by_turn[critical.turn - 1] if critical else None,
        land_count=(
            land_count_analysis(
                library_size=library_size,
                lands=lands,
                turn=critical.turn,
                on_the_play=on_the_play,
            )
            if critical
            else None
        ),
    )
