import pytest

from deckstats.simulation.mana import (
    COLORLESS,
    ManaCost,
    can_pay,
    enters_tapped,
    land_type_for,
    parse_cost,
)
from tests.deck.builders import land, make_card, make_face


def lands(*colors: str) -> list[frozenset[str]]:
    """Terrenos que produzem as cores dadas; 'WU' é um terreno W/U."""
    return [frozenset(c) for c in colors]


# --- custos --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "generic", "colored"),
    [
        (None, 0, []),
        ("", 0, []),
        ("{3}", 3, []),
        ("{2}{U}{U}", 2, [{"U"}, {"U"}]),
        ("{W}{U}{B}{R}{G}", 0, [{"W"}, {"U"}, {"B"}, {"R"}, {"G"}]),
        ("{X}{R}{R}", 0, [{"R"}, {"R"}]),
        ("{C}{C}", 0, [{"C"}, {"C"}]),
        ("{S}{1}", 2, []),
        ("{W/U}{W/U}", 0, [{"W", "U"}, {"W", "U"}]),
        ("{B/P}{1}", 1, []),
        ("{2/W}{2/W}", 4, []),
        ("{10}", 10, []),
        ("{Z}{Q}", 0, []),
    ],
)
def test_parse_cost(text: str | None, generic: int, colored: list[set[str]]) -> None:
    cost = parse_cost(text)

    assert cost.generic == generic
    assert sorted(map(sorted, cost.colored)) == sorted(map(sorted, colored))


def test_cost_total() -> None:
    assert parse_cost("{2}{U}{U}").total == 4


@pytest.mark.parametrize(
    ("cost", "available", "expected"),
    [
        ("{2}", ["G", "G"], True),
        ("{2}", ["G"], False),
        ("{U}", ["G", "G", "G"], False),
        ("{U}", ["G", "U"], True),
        ("{U}{U}", ["U", "G", "G"], False),
        ("{U}{U}", ["U", "U"], True),
        ("{1}{U}{U}", ["U", "U", "G"], True),
        ("{1}{U}{U}", ["U", "G", "G"], False),
        # um terreno dual paga só um símbolo, mas o emparelhamento escolhe a cor certa
        ("{U}{R}", ["UR", "U"], True),
        ("{U}{R}", ["UR", "G"], False),
        ("{U}{U}", ["UR", "G"], False),
        ("{U}{R}{G}", ["UR", "RG", "UG"], True),
        ("{W/U}", ["U"], True),
        ("{W/U}", ["R"], False),
        ("{C}", ["G"], False),
        ("{C}", ["C"], True),
        ("", [], True),
        ("{B/P}", [], True),
    ],
)
def test_can_pay(cost: str, available: list[str], expected: bool) -> None:
    assert can_pay(parse_cost(cost), lands(*available)) is expected


def test_can_pay_needs_augmenting_paths() -> None:
    # {U}{R}: se o dual U/R fosse dado ao U, o R ficaria sem terreno. Tem que reatribuir.
    cost = ManaCost(generic=0, colored=(frozenset("U"), frozenset("R")))

    assert can_pay(cost, [frozenset("UR"), frozenset("R")]) is True
    assert can_pay(cost, [frozenset("UR"), frozenset("U")]) is True


def test_lands_without_colors_provide_no_mana() -> None:
    assert can_pay(parse_cost("{1}"), [frozenset()]) is False


# --- entrada virada -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("This land enters tapped.\n{T}: Add {U}.", True),
        ("Sunken Palace enters tapped. {T}: Add {U}.", True),
        ("{T}: Add {G}.", False),
        ("({T}: Add {G}.)", False),
        ("This land enters tapped unless you control two or more other lands.", False),
        ("As this land enters, you may pay 2 life. If you don't, it enters tapped.", False),
        ("As this land enters, you may reveal an Island or Mountain card from your hand. "
         "If you don't, this land enters tapped.", False),
        ("This land enters tapped unless you control an Island or a Swamp.", False),
        ("", False),
    ],
)  # fmt: skip
def test_enters_tapped(text: str, expected: bool) -> None:
    assert enters_tapped(text) is expected


# --- tipos de terreno --------------------------------------------------------------------


def test_basic_land_produces_its_color() -> None:
    forest = land("Forest", identity=("G",), produces=("G",))

    kind = land_type_for(forest, frozenset("G"))

    assert kind.colors == frozenset("G")
    assert kind.enters_tapped is False


def test_colors_outside_the_commander_identity_are_dropped() -> None:
    dual = land("Steam Vents", basic=False, produces=("R", "U"))

    assert land_type_for(dual, frozenset("U")).colors == frozenset("U")


def test_command_tower_is_limited_to_the_identity_and_gives_no_colorless() -> None:
    tower = land(
        "Command Tower",
        basic=False,
        produces=("W", "U", "B", "R", "G"),
        text="{T}: Add one mana of any color in your commander's color identity.",
    )

    assert land_type_for(tower, frozenset("UR")).colors == frozenset("UR")
    assert land_type_for(tower, frozenset()).colors == frozenset()  # comandante incolor


def test_any_color_land_turns_foreign_mana_into_colorless() -> None:
    confluence = land(
        "Mana Confluence",
        basic=False,
        produces=("W", "U", "B", "R", "G"),
        text="{T}, Pay 1 life: Add one mana of any color.",
    )

    assert land_type_for(confluence, frozenset("U")).colors == frozenset({"U", COLORLESS})
    assert land_type_for(confluence, frozenset()).colors == frozenset({COLORLESS})


def test_colorless_land_stays_colorless() -> None:
    wastes = land("Wastes", produces=("C",))

    assert land_type_for(wastes, frozenset("G")).colors == frozenset({COLORLESS})


def test_without_a_commander_the_colors_are_not_limited() -> None:
    dual = land("Steam Vents", basic=False, produces=("R", "U"))

    assert land_type_for(dual, None).colors == frozenset("UR")


def test_land_with_no_known_mana_has_no_colors() -> None:
    fetch = land(
        "Evolving Wilds", basic=False, text="{T}, Sacrifice this land: Search your library"
    )

    assert land_type_for(fetch, frozenset("G")).colors == frozenset()


def test_entering_tapped_comes_from_the_text() -> None:
    temple = land("Temple", basic=False, produces=("U",), text="This land enters tapped.")

    assert land_type_for(temple, frozenset("U")).enters_tapped is True


def test_mdfc_uses_the_land_face() -> None:
    mdfc = make_card(
        "Emeria's Call // Emeria, Shattered Skyclave",
        layout="modal_dfc",
        mana_value=7.0,
        faces=[
            make_face(
                "Emeria's Call", mana_cost="{4}{W}{W}{W}", mana_value=7.0, types=("Sorcery",)
            ),
            make_face(
                "Emeria, Shattered Skyclave",
                types=("Land",),
                position=1,
                produced_mana=("W",),
                text="As Emeria enters, you may pay 3 life. If you don't, it enters tapped.",
            ),
        ],
    )

    kind = land_type_for(mdfc, frozenset("W"))

    assert kind.colors == frozenset("W")
    assert kind.enters_tapped is False  # entrada condicional conta como desvirada
