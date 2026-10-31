"""Motor Monte Carlo: mão inicial, mulligan, jogadas de terreno e mana por cor.

Cada iteração embaralha a biblioteca, aplica a política de mulligan (London,
primeiro grátis em Commander), compra uma carta por turno e joga um terreno por
turno quando há. Mede, sobre muitas iterações, a mão jogável (M1), o mulligan
(M2) e a chance de não perder nenhuma jogada de terreno até cada turno (M3).

Com um ``ManaModel``, mede também as fontes de mana (M4), o comandante na curva
(M5) e os custos coloridos (M6), levando em conta cores e terrenos que entram
virados. Sem ele, só usa a contagem de terrenos (caminho rápido).

Sem mulligan, M3 tem fórmula exata (``deck.odds``), que serve de gabarito.
"""

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from deckstats.deck.odds import OPENING_HAND
from deckstats.simulation.estimate import Estimate, estimate
from deckstats.simulation.keep import BOTTOM_LAND_LIMIT, bottom_cards, count_lands, is_keepable
from deckstats.simulation.mana import ManaModel, ManaResult, ManaTally
from deckstats.simulation.options import SimulationOptions

__all__ = [
    "BOTTOM_LAND_LIMIT",
    "MulliganResult",
    "SimulationOptions",
    "SimulationResult",
    "bottom_cards",
    "count_lands",
    "is_keepable",
    "run_simulation",
]

_SEED_STRIDE = 1_000_003


@dataclass(frozen=True, slots=True)
class MulliganResult:
    at_least_one: Estimate
    distribution: dict[int, Estimate]
    mean_final_hand_size: float


@dataclass(frozen=True, slots=True)
class SimulationResult:
    iterations: int
    seed: int
    library_size: int
    lands_in_library: int
    first_hand_keepable: Estimate  # M1
    first_hand_lands: dict[int, Estimate] = field(default_factory=dict)
    mulligans: MulliganResult | None = None  # M2 (None sem apply_mulligan)
    land_drops: dict[int, Estimate] = field(default_factory=dict)  # M3, por turno
    mana: ManaResult | None = None  # M4 a M6 (None sem modelo de mana)


def _choose_land(
    candidates: Sequence[int], colors_in_play: set[str], turn: int, model: ManaModel
) -> int:
    """Política de terrenos: cores que faltam ao comandante primeiro; antes do turno-alvo
    os terrenos que entram virados (não custam nada), a partir dele os desvirados."""
    best = candidates[0]
    best_key: tuple[int, bool, int, int, int] | None = None
    for code in set(candidates):
        land = model.land_types[-1 - code]
        needed_here = land.colors & model.needed_colors
        new_needed = len(needed_here - colors_in_play)
        timing = land.enters_tapped if turn < model.plan_turn else not land.enters_tapped
        key = (new_needed, timing, len(needed_here), len(land.colors), code)
        if best_key is None or key > best_key:
            best_key, best = key, code
    return best


def _play_with_mana(
    hand: Sequence[int],
    library: Sequence[int],
    options: SimulationOptions,
    model: ManaModel,
    tally: ManaTally,
    hits: dict[int, int],
) -> None:
    lands_in_hand = [card for card in hand if card < 0]
    in_play: list[tuple[int, int]] = []  # (tipo de terreno, turno em que entrou)
    colors_in_play: set[str] = set()
    next_card = 0
    for turn in range(1, options.max_turn + 1):
        if not (turn == 1 and options.on_the_play) and next_card < len(library):
            card = library[next_card]
            next_card += 1
            if card < 0:
                lands_in_hand.append(card)
        if lands_in_hand:
            code = _choose_land(lands_in_hand, colors_in_play, turn, model)
            lands_in_hand.remove(code)
            land_index = -1 - code
            in_play.append((land_index, turn))
            colors_in_play |= model.land_types[land_index].colors
        if len(in_play) >= turn:
            hits[turn] += 1
        available = [
            index
            for index, played in in_play
            if played < turn or not model.land_types[index].enters_tapped
        ]
        tally.record(turn, available)


def run_simulation(
    deck: Sequence[int],
    options: SimulationOptions | None = None,
    mana: ManaModel | None = None,
) -> SimulationResult:
    """Simula ``iterations`` jogos sobre a biblioteca ``deck`` (códigos de ``simulation.model``)."""
    options = options or SimulationOptions()
    if options.keep_policy == "castable" and mana is None:
        raise ValueError("a política 'castable' precisa do modelo de mana")
    shared_rng = random.Random(options.seed)
    library_size = len(deck)

    keepable = 0
    first_hand_lands: Counter[int] = Counter()
    mulligan_counts: Counter[int] = Counter()
    final_hand_total = 0
    hits = dict.fromkeys(range(1, options.max_turn + 1), 0)
    tally = ManaTally(mana, options.max_turn) if mana is not None else None
    base = list(deck)

    for iteration in range(options.iterations):
        rng = (
            random.Random(options.seed * _SEED_STRIDE + iteration)
            if options.paired_seeds
            else shared_rng
        )
        cards = base[:]
        rng.shuffle(cards)
        hand = cards[:OPENING_HAND]
        first_hand_lands[count_lands(hand)] += 1
        keepable += is_keepable(hand, options, mana)

        library = cards[OPENING_HAND:]
        if options.apply_mulligan:
            mulligans = 0
            while not is_keepable(hand, options, mana) and mulligans < options.max_mulligans:
                mulligans += 1
                rng.shuffle(cards)
                hand = cards[:OPENING_HAND]
            to_bottom = max(0, mulligans - 1) if options.free_mulligan else mulligans
            hand, bottomed = bottom_cards(hand, to_bottom, mana)
            library = cards[OPENING_HAND:] + bottomed
            mulligan_counts[mulligans] += 1
            final_hand_total += len(hand)

        if mana is not None and tally is not None:
            _play_with_mana(hand, library, options, mana, tally, hits)
            continue

        lands_in_hand = count_lands(hand)
        lands_in_play = 0
        next_card = 0
        for turn in range(1, options.max_turn + 1):
            if not (turn == 1 and options.on_the_play) and next_card < len(library):
                lands_in_hand += library[next_card] < 0
                next_card += 1
            if lands_in_hand:
                lands_in_hand -= 1
                lands_in_play += 1
            if lands_in_play >= turn:
                hits[turn] += 1

    n = options.iterations
    mulligan_result: MulliganResult | None = None
    if options.apply_mulligan:
        mulligan_result = MulliganResult(
            at_least_one=estimate(n - mulligan_counts[0], n),
            distribution={
                m: estimate(mulligan_counts[m], n) for m in range(options.max_mulligans + 1)
            },
            mean_final_hand_size=final_hand_total / n,
        )
    return SimulationResult(
        iterations=n,
        seed=options.seed,
        library_size=library_size,
        lands_in_library=count_lands(base),
        first_hand_keepable=estimate(keepable, n),
        first_hand_lands={k: estimate(first_hand_lands[k], n) for k in range(OPENING_HAND + 1)},
        mulligans=mulligan_result,
        land_drops={turn: estimate(count, n) for turn, count in hits.items()},
        mana=tally.result(n) if tally is not None else None,
    )
