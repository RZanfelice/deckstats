"""Caso de uso: de um texto de lista de deck a uma análise completa."""

from dataclasses import dataclass, field, replace

from deckstats.catalog.records import CardRecord
from deckstats.catalog.repository import CardRepository, MatchedBy
from deckstats.classification.classifier import classify_card
from deckstats.classification.stats import CategoryStats, compute_category_stats
from deckstats.deck.formats import CommanderRules, FormatRules, Issue, Severity, can_lead
from deckstats.deck.model import Deck, DeckEntry, Section
from deckstats.deck.odds import LandOdds, compute_land_odds
from deckstats.deck.parser import ParseError, parse_decklist
from deckstats.deck.stats import DeckStats, StatsOptions, compute_stats

_SEVERITY_ORDER: dict[Severity, int] = {"error": 0, "warning": 1, "info": 2}
_MAX_INFERRED_COMMANDERS = 2


@dataclass(frozen=True, slots=True)
class ResolvedCard:
    requested_name: str
    quantity: int
    section: Section
    card: CardRecord
    matched_by: MatchedBy
    alternatives: int
    categories: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class UnresolvedCard:
    requested_name: str
    quantity: int
    section: Section
    line_number: int
    suggestions: list[str]


@dataclass(frozen=True, slots=True)
class Analysis:
    format: str
    deck: Deck
    stats: DeckStats
    land_odds: LandOdds | None
    categories: CategoryStats
    issues: list[Issue]
    cards: list[ResolvedCard]
    unresolved: list[UnresolvedCard]
    parse_errors: list[ParseError]
    commander_inferred: bool = False
    options: StatsOptions = field(default_factory=StatsOptions)


def _is_commander_block(items: list[ResolvedCard]) -> bool:
    """1 a 2 cópias no total, todas elegíveis a comandante."""
    total = sum(item.quantity for item in items)
    return 0 < total <= _MAX_INFERRED_COMMANDERS and all(can_lead(i.card) for i in items)


def _assign_commanders(
    resolved: list[ResolvedCard], has_headers: bool
) -> tuple[list[ResolvedCard], list[ResolvedCard]]:
    """Descobre o comandante quando a lista não o declara. Devolve (cartas, inferidas).

    Sem seção de comandante, o bloco pequeno de cartas elegíveis é o comandante,
    esteja ele depois do deck (MTGO, no sideboard) ou antes dele (a 1ª linha em
    branco separa o comandante do resto). Seções explícitas sempre vencem.
    """
    if any(item.section == "commander" for item in resolved):
        return resolved, []
    main = [item for item in resolved if item.section == "main"]
    side = [item for item in resolved if item.section == "sideboard"]

    if _is_commander_block(side):
        moves: dict[int, Section] = {id(item): "commander" for item in side}
    elif not has_headers and side and _is_commander_block(main):
        # Comandante no topo, o resto do deck depois da linha em branco.
        moves = {id(item): "commander" for item in main}
        moves |= {id(item): "main" for item in side}
    else:
        return resolved, []

    updated = [replace(item, section=moves.get(id(item), item.section)) for item in resolved]
    return updated, [item for item in updated if item.section == "commander"]


def analyze_decklist(
    text: str,
    repository: CardRepository,
    options: StatsOptions | None = None,
    rules: FormatRules | None = None,
) -> Analysis:
    options = options or StatsOptions()
    rules = rules or CommanderRules()

    parsed = parse_decklist(text)
    lines = parsed.merged()
    resolutions = repository.resolve([line.name for line in lines])

    resolved: list[ResolvedCard] = []
    unresolved: list[UnresolvedCard] = []
    for line, resolution in zip(lines, resolutions, strict=True):
        if resolution.card is None:
            unresolved.append(
                UnresolvedCard(
                    line.name, line.quantity, line.section, line.line_number, resolution.suggestions
                )
            )
        else:
            resolved.append(
                ResolvedCard(
                    line.name,
                    line.quantity,
                    line.section,
                    resolution.card,
                    resolution.matched_by,
                    resolution.alternatives,
                    classify_card(resolution.card).categories,
                )
            )

    resolved, inferred = _assign_commanders(resolved, parsed.has_headers)

    deck = Deck([DeckEntry(r.card, r.quantity, r.section) for r in resolved])

    issues = rules.validate(deck)
    if inferred:
        issues.append(Issue("commander_inferred", "info", [r.card.name for r in inferred]))
    if unresolved:
        issues.append(Issue("cards_not_found", "error", [u.requested_name for u in unresolved]))
    if parsed.errors:
        issues.append(
            Issue(
                "unparsed_lines",
                "warning",
                details={
                    "lines": [{"line": e.line_number, "reason": e.reason} for e in parsed.errors]
                },
            )
        )
    ambiguous = [r for r in resolved if r.alternatives > 0 and r.section in ("commander", "main")]
    if ambiguous:
        issues.append(
            Issue(
                "ambiguous_names",
                "info",
                [r.requested_name for r in ambiguous],
                {"resolved_to": {r.requested_name: r.card.name for r in ambiguous}},
            )
        )
    issues.sort(key=lambda issue: _SEVERITY_ORDER[issue.severity])

    stats = compute_stats(deck, options)
    return Analysis(
        format=rules.name,
        deck=deck,
        stats=stats,
        land_odds=compute_land_odds(
            library_size=stats.main_cards,
            lands=stats.lands.total,
            commander_mana_values=stats.commander_mana_values,
            average_mana_value=stats.average_mana_value,
            commander_weight=options.commander_weight,
            on_the_play=options.on_the_play,
        ),
        categories=compute_category_stats(deck),
        issues=issues,
        cards=resolved,
        unresolved=unresolved,
        parse_errors=parsed.errors,
        commander_inferred=bool(inferred),
        options=options,
    )
