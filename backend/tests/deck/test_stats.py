import pytest

from deckstats.catalog.records import CardRecord
from deckstats.deck.stats import StatsOptions, compute_stats, count_pips
from tests.deck.builders import deck, entry, land, make_card, make_face

GREEN_SPELL = {"colors": ("G",), "mana_cost": "{1}{G}", "mana_value": 2.0}


def mdfc_spell_land() -> CardRecord:
    """Magia na frente, terreno atrás (ex.: Emeria's Call // Emeria, Shattered Skyclave)."""
    return make_card(
        "Emeria's Call // Emeria, Shattered Skyclave",
        layout="modal_dfc",
        mana_value=7.0,
        colors=("W",),
        faces=[
            make_face("Emeria's Call", mana_cost="{4}{W}{W}{W}", mana_value=7.0, colors=("W",), types=("Sorcery",)),
            make_face("Emeria, Shattered Skyclave", types=("Land",), position=1),
        ],
    )  # fmt: skip


def test_empty_deck_has_no_averages() -> None:
    stats = compute_stats(deck())

    assert stats.played_cards == 0
    assert stats.average_mana_value is None
    assert stats.median_mana_value is None
    assert stats.lands.total == 0


def test_counts_lands_by_quantity() -> None:
    stats = compute_stats(deck(entry(land("Forest"), 20), entry(land("Island"), 15)))

    assert stats.lands.lands == 35
    assert stats.main_cards == 35
    assert stats.nonland_cards == 0


def test_mdfc_land_counts_by_default_and_can_be_turned_off() -> None:
    d = deck(entry(land("Forest"), 10), entry(mdfc_spell_land(), 2))

    on = compute_stats(d)
    off = compute_stats(d, StatsOptions(count_mdfc_lands=False))

    assert (on.lands.lands, on.lands.mdfc_lands, on.lands.total) == (10, 2, 12)
    assert (off.lands.lands, off.lands.mdfc_lands, off.lands.total) == (10, 2, 10)


def test_mdfc_is_a_spell_for_the_curve_regardless_of_the_option() -> None:
    d = deck(entry(mdfc_spell_land()))

    for count in (True, False):
        stats = compute_stats(d, StatsOptions(count_mdfc_lands=count))
        assert stats.curve["7+"] == 1
        assert stats.nonland_cards == 1


def test_mdfc_whose_front_is_a_land_is_a_plain_land() -> None:
    pathway = make_card(
        "Blightstep Pathway // Searstep Pathway",
        layout="modal_dfc",
        types=("Land",),
        faces=[make_face("Blightstep Pathway", types=("Land",)), make_face("Searstep Pathway", types=("Land",), position=1)],
    )  # fmt: skip

    stats = compute_stats(deck(entry(pathway)), StatsOptions(count_mdfc_lands=True))

    assert (stats.lands.lands, stats.lands.mdfc_lands, stats.lands.total) == (1, 0, 1)
    assert stats.nonland_cards == 0


def test_transform_card_with_a_land_back_is_not_an_mdfc_land() -> None:
    azcanta = make_card(
        "Search for Azcanta // Azcanta, the Sunken Ruin",
        layout="transform",
        mana_value=2.0,
        colors=("U",),
        types=("Enchantment",),
        faces=[
            make_face("Search for Azcanta", mana_cost="{1}{U}", mana_value=2.0, colors=("U",), types=("Enchantment",)),
            make_face("Azcanta, the Sunken Ruin", types=("Land",), position=1),
        ],
    )  # fmt: skip

    stats = compute_stats(deck(entry(azcanta)))

    assert stats.lands.mdfc_lands == 0
    assert stats.lands.total == 0


def test_curve_excludes_lands_and_caps_at_seven_plus() -> None:
    spells = [
        (0.0, 1),
        (1.0, 2),
        (3.0, 3),
        (7.0, 1),
        (12.0, 1),
    ]
    entries = [entry(make_card(f"Spell {mv}", mana_value=mv), qty) for mv, qty in spells]

    stats = compute_stats(deck(*entries, entry(land(), 36)))

    assert stats.curve == {"0": 1, "1": 2, "2": 0, "3": 3, "4": 0, "5": 0, "6": 0, "7+": 2}
    assert stats.nonland_cards == 8


def test_average_and_median_ignore_lands_and_weight_by_quantity() -> None:
    d = deck(
        entry(make_card("Cheap", mana_value=1.0), 3),
        entry(make_card("Pricey", mana_value=5.0), 1),
        entry(land(), 40),
    )

    stats = compute_stats(d)

    assert stats.average_mana_value == 2.0
    assert stats.median_mana_value == 1.0


def test_average_is_rounded_to_two_decimals() -> None:
    d = deck(entry(make_card("A", mana_value=1.0), 2), entry(make_card("B", mana_value=2.0)))

    assert compute_stats(d).average_mana_value == 1.33


def test_commander_is_outside_the_curve_but_reported() -> None:
    d = deck(
        entry(make_card("Atraxa", mana_value=4.0, can_be_commander=True), 1, "commander"),
        entry(make_card("Spell", mana_value=2.0)),
    )

    stats = compute_stats(d)

    assert stats.commander_mana_values == [4.0]
    assert stats.curve["4"] == 0
    assert stats.average_mana_value == 2.0
    assert stats.played_cards == 2
    assert stats.main_cards == 1


def test_sideboard_and_maybeboard_are_ignored() -> None:
    d = deck(
        entry(make_card("In", mana_value=1.0)),
        entry(make_card("Out", mana_value=6.0), 1, "sideboard"),
    )

    stats = compute_stats(d)

    assert stats.nonland_cards == 1
    assert stats.played_cards == 1


def test_card_colors_multicolor_and_colorless() -> None:
    d = deck(
        entry(make_card("Green", colors=("G",), mana_value=1.0), 2),
        entry(make_card("Gruul", colors=("R", "G"), mana_value=2.0)),
        entry(make_card("Rock", types=("Artifact",), mana_value=1.0), 3),
    )

    stats = compute_stats(d)

    assert stats.card_colors == {"W": 0, "U": 0, "B": 0, "R": 1, "G": 3, "colorless": 3}
    assert stats.multicolor_cards == 1


def test_pips_count_mana_symbols_per_color() -> None:
    d = deck(
        entry(make_card("A", mana_cost="{2}{G}{G}", colors=("G",), mana_value=4.0), 2),
        entry(make_card("B", mana_cost="{W}{U}", colors=("W", "U"), mana_value=2.0)),
    )

    assert compute_stats(d).pips == {"W": 1, "U": 1, "B": 0, "R": 0, "G": 4}


@pytest.mark.parametrize(
    ("cost", "expected"),
    [
        (None, {}),
        ("{3}", {}),
        ("{X}{R}{R}", {"R": 2}),
        ("{W/U}{W/U}", {"W": 2, "U": 2}),
        ("{B/P}", {"B": 1}),
        ("{2/W}{2/W}", {"W": 2}),
        ("{W}{U}{B}{R}{G}", {"W": 1, "U": 1, "B": 1, "R": 1, "G": 1}),
        ("{C}{S}", {}),
    ],
)
def test_count_pips(cost: str | None, expected: dict[str, int]) -> None:
    full = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0} | expected

    assert count_pips(cost) == full


def test_split_card_counts_colors_and_pips_from_both_faces() -> None:
    fire_ice = make_card(
        "Fire // Ice",
        layout="split",
        mana_value=4.0,
        colors=("R", "U"),
        types=("Instant",),
        faces=[
            make_face("Fire", mana_cost="{1}{R}", mana_value=2.0, colors=("R",), types=("Instant",)),
            make_face("Ice", mana_cost="{1}{U}", mana_value=2.0, colors=("U",), types=("Instant",), position=1),
        ],
    )  # fmt: skip

    stats = compute_stats(deck(entry(fire_ice)))

    assert stats.card_colors["R"] == stats.card_colors["U"] == 1
    assert stats.pips["R"] == stats.pips["U"] == 1
    assert stats.multicolor_cards == 1
    assert stats.curve["4"] == 1  # a curva usa o valor de mana da carta inteira


def test_adventure_card_uses_only_the_front_face() -> None:
    giant = make_card(
        "Bonecrusher Giant // Stomp",
        layout="adventure",
        mana_value=3.0,
        colors=("R",),
        faces=[
            make_face("Bonecrusher Giant", mana_cost="{2}{R}", mana_value=3.0, colors=("R",)),
            make_face("Stomp", mana_cost="{1}{R}", mana_value=2.0, colors=("R",), types=("Instant",), position=1),
        ],
    )  # fmt: skip

    stats = compute_stats(deck(entry(giant)))

    assert stats.pips["R"] == 1
    assert stats.types["Creature"] == 1
    assert stats.types["Instant"] == 0


def test_type_distribution_uses_one_primary_type_per_card() -> None:
    d = deck(
        entry(make_card("Golem", types=("Artifact", "Creature")), 2),
        entry(make_card("Dryad Arbor", types=("Land", "Creature"))),
        entry(make_card("Mox", types=("Artifact",))),
        entry(make_card("Dryad", types=("Enchantment", "Creature"))),
        entry(make_card("Kindred Surge", types=("Kindred", "Instant"))),
        entry(make_card("Bolt", types=("Instant",))),
        entry(make_card("Wrath", types=("Sorcery",))),
        entry(make_card("Jace", types=("Planeswalker",))),
        entry(make_card("Invasion", types=("Battle",))),
        entry(make_card("Odd", types=("Conspiracy",))),
    )

    types = compute_stats(d).types

    assert types == {
        "Land": 1, "Creature": 3, "Planeswalker": 1, "Battle": 1, "Artifact": 1,
        "Enchantment": 0, "Instant": 2, "Sorcery": 1, "Other": 1,
    }  # fmt: skip


def test_permanent_split() -> None:
    d = deck(
        entry(make_card("Creature"), 3),
        entry(land(), 2),
        entry(make_card("Bolt", types=("Instant",)), 4),
        entry(make_card("Wrath", types=("Sorcery",))),
    )

    assert compute_stats(d).permanents == {"permanent": 5, "non_permanent": 5}


def test_color_identity_is_the_union_in_wubrg_order() -> None:
    d = deck(
        entry(
            make_card("Atraxa", identity=("G", "W", "U", "B"), can_be_commander=True),
            1,
            "commander",
        ),
        entry(make_card("Bolt", identity=("R",))),
        entry(land("Command Tower", identity=(), basic=False)),
    )

    assert compute_stats(d).color_identity == ["W", "U", "B", "R", "G"]


def test_stats_use_the_named_default_options() -> None:
    assert StatsOptions().count_mdfc_lands is True
