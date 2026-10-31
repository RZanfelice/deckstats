"""Contagem de cartas por categoria num deck (item 4.7)."""

from collections.abc import Callable
from dataclasses import dataclass

from deckstats.catalog.records import CardRecord
from deckstats.classification import taxonomy as t
from deckstats.classification.classifier import classify_card
from deckstats.deck.model import Deck


@dataclass(frozen=True, slots=True)
class CategoryCount:
    category: str
    supported: bool  # False: as regras não decidem esta categoria (combo_piece)
    count: int  # cópias no deck principal
    percent: float  # count / cartas do deck principal, de 0 a 1
    cards: list[str]  # nomes distintos


@dataclass(frozen=True, slots=True)
class CategoryStats:
    classifier_version: str
    main_cards: int
    categories: list[CategoryCount]
    # O comandante fica fora das contagens, mas conta como peça do plano do deck.
    commander_categories: dict[str, list[str]]


def compute_category_stats(
    deck: Deck,
    classify: Callable[[CardRecord], frozenset[str]] = lambda card: classify_card(card).categories,
) -> CategoryStats:
    cache: dict[str, frozenset[str]] = {}

    def categories_of(card: CardRecord) -> frozenset[str]:
        if card.oracle_id not in cache:
            cache[card.oracle_id] = classify(card)
        return cache[card.oracle_id]

    main_cards = sum(entry.quantity for entry in deck.main)
    counts = dict.fromkeys(t.CATEGORIES, 0)
    names: dict[str, set[str]] = {category: set() for category in t.CATEGORIES}
    for entry in deck.main:
        for category in categories_of(entry.card):
            counts[category] += entry.quantity
            names[category].add(entry.card.name)

    return CategoryStats(
        classifier_version=t.CLASSIFIER_VERSION,
        main_cards=main_cards,
        categories=[
            CategoryCount(
                category=category,
                supported=category not in t.UNSUPPORTED,
                count=counts[category],
                percent=counts[category] / main_cards if main_cards else 0.0,
                cards=sorted(names[category]),
            )
            for category in t.CATEGORIES
        ],
        commander_categories={
            entry.card.name: sorted(categories_of(entry.card)) for entry in deck.commanders
        },
    )
