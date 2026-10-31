import pytest

from deckstats.deck.parser import ParsedLine, parse_decklist


def names(text: str) -> list[tuple[int, str]]:
    return [(line.quantity, line.name) for line in parse_decklist(text).lines]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("1 Sol Ring", (1, "Sol Ring")),
        ("1x Sol Ring", (1, "Sol Ring")),
        ("1X Sol Ring", (1, "Sol Ring")),
        ("1 x Sol Ring", (1, "Sol Ring")),
        ("Sol Ring", (1, "Sol Ring")),
        ("  12   Forest  ", (12, "Forest")),
        ("1 Xenagos, God of Revels", (1, "Xenagos, God of Revels")),
        ("1 Fire // Ice", (1, "Fire // Ice")),
        ("1 Sol Ring (C21) 263", (1, "Sol Ring")),
        ("1x Sol Ring (c21) 263 *F*", (1, "Sol Ring")),
        ("1 Sol Ring (C21) 263 *E*", (1, "Sol Ring")),
        ("1x Sol Ring (c21) 263 [Ramp,Mana Rock]", (1, "Sol Ring")),
        ("1x Sol Ring (c21) 263 ^Have,#37d67d^", (1, "Sol Ring")),
        ("1 B.F.M. (Big Furry Monster)", (1, "B.F.M. (Big Furry Monster)")),
        ("1 Jace, the Mind Sculptor (A25) 65", (1, "Jace, the Mind Sculptor")),
    ],
)
def test_card_line_formats(line: str, expected: tuple[int, str]) -> None:
    assert names(line) == [expected]


def test_extracts_set_and_collector_number() -> None:
    (line,) = parse_decklist("1 Sol Ring (c21) 263").lines

    assert (line.set_code, line.collector_number) == ("C21", "263")


def test_set_without_number() -> None:
    (line,) = parse_decklist("1 Sol Ring (C21)").lines

    assert (line.set_code, line.collector_number) == ("C21", None)


def test_blank_lines_and_comments_are_ignored() -> None:
    text = "# meu deck\n\n// outro comentário\n1 Sol Ring\n"

    assert names(text) == [(1, "Sol Ring")]


def test_explicit_sections() -> None:
    text = (
        "Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring\n\nSideboard\n1 Mystic Remora\n"
    )

    sections = {line.name: line.section for line in parse_decklist(text).lines}

    assert sections == {
        "Atraxa, Praetors' Voice": "commander",
        "Sol Ring": "main",
        "Mystic Remora": "sideboard",
    }


@pytest.mark.parametrize("header", ["Commander:", "COMMANDER", "Commander (1)", "commanders"])
def test_section_header_variants(header: str) -> None:
    (line,) = parse_decklist(f"{header}\n1 Atraxa").lines

    assert line.section == "commander"


def test_maybeboard_and_companion_sections() -> None:
    text = "Maybeboard\n1 A\nCompanion\n1 B"

    assert [line.section for line in parse_decklist(text).lines] == ["maybeboard", "companion"]


def test_without_headers_first_blank_line_starts_the_sideboard() -> None:
    text = "1 Sol Ring\n1 Island\n\n1 Atraxa, Praetors' Voice\n"

    sections = [(line.name, line.section) for line in parse_decklist(text).lines]

    assert sections == [
        ("Sol Ring", "main"),
        ("Island", "main"),
        ("Atraxa, Praetors' Voice", "sideboard"),
    ]


def test_leading_blank_lines_do_not_start_the_sideboard() -> None:
    assert [line.section for line in parse_decklist("\n\n1 Sol Ring").lines] == ["main"]


def test_sb_prefix_marks_sideboard_lines() -> None:
    lines = parse_decklist("1 Sol Ring\nSB: 1 Atraxa").lines

    assert [(line.name, line.section) for line in lines] == [
        ("Sol Ring", "main"),
        ("Atraxa", "sideboard"),
    ]


def test_invalid_quantity_is_reported_with_line_number() -> None:
    result = parse_decklist("1 Sol Ring\n0 Island\n1000 Forest")

    assert [line.name for line in result.lines] == ["Sol Ring"]
    assert [(e.line_number, e.reason) for e in result.errors] == [
        (2, "invalid_quantity"),
        (3, "invalid_quantity"),
    ]


def test_line_with_only_tags_is_a_missing_name() -> None:
    result = parse_decklist("[Ramp]\n1 Sol Ring")

    assert [(e.line_number, e.reason) for e in result.errors] == [(1, "missing_name")]
    assert [line.name for line in result.lines] == ["Sol Ring"]


def test_merged_sums_repeated_names_within_a_section() -> None:
    result = parse_decklist("1 Island\n1 Forest\n2 island\n")

    merged = {line.name: line.quantity for line in result.merged()}

    assert merged == {"Island": 3, "Forest": 1}


def test_merged_keeps_sections_apart() -> None:
    result = parse_decklist("Deck\n1 Sol Ring\nSideboard\n1 Sol Ring")

    assert sorted((line.section, line.quantity) for line in result.merged()) == [
        ("main", 1),
        ("sideboard", 1),
    ]


def test_windows_line_endings() -> None:
    assert names("1 Sol Ring\r\n1 Island\r\n") == [(1, "Sol Ring"), (1, "Island")]


def test_returns_parsed_lines_with_line_numbers() -> None:
    result = parse_decklist("\n1 Sol Ring")

    assert result.lines == [ParsedLine(2, 1, "Sol Ring", "main")]


def test_has_headers_flag() -> None:
    assert parse_decklist("Deck\n1 Sol Ring").has_headers is True
    assert parse_decklist("1 Sol Ring").has_headers is False
