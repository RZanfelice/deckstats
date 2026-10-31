from deckstats.catalog.records import CardRecord
from deckstats.classification import taxonomy as t
from deckstats.classification.stats import CategoryCount, CategoryStats, compute_category_stats
from deckstats.deck.model import DeckEntry
from tests.deck.builders import deck, entry, land, make_card

ROCK = make_card(
    "Sol Ring", types=("Artifact",), text="{T}: Add {C}{C}.", produced_mana=("C",), identity=()
)
SWORDS = make_card("Swords to Plowshares", types=("Instant",), text="Exile target creature.")
DRAW = make_card("Harmonize", types=("Sorcery",), text="Draw three cards.")


def stats_for(*entries: DeckEntry) -> CategoryStats:
    return compute_category_stats(deck(*entries))


def by_category(stats: CategoryStats) -> dict[str, CategoryCount]:
    return {c.category: c for c in stats.categories}


def test_counts_copies_in_the_main_deck() -> None:
    stats = stats_for(entry(ROCK, 2), entry(SWORDS), entry(land(), 7))

    counts = by_category(stats)
    assert counts[t.RAMP].count == 2
    assert counts[t.REMOVAL].count == 1
    assert counts[t.INTERACTION].count == 1  # implicada por remoção
    assert stats.main_cards == 10


def test_percent_is_a_fraction_of_the_main_deck() -> None:
    stats = stats_for(entry(ROCK, 2), entry(land(), 8))

    assert by_category(stats)[t.RAMP].percent == 0.2


def test_lists_distinct_card_names_per_category() -> None:
    stats = stats_for(entry(ROCK, 3), entry(DRAW))

    counts = by_category(stats)
    assert counts[t.RAMP].cards == ["Sol Ring"]
    assert counts[t.CARD_DRAW].cards == ["Harmonize"]


def test_every_category_is_present_and_unsupported_ones_are_flagged() -> None:
    stats = stats_for(entry(land(), 3))

    counts = by_category(stats)
    assert list(counts) == list(t.CATEGORIES)
    assert counts[t.COMBO_PIECE].supported is False
    assert counts[t.RAMP].supported is True
    assert all(c.count == 0 and c.percent == 0.0 for c in counts.values())
    assert stats.classifier_version == t.CLASSIFIER_VERSION


def test_the_commander_is_reported_apart_and_not_counted() -> None:
    stats = stats_for(entry(ROCK, 1, "commander"), entry(SWORDS), entry(land(), 8))

    assert by_category(stats)[t.RAMP].count == 0
    assert stats.commander_categories == {"Sol Ring": [t.RAMP]}
    assert stats.main_cards == 9  # o comandante fica de fora


def test_sideboard_cards_are_not_counted() -> None:
    stats = stats_for(entry(ROCK), entry(SWORDS, 1, "sideboard"))

    assert by_category(stats)[t.REMOVAL].count == 0


def test_an_empty_deck_has_zero_percentages() -> None:
    stats = stats_for()

    assert stats.main_cards == 0
    assert all(c.percent == 0.0 for c in stats.categories)


def test_each_distinct_card_is_classified_once() -> None:
    calls: list[str] = []

    def classify(card: CardRecord) -> frozenset[str]:
        calls.append(card.oracle_id)
        return frozenset({t.RAMP})

    compute_category_stats(deck(entry(ROCK, 5), entry(SWORDS, 3)), classify)

    assert sorted(calls) == sorted({ROCK.oracle_id, SWORDS.oracle_id})
