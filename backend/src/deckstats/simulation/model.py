"""Do deck para a lista de cartas que a simulação embaralha."""

from collections.abc import Sequence
from dataclasses import dataclass

from deckstats.catalog.records import CardRecord, FaceRecord
from deckstats.classification import taxonomy as taxonomy
from deckstats.classification.classifier import classify_card
from deckstats.deck.model import Deck
from deckstats.deck.odds import MAX_TURN
from deckstats.deck.stats import COLORS, castable_faces, count_pips, is_land, is_mdfc_land
from deckstats.simulation.mana import (
    COLORLESS,
    LandType,
    ManaModel,
    SpellType,
    Target,
    land_type_for,
    parse_cost,
)

# Terreno é -1; magia é o valor de mana (inteiro, limitado). Inteiros comparam e
# embaralham bem mais rápido que objetos, e a simulação só precisa disso.
# Com a tabela de magias do ``ManaModel``, o código da magia é o índice nela.
# Com o modelo de mana, os terrenos usam códigos negativos distintos por tipo
# (-1 - índice do tipo), então "é terreno" sempre significa "código < 0".
LAND = -1
MAX_SPELL_CODE = 99
DEFAULT_PLAN_TURN = 4
CANTRIP_MAX_MV = 2
# Regras da classificação que dão rampa de verdade (mais fontes de mana). Rituais, que
# só adiantam mana uma vez, não contam como terreno extra na mão inicial.
_RAMP_SOURCE_RULES = frozenset(
    {"mana_permanent", "land_fetch", "extra_land_drops", "mana_multiplier"}
)


def spell_roles(card: CardRecord) -> tuple[bool, bool]:
    """(rampa, cantrip) da carta, pela classificação por regras."""
    result = classify_card(card)
    ramp = any(e.rule in _RAMP_SOURCE_RULES for e in result.evidence.get(taxonomy.RAMP, []))
    instant_or_sorcery = bool({"Instant", "Sorcery"} & set(card.faces[0].types))
    cantrip = (
        taxonomy.CARD_DRAW in result.evidence
        and instant_or_sorcery
        and card.mana_value <= CANTRIP_MAX_MV
    )
    return ramp, cantrip


def build_sim_deck(deck: Deck, *, count_mdfc_lands: bool = True) -> list[int]:
    """Biblioteca da simulação: a seção ``main`` expandida por quantidade.

    O comandante e as seções fora do deck não entram. MDFC com terreno atrás
    vira terreno quando ``count_mdfc_lands`` (mesma convenção das estatísticas).
    Todos os terrenos recebem o mesmo código; para cores, use ``build_simulation_input``.
    """
    cards: list[int] = []
    for entry in deck.main:
        card = entry.card
        as_land = is_land(card) or (count_mdfc_lands and is_mdfc_land(card))
        code = LAND if as_land else min(int(card.mana_value), MAX_SPELL_CODE)
        cards.extend([code] * entry.quantity)
    return cards


@dataclass(frozen=True, slots=True)
class SimulationInput:
    cards: list[int]
    mana: ManaModel


def _front_cost(card: CardRecord) -> str:
    return card.faces[0].mana_cost or ""


def _costs_of(card: CardRecord) -> list[tuple[str, FaceRecord]]:
    return [(face.mana_cost or "", face) for face in castable_faces(card) if face.mana_cost]


def _cost_key(text: str) -> tuple[int, tuple[tuple[str, ...], ...]]:
    cost = parse_cost(text)
    return cost.generic, tuple(sorted(tuple(sorted(c)) for c in cost.colored))


def _heaviest_by_color(deck: Deck, colors: Sequence[str]) -> list[tuple[str, str, str]]:
    """Para cada cor, o custo com mais símbolos dela numa única carta: (cor, carta, custo)."""
    best: dict[str, tuple[int, float, str, str]] = {}
    for entry in deck.main:
        card = entry.card
        if is_land(card):
            continue
        for cost_text, _face in _costs_of(card):
            pips = count_pips(cost_text)
            for color in colors:
                if pips[color] == 0:
                    continue
                # Mais símbolos da cor primeiro; no empate, a carta mais barata, em que a
                # restrição de cor aparece cedo em vez de ficar mascarada por mana genérico.
                candidate = (pips[color], -card.mana_value, card.name, cost_text)
                current = best.get(color)
                if current is None or candidate[:2] > current[:2]:
                    best[color] = candidate
    return [(color, name, text) for color, (_, _, name, text) in sorted(best.items())]


def build_simulation_input(
    deck: Deck,
    *,
    count_mdfc_lands: bool = True,
    extra_costs: Sequence[str] = (),
) -> SimulationInput:
    """Biblioteca com tipos de terreno e o modelo de mana (cores, entrada virada, alvos)."""
    commanders = [entry.card for entry in deck.commanders]
    identity: frozenset[str] | None = (
        frozenset(c for card in commanders for c in card.color_identity) if commanders else None
    )

    land_types: list[LandType] = []
    type_index: dict[tuple[frozenset[str], bool], int] = {}
    unknown: list[str] = []
    cards: list[int] = []
    spells: list[SpellType] = []
    spell_index: dict[tuple[int, tuple[int, tuple[tuple[str, ...], ...]], bool, bool], int] = {}
    for entry in deck.main:
        card = entry.card
        if is_land(card) or (count_mdfc_lands and is_mdfc_land(card)):
            land = land_type_for(card, identity)
            if not land.colors and card.name not in unknown:
                unknown.append(card.name)  # terreno sem mana conhecida (ex.: fetchland)
            key = (land.colors, land.enters_tapped)
            if key not in type_index:
                type_index[key] = len(land_types)
                land_types.append(land)
            cards.extend([-1 - type_index[key]] * entry.quantity)
        else:
            ramp, cantrip = spell_roles(card)
            front_cost = _front_cost(card)
            mana_value = min(int(card.mana_value), MAX_SPELL_CODE)
            spell_key = (mana_value, _cost_key(front_cost), ramp, cantrip)
            if spell_key not in spell_index:
                spell_index[spell_key] = len(spells)
                spells.append(
                    SpellType(card.name, mana_value, parse_cost(front_cost), ramp, cantrip)
                )
            cards.extend([spell_index[spell_key]] * entry.quantity)

    if identity is not None:
        histogram = tuple(c for c in COLORS if c in identity) + (COLORLESS,)
    else:
        present = {c for land in land_types for c in land.colors}
        histogram = tuple(c for c in COLORS if c in present) + (COLORLESS,)

    targets: list[Target] = []
    seen: set[tuple[int, tuple[tuple[str, ...], ...]]] = set()

    def add(label: str, source: str, text: str, mana_value: float) -> None:
        key = _cost_key(text)
        if key in seen:
            return
        seen.add(key)
        targets.append(Target(label, source, text, parse_cost(text), int(mana_value)))

    for card in commanders:
        add(card.name, "commander", _front_cost(card), card.mana_value)
    for color, name, text in _heaviest_by_color(deck, [c for c in histogram if c in COLORS]):
        add(name, f"deck_color:{color}", text, parse_cost(text).total)
    for text in extra_costs:
        add(text, "custom", text, parse_cost(text).total)

    commander_colors = {
        color
        for target in targets
        if target.source == "commander"
        for requirement in target.cost.colored
        for color in requirement
        if color in COLORS
    }
    plan_turn = (
        min(MAX_TURN, max(1, min(int(card.mana_value) for card in commanders)))
        if commanders
        else DEFAULT_PLAN_TURN
    )
    needed = frozenset(commander_colors) or frozenset(
        color
        for target in targets
        for requirement in target.cost.colored
        for color in requirement
        if color in COLORS
    )
    return SimulationInput(
        cards=cards,
        mana=ManaModel(
            land_types=tuple(land_types),
            targets=tuple(targets),
            histogram_colors=histogram,
            plan_turn=plan_turn,
            needed_colors=needed,
            unknown_mana_lands=tuple(unknown),
            spells=tuple(spells),
        ),
    )
