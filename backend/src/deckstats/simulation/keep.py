"""Regra de mão mantível e escolha das cartas para o fundo (mulligan London).

Duas políticas (``SimulationOptions.keep_policy``):

* ``simple``: de ``keep_min_lands`` a ``keep_max_lands`` terrenos e pelo menos uma magia com
  valor de mana até ``keep_max_spell_mv``. Não relaciona a magia aos terrenos da mão.
* ``castable``: o que conta é o que **dá para conjurar com os terrenos da mão** (cores
  incluídas). Rampa castável vale como terreno extra (no máximo ``ramp_credit_cap``) e
  cantrips baratos castáveis valem ``cantrip_weight`` de terreno (no máximo dois). A mão é
  mantida se os terrenos reais ficam no intervalo, os terrenos efetivos chegam a
  ``keep_min_effective`` e existe uma magia castável de valor de mana até ``keep_max_spell_mv``.

A castabilidade olha só os terrenos já na mão. Quem tem 2 terrenos e uma rampa de custo 3 não a
conta (ela depende de comprar o terceiro terreno).
"""

from collections.abc import Sequence

from deckstats.simulation.mana import ManaModel, SpellType, can_pay
from deckstats.simulation.options import SimulationOptions

# Com mais terrenos que isto na mão, o London coloca um terreno no fundo; senão, a magia mais cara.
BOTTOM_LAND_LIMIT = 4
_CANTRIP_CREDIT_CAP = 2  # no máximo dois cantrips contam como fração de terreno


def count_lands(cards: Sequence[int]) -> int:
    """Terrenos têm código negativo (ver ``simulation.model``)."""
    return sum(1 for card in cards if card < 0)


def mana_value(code: int, mana: ManaModel | None) -> int:
    """Valor de mana de uma carta da biblioteca (terrenos valem -1)."""
    if code < 0:
        return -1
    if mana is not None and mana.spells:
        return mana.spells[code].mana_value
    return code


def _spells_in(hand: Sequence[int], mana: ManaModel) -> list[SpellType]:
    return [mana.spells[card] for card in hand if card >= 0]


def _simple(hand: Sequence[int], options: SimulationOptions, mana: ManaModel | None) -> bool:
    if not options.keep_min_lands <= count_lands(hand) <= options.keep_max_lands:
        return False
    return any(0 <= mana_value(card, mana) <= options.keep_max_spell_mv for card in hand)


def castable_spells(hand: Sequence[int], mana: ManaModel) -> list[SpellType]:
    """Magias da mão que dá para pagar com os terrenos que já estão na mão."""
    lands = [mana.land_types[-1 - card].colors for card in hand if card < 0]
    return [spell for spell in _spells_in(hand, mana) if can_pay(spell.cost, lands)]


def effective_lands(hand: Sequence[int], options: SimulationOptions, mana: ManaModel) -> float:
    """Terrenos da mão mais o crédito da rampa e dos cantrips castáveis."""
    castable = castable_spells(hand, mana)
    ramp = min(options.ramp_credit_cap, sum(1 for spell in castable if spell.ramp))
    cantrips = min(_CANTRIP_CREDIT_CAP, sum(1 for spell in castable if spell.cantrip))
    return count_lands(hand) + ramp + options.cantrip_weight * cantrips


def _castable(hand: Sequence[int], options: SimulationOptions, mana: ManaModel) -> bool:
    if not options.keep_min_lands <= count_lands(hand) <= options.keep_max_lands:
        return False
    if effective_lands(hand, options, mana) < options.keep_min_effective:
        return False
    return any(
        spell.mana_value <= options.keep_max_spell_mv for spell in castable_spells(hand, mana)
    )


def is_keepable(
    hand: Sequence[int], options: SimulationOptions, mana: ManaModel | None = None
) -> bool:
    if options.keep_policy == "castable":
        if mana is None:
            raise ValueError("a política 'castable' precisa do modelo de mana")
        return _castable(hand, options, mana)
    return _simple(hand, options, mana)


def bottom_cards(
    hand: Sequence[int], count: int, mana: ManaModel | None = None
) -> tuple[list[int], list[int]]:
    """London: devolve (mão que fica, cartas para o fundo da biblioteca)."""
    kept = list(hand)
    bottomed: list[int] = []
    for _ in range(min(count, len(kept))):
        if count_lands(kept) > BOTTOM_LAND_LIMIT:
            card = next(c for c in kept if c < 0)
        else:
            # a magia mais cara; só terrenos: um terreno
            card = max(kept, key=lambda c: (mana_value(c, mana), c))
        kept.remove(card)
        bottomed.append(card)
    return kept, bottomed
