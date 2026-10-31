from deckstats.catalog.records import CardRecord
from deckstats.simulation.model import LAND, build_sim_deck
from tests.deck.builders import deck, entry, land, make_card, make_face


def mdfc_spell_land() -> CardRecord:
    return make_card(
        "Emeria's Call // Emeria, Shattered Skyclave",
        layout="modal_dfc",
        mana_value=7.0,
        faces=[
            make_face(
                "Emeria's Call", mana_cost="{4}{W}{W}{W}", mana_value=7.0, types=("Sorcery",)
            ),
            make_face("Emeria, Shattered Skyclave", types=("Land",), position=1),
        ],
    )


def test_lands_and_spells_are_coded_by_quantity() -> None:
    d = deck(
        entry(land("Forest"), 3),
        entry(make_card("Bolt", mana_value=1.0), 2),
        entry(make_card("Wrath", mana_value=4.0)),
    )

    assert sorted(build_sim_deck(d)) == [LAND, LAND, LAND, 1, 1, 4]


def test_commander_and_sideboard_are_not_in_the_library() -> None:
    d = deck(
        entry(make_card("Atraxa", mana_value=4.0, can_be_commander=True), 1, "commander"),
        entry(make_card("Sol Ring", mana_value=1.0)),
        entry(make_card("Side", mana_value=2.0), 1, "sideboard"),
    )

    assert build_sim_deck(d) == [1]


def test_mdfc_land_follows_the_option() -> None:
    d = deck(entry(mdfc_spell_land()))

    assert build_sim_deck(d, count_mdfc_lands=True) == [LAND]
    assert build_sim_deck(d, count_mdfc_lands=False) == [7]


def test_spell_cost_is_truncated_and_capped() -> None:
    d = deck(
        entry(make_card("Half", mana_value=2.5)),
        entry(make_card("Huge", mana_value=1_000_000.0)),
    )

    assert sorted(build_sim_deck(d)) == [2, 99]
