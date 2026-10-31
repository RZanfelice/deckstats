"""Estatísticas gerais de um deck.

Convenções (todas ponderadas pela quantidade):

* O deck "principal" são as cartas da seção ``main``; o comandante fica fora
  da curva, da média e das distribuições, e aparece em ``commander_mana_values``.
* Terrenos não entram na curva nem na média. Um terreno é uma carta cuja
  primeira face é ``Land``.
* MDFC com um terreno atrás (``modal_dfc`` cuja frente não é terreno) é uma
  magia para a curva e para as distribuições. Só o total de terrenos muda,
  conforme ``StatsOptions.count_mdfc_lands`` (ligado por padrão).
* Cartas ``split`` e ``aftermath`` somam as cores e os símbolos de mana de
  todas as faces; as demais usam só a primeira face.
"""

import re
from dataclasses import dataclass
from statistics import median

from deckstats.catalog.records import CardRecord, FaceRecord
from deckstats.deck.model import Deck, DeckEntry
from deckstats.deck.odds import DEFAULT_COMMANDER_WEIGHT

COLORS = ("W", "U", "B", "R", "G")
CURVE_CAP = 7
CURVE_LABELS = [str(value) for value in range(CURVE_CAP)] + [f"{CURVE_CAP}+"]
_TYPE_PRIORITY = (
    "Land",
    "Creature",
    "Planeswalker",
    "Battle",
    "Artifact",
    "Enchantment",
    "Instant",
    "Sorcery",
)
_PERMANENT_TYPES = frozenset(
    {"Land", "Creature", "Planeswalker", "Battle", "Artifact", "Enchantment"}
)
_ALL_FACES_LAYOUTS = frozenset({"split", "aftermath"})
_SYMBOL = re.compile(r"\{([^}]+)\}")


@dataclass(frozen=True, slots=True)
class StatsOptions:
    count_mdfc_lands: bool = True
    # Peso do custo do comandante no turno crítico (o resto vai para o MV médio).
    commander_weight: float = DEFAULT_COMMANDER_WEIGHT
    # Jogo de 2 jogadores em que se começa sem comprar no turno 1.
    on_the_play: bool = False


@dataclass(frozen=True, slots=True)
class LandStats:
    lands: int
    mdfc_lands: int
    total: int


@dataclass(frozen=True, slots=True)
class DeckStats:
    played_cards: int
    main_cards: int
    nonland_cards: int
    lands: LandStats
    curve: dict[str, int]
    average_mana_value: float | None
    median_mana_value: float | None
    commander_mana_values: list[float]
    card_colors: dict[str, int]
    multicolor_cards: int
    pips: dict[str, int]
    color_identity: list[str]
    types: dict[str, int]
    permanents: dict[str, int]


def is_land(card: CardRecord) -> bool:
    return "Land" in card.faces[0].types


def is_mdfc_land(card: CardRecord) -> bool:
    """MDFC jogável como terreno, cuja frente é uma magia."""
    return (
        card.layout == "modal_dfc"
        and not is_land(card)
        and any("Land" in face.types for face in card.faces[1:])
    )


def castable_faces(card: CardRecord) -> list[FaceRecord]:
    return card.faces if card.layout in _ALL_FACES_LAYOUTS else card.faces[:1]


def primary_type(card: CardRecord) -> str:
    types = set(card.faces[0].types)
    return next((kind for kind in _TYPE_PRIORITY if kind in types), "Other")


def count_pips(mana_cost: str | None) -> dict[str, int]:
    """Símbolos de mana por cor. Híbridos contam para cada cor que oferecem."""
    pips = dict.fromkeys(COLORS, 0)
    for symbol in _SYMBOL.findall(mana_cost or ""):
        for part in symbol.split("/"):
            if part in pips:
                pips[part] += 1
    return pips


def _expand(entries: list[DeckEntry]) -> list[CardRecord]:
    return [entry.card for entry in entries for _ in range(entry.quantity)]


def _curve(spells: list[CardRecord]) -> dict[str, int]:
    curve = dict.fromkeys(CURVE_LABELS, 0)
    for card in spells:
        curve[CURVE_LABELS[min(int(card.mana_value), CURVE_CAP)]] += 1
    return curve


def compute_stats(deck: Deck, options: StatsOptions | None = None) -> DeckStats:
    options = options or StatsOptions()
    main = _expand(deck.main)
    spells = [card for card in main if not is_land(card)]
    true_lands = sum(1 for card in main if is_land(card))
    mdfc_lands = sum(1 for card in spells if is_mdfc_land(card))

    values = [card.mana_value for card in spells]
    card_colors = dict.fromkeys((*COLORS, "colorless"), 0)
    pips = dict.fromkeys(COLORS, 0)
    multicolor = 0
    for card in spells:
        colors = {color for face in castable_faces(card) for color in face.colors}
        for color in colors:
            card_colors[color] += 1
        if not colors:
            card_colors["colorless"] += 1
        if len(colors) > 1:
            multicolor += 1
        for face in castable_faces(card):
            for color, amount in count_pips(face.mana_cost).items():
                pips[color] += amount

    types = dict.fromkeys(_TYPE_PRIORITY, 0)
    permanents = {"permanent": 0, "non_permanent": 0}
    for card in main:
        kind = primary_type(card)
        types[kind] = types.get(kind, 0) + 1
        permanents["permanent" if kind in _PERMANENT_TYPES else "non_permanent"] += 1

    identity = {color for entry in deck.played for color in entry.card.color_identity}

    return DeckStats(
        played_cards=deck.played_count,
        main_cards=len(main),
        nonland_cards=len(spells),
        lands=LandStats(
            lands=true_lands,
            mdfc_lands=mdfc_lands,
            total=true_lands + (mdfc_lands if options.count_mdfc_lands else 0),
        ),
        curve=_curve(spells),
        average_mana_value=round(sum(values) / len(values), 2) if values else None,
        median_mana_value=float(median(values)) if values else None,
        commander_mana_values=[entry.card.mana_value for entry in deck.commanders],
        card_colors=card_colors,
        multicolor_cards=multicolor,
        pips=pips,
        color_identity=[color for color in COLORS if color in identity],
        types=types,
        permanents=permanents,
    )
