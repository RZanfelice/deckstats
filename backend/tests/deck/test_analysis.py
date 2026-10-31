import pytest

from deckstats.catalog.repository import SqlCardRepository
from deckstats.deck.analysis import Analysis, analyze_decklist
from deckstats.deck.stats import StatsOptions

VALID = "Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n99 Forest\n"


def codes(analysis: Analysis) -> list[str]:
    return [issue.code for issue in analysis.issues]


def test_valid_deck_has_no_issues(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist(VALID, repository)

    assert analysis.issues == []
    assert analysis.format == "commander"
    assert [e.card.name for e in analysis.deck.commanders] == ["Atraxa, Praetors' Voice"]
    assert analysis.stats.played_cards == 100
    assert analysis.stats.lands.total == 99
    assert analysis.stats.color_identity == ["W", "U", "B", "G"]


def test_mtgo_style_list_infers_the_commander_from_the_sideboard(
    repository: SqlCardRepository,
) -> None:
    analysis = analyze_decklist("99 Forest\n\n1 Atraxa, Praetors' Voice\n", repository)

    assert analysis.commander_inferred is True
    assert [e.card.name for e in analysis.deck.commanders] == ["Atraxa, Praetors' Voice"]
    assert codes(analysis) == ["commander_inferred"]
    assert analysis.stats.played_cards == 100


def test_sideboard_is_not_promoted_when_a_card_cannot_lead(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist("98 Forest\n\n1 Sol Ring\n", repository)

    assert analysis.commander_inferred is False
    assert analysis.deck.commanders == []
    assert "commander_missing" in codes(analysis)


def test_explicit_commander_section_disables_inference(repository: SqlCardRepository) -> None:
    text = "Commander\n1 Goblin Chief\nDeck\n99 Forest\nSideboard\n1 Atraxa, Praetors' Voice\n"

    analysis = analyze_decklist(text, repository)

    assert analysis.commander_inferred is False
    assert [e.card.name for e in analysis.deck.commanders] == ["Goblin Chief"]


def test_unresolved_names_are_reported_with_suggestions_and_sorted_first(
    repository: SqlCardRepository,
) -> None:
    analysis = analyze_decklist(VALID + "1 Solring\n", repository)

    (missing,) = analysis.unresolved
    assert missing.requested_name == "Solring"
    assert missing.suggestions[0] == "Sol Ring"
    assert analysis.issues[0].code == "cards_not_found"
    assert analysis.issues[0].severity == "error"
    assert analysis.issues[0].cards == ["Solring"]


def test_unparsed_lines_become_a_warning_with_line_numbers(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist(VALID + "0 Forest\n", repository)

    (issue,) = [i for i in analysis.issues if i.code == "unparsed_lines"]
    assert issue.details == {"lines": [{"line": 6, "reason": "invalid_quantity"}]}


def test_ambiguous_name_resolves_to_the_best_card_and_informs(
    repository: SqlCardRepository,
) -> None:
    analysis = analyze_decklist(
        VALID.replace("99 Forest", "98 Forest\n1 Unquenchable Fury"), repository
    )

    (issue,) = [i for i in analysis.issues if i.code == "ambiguous_names"]
    assert issue.severity == "info"
    assert issue.details["resolved_to"] == {"Unquenchable Fury": "Unquenchable Fury"}
    fury = next(c for c in analysis.cards if c.requested_name == "Unquenchable Fury")
    assert fury.card.oracle_id == "fury-ok"
    assert fury.alternatives == 1


def test_export_decorations_do_not_prevent_resolution(repository: SqlCardRepository) -> None:
    text = "Commander\n1 Atraxa, Praetors' Voice (MUL) 1\nDeck\n1x Sol Ring (c21) 263 *F* [Ramp]\n98 Forest\n"

    analysis = analyze_decklist(text, repository)

    assert analysis.unresolved == []
    assert analysis.issues == []


def test_repeated_lines_are_merged_before_counting(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist(
        "Commander\n1 Atraxa, Praetors' Voice\nDeck\n50 Forest\n49 Forest\n", repository
    )

    assert analysis.stats.lands.total == 99
    assert len([c for c in analysis.cards if c.requested_name == "Forest"]) == 1


def test_mdfc_option_changes_the_land_total(repository: SqlCardRepository) -> None:
    text = "Commander\n1 Atraxa, Praetors' Voice\nDeck\n90 Forest\n9 Emeria's Call // Emeria, Shattered Skyclave\n"

    on = analyze_decklist(text, repository)
    off = analyze_decklist(text, repository, StatsOptions(count_mdfc_lands=False))

    assert on.stats.lands.total == 99
    assert off.stats.lands.total == 90
    assert off.stats.lands.mdfc_lands == 9
    assert on.options.count_mdfc_lands is True and off.options.count_mdfc_lands is False


def test_rule_violations_surface_as_issues(repository: SqlCardRepository) -> None:
    text = "Commander\n1 Atraxa, Praetors' Voice\nDeck\n1 Lightning Bolt\n1 Time Walk\n2 Sol Ring\n95 Forest\n"

    analysis = analyze_decklist(text, repository)

    assert set(codes(analysis)) == {
        "color_identity_violation",
        "banned_cards",
        "singleton_violation",
    }


def test_empty_list_still_returns_an_analysis(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist("", repository)

    assert analysis.stats.played_cards == 0
    assert {"commander_missing", "deck_size"} <= set(codes(analysis))


def test_commander_on_top_then_blank_line_then_the_deck(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist("1 Atraxa, Praetors' Voice\n\n99 Forest\n", repository)

    assert analysis.commander_inferred is True
    assert [e.card.name for e in analysis.deck.commanders] == ["Atraxa, Praetors' Voice"]
    assert analysis.stats.lands.total == 99
    assert analysis.stats.played_cards == 100
    assert codes(analysis) == ["commander_inferred"]


def test_top_block_that_cannot_lead_is_left_as_the_deck(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist("1 Sol Ring\n\n99 Forest\n", repository)

    assert analysis.commander_inferred is False
    assert analysis.deck.commanders == []
    assert "commander_missing" in codes(analysis)


def test_top_block_is_not_promoted_when_sections_are_explicit(
    repository: SqlCardRepository,
) -> None:
    text = "Deck\n1 Atraxa, Praetors' Voice\n\nSideboard\n99 Forest\n"

    analysis = analyze_decklist(text, repository)

    assert analysis.commander_inferred is False
    assert analysis.deck.commanders == []


def test_top_block_is_not_promoted_when_there_is_no_second_block(
    repository: SqlCardRepository,
) -> None:
    analysis = analyze_decklist("1 Atraxa, Praetors' Voice\n", repository)

    assert analysis.commander_inferred is False


MIXED = "Commander\n1 Atraxa, Praetors' Voice\nDeck\n36 Forest\n63 Cultivate\n"


def test_land_odds_use_the_library_without_the_commander(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist(MIXED, repository)

    odds = analysis.land_odds
    assert odds is not None
    assert (odds.library_size, odds.lands_in_library) == (99, 36)
    assert odds.on_the_play is False


def test_critical_turn_mixes_the_commander_with_the_average(repository: SqlCardRepository) -> None:
    analysis = analyze_decklist(MIXED, repository)

    assert analysis.land_odds is not None
    critical = analysis.land_odds.critical_turn
    assert critical is not None
    assert critical.commander_mana_value == 4.0
    assert critical.average_mana_value == 3.0
    assert critical.raw == pytest.approx(0.6 * 4 + 0.4 * 3)
    assert critical.turn == 4
    # 36 terrenos em 99 cartas, 11 cartas vistas no turno 4 (valor de regressão)
    assert analysis.land_odds.at_critical_turn is not None
    assert analysis.land_odds.at_critical_turn.p_land_drops == pytest.approx(0.6213, abs=1e-3)


def test_options_flow_into_the_odds(repository: SqlCardRepository) -> None:
    heavy = analyze_decklist(MIXED, repository, StatsOptions(commander_weight=1.0))
    play = analyze_decklist(MIXED, repository, StatsOptions(on_the_play=True))

    assert heavy.land_odds is not None and heavy.land_odds.critical_turn is not None
    assert heavy.land_odds.critical_turn.raw == 4.0
    assert play.land_odds is not None
    assert play.land_odds.on_the_play is True
    assert play.land_odds.by_turn[3].cards_seen == 10


def test_mdfc_option_changes_the_lands_used_in_the_odds(repository: SqlCardRepository) -> None:
    text = "Commander\n1 Atraxa, Praetors' Voice\nDeck\n90 Forest\n9 Emeria's Call // Emeria, Shattered Skyclave\n"

    on = analyze_decklist(text, repository)
    off = analyze_decklist(text, repository, StatsOptions(count_mdfc_lands=False))

    assert on.land_odds is not None and off.land_odds is not None
    assert (on.land_odds.lands_in_library, off.land_odds.lands_in_library) == (99, 90)
    assert on.land_odds.by_turn[3].p_land_drops > off.land_odds.by_turn[3].p_land_drops


def test_no_odds_for_an_empty_list(repository: SqlCardRepository) -> None:
    assert analyze_decklist("", repository).land_odds is None
