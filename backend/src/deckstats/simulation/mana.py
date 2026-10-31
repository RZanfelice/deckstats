"""Modelo de mana por cor da simulação (versão 1: só terrenos).

Ver docs/F3_SIMULATION_SPEC.md, seção 4. Resumo das convenções:

* cada terreno em jogo gera 1 mana de uma das cores que produz;
* as cores vêm de ``produced_mana``, limitadas à identidade de cor do comandante;
* terreno que "enters tapped" sem condição só produz mana a partir do turno seguinte;
* entrada condicional (checklands, fastlands, snarls, shocklands) conta como desvirada;
* custos: genérico paga com qualquer mana; símbolo colorido exige a cor; híbrido aceita
  qualquer das cores; fitiriano (``{B/P}``) é ignorado; ``{2/W}`` vale 2 genéricos;
  ``{X}`` vale 0; ``{S}`` é genérico; ``{C}`` exige mana incolor.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from deckstats.catalog.records import CardRecord
from deckstats.simulation.estimate import Estimate, estimate

COLORS = "WUBRG"
COLORLESS = "C"
SOURCE_CAP = 10
COLOR_CAP = 3

_SYMBOL = re.compile(r"\{([^}]+)\}")
_TAPPED = re.compile(r"enters(?: the battlefield)? tapped", re.IGNORECASE)
_CONDITION = re.compile(r"unless|\bif\b|you may|\bas\b.*\benters|choose|reveal", re.IGNORECASE)


# --- custos --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ManaCost:
    generic: int
    # Um item por símbolo colorido; cada item lista as cores que podem pagá-lo.
    colored: tuple[frozenset[str], ...]

    @property
    def total(self) -> int:
        return self.generic + len(self.colored)


def parse_cost(text: str | None) -> ManaCost:
    """Converte ``{2}{U}{U}`` em um custo avaliável. Símbolos desconhecidos são ignorados."""
    generic = 0
    colored: list[frozenset[str]] = []
    for symbol in _SYMBOL.findall(text or ""):
        sym = symbol.upper()
        if sym.isdigit():
            generic += int(sym)
        elif sym == "S":
            generic += 1
        elif len(sym) == 1 and sym in COLORS + COLORLESS:
            colored.append(frozenset(sym))
        elif "/" in sym:
            parts = sym.split("/")
            if "P" in parts:
                continue  # fitiriano: pode ser pago com vida
            if parts[0].isdigit():
                generic += int(parts[0])  # {2/W}: aproximado por 2 genéricos
                continue
            options = frozenset(p for p in parts if len(p) == 1 and p in COLORS + COLORLESS)
            if options:
                colored.append(options)
    return ManaCost(generic=generic, colored=tuple(colored))


def can_pay(cost: ManaCost, lands: Sequence[frozenset[str]]) -> bool:
    """Dá para pagar ``cost`` com estes terrenos (1 mana por terreno)?

    O genérico usa qualquer terreno sobrando; os símbolos coloridos precisam de um
    emparelhamento terreno-símbolo (caminhos aumentantes, como em Kuhn).
    """
    lands = [colors for colors in lands if colors]  # terreno sem mana não paga nada
    if len(lands) < cost.total:
        return False
    owner = [-1] * len(lands)  # terreno -> índice do símbolo que ele paga

    def assign(requirement: int, seen: set[int]) -> bool:
        for index, colors in enumerate(lands):
            if index in seen or colors.isdisjoint(cost.colored[requirement]):
                continue
            seen.add(index)
            if owner[index] == -1 or assign(owner[index], seen):
                owner[index] = requirement
                return True
        return False

    return all(assign(requirement, set()) for requirement in range(len(cost.colored)))


# --- terrenos ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LandType:
    """Terrenos com as mesmas cores e a mesma entrada são intercambiáveis na simulação."""

    name: str
    colors: frozenset[str]
    enters_tapped: bool


def enters_tapped(text: str) -> bool:
    """Entra virado sem condição? Heurística de texto, frase a frase."""
    return any(
        _TAPPED.search(sentence) and not _CONDITION.search(sentence)
        for sentence in re.split(r"[\n.]", text)
    )


def land_type_for(card: CardRecord, identity: frozenset[str] | None) -> LandType:
    """Cores e entrada do terreno (da face de terreno, para MDFC)."""
    face = next((f for f in card.faces if "Land" in f.types), card.faces[0])
    text = face.text or ""
    colors = {c for c in face.produced_mana if c in COLORS + COLORLESS}
    if identity is not None:
        outside = {c for c in colors if c in COLORS and c not in identity}
        colors -= outside
        lowered = text.lower()
        # "any color": mana fora da identidade vira incolor. "...in your commander's color
        # identity" (Command Tower) já é restrito e não gera incolor.
        if outside and "any color" in lowered and "color identity" not in lowered:
            colors.add(COLORLESS)
        if not colors and face.produced_mana and "color identity" not in lowered:
            colors.add(COLORLESS)
    return LandType(card.name, frozenset(colors), enters_tapped(text))


# --- modelo e resultados ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Target:
    label: str
    source: str  # "commander", "deck_color:U" ou "custom"
    cost_text: str
    cost: ManaCost
    mana_value: int


@dataclass(frozen=True, slots=True)
class SpellType:
    """Magia que a simulação enxerga: custo e o papel que ela tem na mão inicial.

    ``ramp``: pedra, criatura de mana, magia que busca terreno ou jogada extra de terreno
    (rituais de uso único não contam). ``cantrip``: instantâneo ou feitiço barato que
    compra carta. As duas marcas vêm da classificação por regras (F4).
    """

    name: str
    mana_value: int
    cost: ManaCost
    ramp: bool = False
    cantrip: bool = False


@dataclass(frozen=True, slots=True)
class ManaModel:
    land_types: tuple[LandType, ...]
    targets: tuple[Target, ...]
    histogram_colors: tuple[str, ...]
    plan_turn: int
    needed_colors: frozenset[str]
    unknown_mana_lands: tuple[str, ...] = ()
    # Com a tabela de magias, os códigos não negativos da biblioteca são índices nela (e não
    # mais o valor de mana). Vazia: códigos legados, em que o código é o próprio valor de mana.
    spells: tuple[SpellType, ...] = ()


@dataclass(frozen=True, slots=True)
class CostResult:
    label: str
    source: str
    cost: str
    mana_value: int
    by_turn: dict[int, Estimate]  # P(conseguir pagar o custo no turno t)
    on_curve_turn: int | None  # turno igual ao valor de mana (None se fora da tabela)


@dataclass(frozen=True, slots=True)
class ManaResult:
    plan_turn: int
    colors: list[str]
    sources: dict[int, dict[int, Estimate]]  # turno -> X -> P(>= X fontes de mana)
    color_sources: dict[str, dict[int, dict[int, Estimate]]]  # cor -> turno -> k -> P(>= k)
    costs: list[CostResult]
    unknown_mana_lands: list[str] = field(default_factory=list)


class ManaTally:
    """Acumula, partida a partida, o que a simulação mede sobre a mana disponível."""

    def __init__(self, model: ManaModel, max_turn: int) -> None:
        self._model = model
        self._max_turn = max_turn
        turns = range(1, max_turn + 1)
        self._sources = {t: [0] * (SOURCE_CAP + 1) for t in turns}
        self._colors = {
            c: {t: [0] * (COLOR_CAP + 1) for t in turns} for c in model.histogram_colors
        }
        self._castable = [dict.fromkeys(turns, 0) for _ in model.targets]
        self._cache: dict[tuple[int, tuple[int, ...]], bool] = {}

    def record(self, turn: int, available: Sequence[int]) -> None:
        """``available``: tipos de terreno desvirados em jogo no fim da jogada do turno."""
        types = self._model.land_types
        signature = tuple(sorted(i for i in available if types[i].colors))
        producing = [types[i].colors for i in signature]

        self._sources[turn][min(len(producing), SOURCE_CAP)] += 1
        for color, by_turn in self._colors.items():
            count = sum(1 for colors in producing if color in colors)
            by_turn[turn][min(count, COLOR_CAP)] += 1

        for index, target in enumerate(self._model.targets):
            key = (index, signature)
            payable = self._cache.get(key)
            if payable is None:
                payable = can_pay(target.cost, producing)
                self._cache[key] = payable
            if payable:
                self._castable[index][turn] += payable

    def result(self, n: int) -> ManaResult:
        turns = range(1, self._max_turn + 1)

        def at_least(histogram: list[int], cap: int) -> dict[int, Estimate]:
            return {x: estimate(sum(histogram[x:]), n) for x in range(1, cap + 1)}

        costs = [
            CostResult(
                label=target.label,
                source=target.source,
                cost=target.cost_text,
                mana_value=target.mana_value,
                by_turn={t: estimate(self._castable[i][t], n) for t in turns},
                on_curve_turn=max(1, target.mana_value)
                if target.mana_value <= self._max_turn
                else None,
            )
            for i, target in enumerate(self._model.targets)
        ]
        return ManaResult(
            plan_turn=self._model.plan_turn,
            colors=list(self._model.histogram_colors),
            sources={t: at_least(self._sources[t], SOURCE_CAP) for t in turns},
            color_sources={
                color: {t: at_least(by_turn[t], COLOR_CAP) for t in turns}
                for color, by_turn in self._colors.items()
            },
            costs=costs,
            unknown_mana_lands=list(self._model.unknown_mana_lands),
        )
