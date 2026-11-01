from collections.abc import Sequence

from deckstats.catalog.records import CardRecord
from deckstats.deck.formats import CommanderRules
from deckstats.deck.model import Deck, DeckEntry
from tests.deck.builders import deck, entry, land, make_card, make_face

ATRAXA = make_card(
    "Atraxa, Praetors' Voice",
    identity=("G", "W", "U", "B"),
    colors=("G", "W", "U", "B"),
    can_be_commander=True,
)
MONO_R_COMMANDER = make_card("Goblin Chief", identity=("R",), colors=("R",), can_be_commander=True)


def codes(d: Deck) -> list[str]:
    return [issue.code for issue in CommanderRules().validate(d)]


def hundred(commander: CardRecord = ATRAXA, extra: Sequence[DeckEntry] = ()) -> Deck:
    """Deck de 100 cartas legais: comandante + 99 terrenos básicos/extras."""
    entries = [entry(commander, 1, "commander"), *extra]
    filler = 100 - sum(e.quantity for e in entries)
    return deck(*entries, entry(land("Forest", identity=("G",)), filler))


def test_a_valid_deck_has_no_issues() -> None:
    assert codes(hundred()) == []


def test_missing_commander() -> None:
    assert "commander_missing" in codes(deck(entry(land(), 100)))


def test_commander_that_cannot_lead() -> None:
    d = deck(entry(make_card("Bear", identity=("G",)), 1, "commander"), entry(land(), 99))

    assert "commander_not_eligible" in codes(d)


def test_too_many_commanders() -> None:
    d = deck(
        entry(ATRAXA, 1, "commander"),
        entry(MONO_R_COMMANDER, 1, "commander"),
        entry(MONO_R_COMMANDER, 1, "commander"),
        entry(land(), 97),
    )

    assert "too_many_commanders" in codes(d)


def test_deck_size_reports_expected_and_actual() -> None:
    d = deck(entry(ATRAXA, 1, "commander"), entry(land("Forest", identity=("G",)), 59))

    (issue,) = [i for i in CommanderRules().validate(d) if i.code == "deck_size"]

    assert issue.details == {"expected": 100, "actual": 60}


def test_singleton_violation_ignores_basic_lands() -> None:
    d = hundred(extra=[entry(make_card("Sol Ring", identity=()), 2)])

    (issue,) = [i for i in CommanderRules().validate(d) if i.code == "singleton_violation"]

    assert issue.cards == ["Sol Ring"]


def test_singleton_allows_cards_that_permit_any_number() -> None:
    rats = make_card(
        "Relentless Rats",
        identity=("B",),
        text="A deck can have any number of cards named Relentless Rats.",
    )
    d = hundred(extra=[entry(rats, 20)])

    assert "singleton_violation" not in codes(d)


def test_commander_also_in_main_deck_is_a_duplicate() -> None:
    d = deck(
        entry(ATRAXA, 1, "commander"),
        entry(ATRAXA, 1, "main"),
        entry(land("Forest", identity=("G",)), 98),
    )

    assert "singleton_violation" in codes(d)


def test_color_identity_violation_lists_offending_cards() -> None:
    bolt = make_card("Lightning Bolt", identity=("R",), colors=("R",))
    d = hundred(extra=[entry(bolt)])

    (issue,) = [i for i in CommanderRules().validate(d) if i.code == "color_identity_violation"]

    assert issue.cards == ["Lightning Bolt"]
    assert issue.details["allowed"] == ["B", "G", "U", "W"]


def test_color_identity_uses_the_union_of_two_partners() -> None:
    partner_a = make_card(
        "Partner A", identity=("R",), can_be_commander=True, keywords=("Partner",)
    )
    partner_b = make_card(
        "Partner B", identity=("U",), can_be_commander=True, keywords=("Partner",)
    )
    izzet = make_card("Izzet Charm", identity=("U", "R"))
    d = deck(
        entry(partner_a, 1, "commander"),
        entry(partner_b, 1, "commander"),
        entry(izzet),
        entry(land(), 97),
    )

    assert codes(d) == []


def test_colorless_commander_allows_only_colorless_cards() -> None:
    kozilek = make_card("Kozilek", identity=(), can_be_commander=True)
    d = deck(
        entry(kozilek, 1, "commander"),
        entry(make_card("Bolt", identity=("R",))),
        entry(land(identity=()), 98),
    )

    assert "color_identity_violation" in codes(d)


def test_no_color_identity_check_without_a_commander() -> None:
    d = deck(entry(make_card("Bolt", identity=("R",))), entry(land(), 99))

    assert "color_identity_violation" not in codes(d)


def test_banned_and_not_legal_cards_are_reported_separately() -> None:
    d = hundred(
        extra=[
            entry(make_card("Time Walk", identity=(), legality="banned")),
            entry(make_card("Funny Card", identity=(), legality="not_legal")),
        ]
    )

    by_code = {i.code: i.cards for i in CommanderRules().validate(d)}

    assert by_code["banned_cards"] == ["Time Walk"]
    assert by_code["not_legal_cards"] == ["Funny Card"]


def partners(
    a_keys: Sequence[str],
    b_keys: Sequence[str],
    a_text: str | None = None,
    a_subtypes: Sequence[str] = (),
    b_subtypes: Sequence[str] = (),
    b_name: str = "Other",
) -> Deck:
    a = make_card(
        "First",
        identity=(),
        can_be_commander=True,
        keywords=a_keys,
        text=a_text,
        subtypes=a_subtypes,
    )
    b = make_card(b_name, identity=(), can_be_commander=True, keywords=b_keys, subtypes=b_subtypes)
    return deck(entry(a, 1, "commander"), entry(b, 1, "commander"), entry(land(identity=()), 98))


def test_two_commanders_without_partner_are_invalid() -> None:
    assert "commander_pair_invalid" in codes(partners((), ()))


def test_partner_pairs() -> None:
    assert "commander_pair_invalid" not in codes(partners(("Partner",), ("Partner",)))


def test_partner_with_requires_the_named_partner() -> None:
    ok = partners(("Partner with",), ("Partner with",), a_text="Partner with Other", b_name="Other")
    wrong = partners(
        ("Partner with",), ("Partner with",), a_text="Partner with Someone Else", b_name="Other"
    )

    assert "commander_pair_invalid" not in codes(ok)
    assert "commander_pair_invalid" in codes(wrong)


def test_friends_forever_pair() -> None:
    assert "commander_pair_invalid" not in codes(
        partners(("Friends forever",), ("Friends forever",))
    )


def test_choose_a_background_pairs_with_a_background() -> None:
    # O MTGJSON grafa a palavra-chave como "Choose a background" (b minúsculo).
    ok = partners(("Choose a background",), (), b_subtypes=("Background",))
    wrong = partners(("Choose a background",), (), b_subtypes=("Elf",))

    assert "commander_pair_invalid" not in codes(ok)
    assert "commander_pair_invalid" in codes(wrong)


def test_doctors_companion_pairs_with_a_time_lord_doctor() -> None:
    ok = partners(("Doctor's companion",), (), b_subtypes=("Time Lord", "Doctor"))

    assert "commander_pair_invalid" not in codes(ok)


def test_multiface_commander_keywords_are_collected_from_every_face() -> None:
    back_partner = make_card(
        "Two Faced",
        identity=(),
        can_be_commander=True,
        faces=[make_face("Front"), make_face("Back", keywords=("Partner",), position=1)],
    )
    other = make_card("Plain Partner", identity=(), can_be_commander=True, keywords=("Partner",))
    d = deck(
        entry(back_partner, 1, "commander"),
        entry(other, 1, "commander"),
        entry(land(identity=()), 98),
    )

    assert "commander_pair_invalid" not in codes(d)


def test_background_is_eligible_next_to_its_commander() -> None:
    result = partners(("Choose a background",), (), b_subtypes=("Background",))

    assert "commander_not_eligible" not in codes(result)


def test_background_alone_is_not_a_valid_commander() -> None:
    background = make_card(
        "Raised by Giants", identity=(), types=("Enchantment",), subtypes=("Background",)
    )
    d = deck(entry(background, 1, "commander"), entry(land(), 99))

    assert "commander_not_eligible" in codes(d)
