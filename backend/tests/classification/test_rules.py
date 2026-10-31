from collections.abc import Sequence

import pytest

from deckstats.classification import taxonomy as t
from deckstats.classification.classifier import Classification, classify_card
from tests.deck.builders import make_card, make_face


def classify(
    text: str,
    *,
    types: Sequence[str] = ("Creature",),
    keywords: Sequence[str] = (),
    produced: Sequence[str] = (),
    name: str = "Test Card",
) -> Classification:
    card = make_card(name, text=text, types=types, keywords=keywords, produced_mana=produced)
    return classify_card(card)


def categories(text: str, **kwargs: object) -> frozenset[str]:
    return classify(text, **kwargs).categories  # type: ignore[arg-type]


# --- Ramp ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "types", "produced"),
    [
        ("{T}: Add {C}{C}.", ("Artifact",), ("C",)),
        ("{T}: Add {G}.", ("Creature",), ("G",)),
        ("{T}: Add one mana of any color.", ("Artifact",), ("W", "U", "B", "R", "G")),
        ("Enchant land\nWhenever enchanted land is tapped for mana, its controller adds an additional {G}.",
         ("Enchantment",), ("G",)),
        ("{T}, Sacrifice this artifact: Add three mana of any one color.", ("Artifact",), ("G",)),
        ("{T}, Sacrifice a Food: Add one mana of any color.", ("Creature",), ("G",)),
    ],
)  # fmt: skip
def test_mana_permanents_are_ramp(text: str, types: Sequence[str], produced: Sequence[str]) -> None:
    assert t.RAMP in categories(text, types=types, produced=produced)


def test_rituals_are_ramp() -> None:
    assert t.RAMP in categories("Add {B}{B}{B}.", types=("Instant",), produced=("B",))


@pytest.mark.parametrize(
    "text",
    [
        "Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.",
        "Search your library for up to two basic land cards, reveal those cards, put one onto the "
        "battlefield tapped and the other into your hand, then shuffle.",
        "Search your library for a Forest card, put that card onto the battlefield, then shuffle.",
        "Search your library for up to X basic land cards. Put those cards onto the battlefield tapped, "
        "then shuffle.",
    ],
)
def test_land_fetching_spells_are_ramp_and_not_tutors(text: str) -> None:
    result = categories(text, types=("Sorcery",))

    assert t.RAMP in result
    assert t.TUTOR not in result


@pytest.mark.parametrize(
    "text",
    [
        "You may play an additional land on each of your turns.",
        "You may play two additional lands on each of your turns.",
        "Untap all permanents you control during each other player's untap step.",
        "If you tap a permanent for mana, it produces twice as much of that mana instead.",
    ],
)
def test_land_drop_and_mana_multiplier_effects_are_ramp(text: str) -> None:
    assert t.RAMP in categories(text, types=("Enchantment",))


@pytest.mark.parametrize(
    ("text", "types", "produced"),
    [
        # Mana paga com o sacrifício de outra criatura não é rampa
        ("Sacrifice a creature: Add {C}{C}.", ("Artifact",), ("C",)),
        ("{T}: Add {G}.", ("Land",), ("G",)),  # terreno não é rampa
        # Faz Tesouros mas não tem habilidade de mana: o produced_mana não basta
        ("Whenever an opponent draws a card, you create a Treasure token.", ("Enchantment",), ("W", "U")),
        ("Flying", ("Creature",), ()),
    ],
)  # fmt: skip
def test_not_ramp(text: str, types: Sequence[str], produced: Sequence[str]) -> None:
    assert t.RAMP not in categories(text, types=types, produced=produced)


def test_fetchland_and_evolving_wilds_are_not_ramp() -> None:
    text = "{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle."

    result = categories(text, types=("Land",))

    assert t.RAMP not in result
    assert t.TUTOR not in result


# --- Card Draw -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Draw a card.",
        "Draw three cards.",
        "You draw two cards and you lose 2 life.",
        "At the beginning of your upkeep, you draw an additional card and you lose 1 life.",
        "Target player draws X cards.",
        "Each player discards their hand, then draws cards equal to the greatest number of cards a player discarded this way.",
        "Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
        "Scry 2, then draw a card.",
        "Look at the top seven cards of your library. Put two of them into your hand and the rest into your graveyard.",
        "Exile the top card of your library. Until end of turn, you may play that card.",
    ],
)
def test_card_draw(text: str) -> None:
    assert t.CARD_DRAW in categories(text, types=("Instant",))


def test_investigate_is_card_draw() -> None:
    assert t.CARD_DRAW in categories("", keywords=("Investigate",))


@pytest.mark.parametrize(
    "text",
    [
        "Whenever an opponent draws a card, they lose 1 life.",
        "Target opponent draws a card.",
        "If you would draw a card while your library has no cards in it, you win the game instead.",
        "Cycling {2} ({2}, Discard this card: Draw a card.)",  # só o texto de lembrete
        "Flying",
    ],
)
def test_not_card_draw(text: str) -> None:
    assert t.CARD_DRAW not in categories(text)


# --- Tutor --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Search your library for a card, put that card into your hand, then shuffle.",
        "Search your library for an instant or sorcery card, reveal it, then shuffle and put that card on top.",
        "Search your library for a creature card, reveal it, put it into your hand, then shuffle.",
        "Search your library for an artifact or enchantment card.",
    ],
)
def test_tutors(text: str) -> None:
    result = categories(text, types=("Sorcery",))

    assert t.TUTOR in result
    assert t.RAMP not in result


@pytest.mark.parametrize(
    "text",
    [
        "Search your library for a basic land card, reveal it, put it into your hand, then shuffle.",
        "Search your library for a Plains or Island card.",
    ],
)
def test_searching_only_for_lands_is_not_a_tutor(text: str) -> None:
    assert t.TUTOR not in categories(text, types=("Sorcery",))


# --- Removal --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Destroy target creature.",
        "Destroy target nonblack creature. It can't be regenerated.",
        "Exile target nonland permanent.",
        "Destroy target artifact or enchantment.",
        "Exile target attacking creature.",
        "Deals 3 damage to any target.",
        "This spell deals 4 damage to target creature or planeswalker.",
        "Target creature gets -2/-2 until end of turn.",
        "Target creature gets -X/-X until end of turn.",
        "Put target creature on the bottom of its owner's library.",
        "The owner of target permanent shuffles it into their library, then reveals the top card.",
        "Target opponent sacrifices a creature.",
        "Target creature you control fights target creature you don't control.",
    ],
)
def test_removal(text: str) -> None:
    result = categories(text, types=("Instant",))

    assert t.REMOVAL in result
    assert t.INTERACTION in result  # implicada


@pytest.mark.parametrize(
    "text",
    [
        "Exile target creature card from a graveyard.",  # hate de cemitério
        "Exile target creature you control, then return it to the battlefield under its owner's control.",
        "Deals 2 damage to target player or planeswalker and ...".replace("or planeswalker ", ""),
        "Target creature gets +2/+2 until end of turn.",
        "Each player sacrifices a creature.",
    ],
)
def test_not_removal(text: str) -> None:
    assert t.REMOVAL not in categories(text, types=("Instant",))


# --- Board Wipe -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Destroy all creatures. They can't be regenerated.",
        "Exile all nonland permanents.",
        "Choose two — • Destroy all artifacts. • Destroy all creatures.",
        "Deals 13 damage to each creature.",
        "All creatures get -X/-X until end of turn.",
        "Creatures your opponents control get -3/-3 until end of turn.",
        "Return all creatures to their owners' hands.",
        "Each player sacrifices all creatures they control.",
    ],
)
def test_board_wipes(text: str) -> None:
    result = categories(text, types=("Sorcery",))

    assert t.BOARD_WIPE in result
    assert t.INTERACTION in result


def test_overload_turns_targeted_bounce_into_a_wipe() -> None:
    text = "Return target nonland permanent you don't control to its owner's hand."

    result = categories(text, types=("Instant",), keywords=("Overload",))

    assert t.BOARD_WIPE in result
    assert t.BOARD_WIPE not in categories(text, types=("Instant",))


@pytest.mark.parametrize(
    "text",
    [
        "Destroy target creature.",
        "Exile all cards from target player's graveyard.",
        "Deals 3 damage to target creature.",
    ],
)
def test_not_board_wipe(text: str) -> None:
    assert t.BOARD_WIPE not in categories(text, types=("Sorcery",))


# --- Counterspell ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Counter target spell.",
        "Counter target noncreature spell.",
        "Counter target spell unless its controller pays {3}.",
        "Counter target activated or triggered ability.",
        "Counter target enchantment, instant, or sorcery spell.",
    ],
)
def test_counterspells(text: str) -> None:
    result = categories(text, types=("Instant",))

    assert t.COUNTERSPELL in result
    assert t.INTERACTION in result


@pytest.mark.parametrize(
    "text",
    [
        "Put a +1/+1 counter on target creature.",
        "Remove a counter from target permanent.",
        "Proliferate.",
    ],
)
def test_counters_that_are_not_counterspells(text: str) -> None:
    assert t.COUNTERSPELL not in categories(text)


# --- Protection ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Permanents you control gain hexproof and indestructible until end of turn.",
        "Creatures you control gain indestructible until end of turn.",
        "Equipped creature has hexproof and haste.",
        "Equipped creature has haste and shroud.",
        "{T}: Target creature you control gains protection from the color of your choice until end of turn.",
        "Other permanents you control have indestructible.",
        "Until your next turn, you gain protection from everything.",
        "Exile target creature you control, then return it to the battlefield under its owner's control.",
        "All permanents you control phase out.",
    ],
)
def test_protection(text: str) -> None:
    assert t.PROTECTION in categories(text, types=("Instant",))


@pytest.mark.parametrize(
    "text",
    [
        "Hexproof",
        "Flying, indestructible",
        "Protection from red",
        "This creature gains indestructible until end of turn.",
        "This creature has hexproof as long as you control another green creature.",
    ],
)
def test_a_card_that_only_protects_itself_is_not_protection(text: str) -> None:
    assert t.PROTECTION not in categories(text)


def test_a_blink_of_your_own_creature_is_not_removal() -> None:
    result = categories("Exile target creature you control, then return it to the battlefield.")

    assert t.REMOVAL not in result


# --- Win Condition -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "If X is greater than or equal to the number of cards in your library, you win the game.",
        "Target player loses the game.",
        "Each opponent loses X life.",
        "Creatures you control get +3/+3 and gain trample until end of turn.",
        "Creatures you control gain trample and get +X/+X until end of turn, where X is the greatest power.",
    ],
)
def test_win_conditions(text: str) -> None:
    assert t.WIN_CONDITION in categories(text, types=("Sorcery",))


@pytest.mark.parametrize(
    "text",
    ["Creatures you control get +1/+1.", "Each opponent loses 1 life.", "You lose the game."],
)
def test_not_win_conditions(text: str) -> None:
    assert t.WIN_CONDITION not in categories(text, types=("Enchantment",))


# --- Recursion ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Return target card from your graveyard to your hand.",
        "Return target creature card from your graveyard to your hand.",
        "Put target creature card from a graveyard onto the battlefield under your control.",
        "Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
        "Return target permanent card with mana value 3 or less from your graveyard to the battlefield.",
        "Return enchanted creature card to the battlefield under your control.",
        "Target instant or sorcery card in your graveyard gains flashback until end of turn.",
        "You may cast target instant card from your graveyard this turn.",
    ],
)
def test_recursion(text: str) -> None:
    assert t.RECURSION in categories(text, types=("Sorcery",))


@pytest.mark.parametrize(
    ("text", "keywords"),
    [
        ("Exile target card from a graveyard.", ()),
        ("Exile all cards from target player's graveyard.", ()),
        ("Escape—{3}{B}{B}, Exile four other cards from your graveyard.", ("Escape",)),
        ("Flashback {3}{R}", ("Flashback",)),
    ],
)
def test_not_recursion(text: str, keywords: Sequence[str]) -> None:
    assert t.RECURSION not in categories(text, keywords=keywords)


# --- Token Generator ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Create a 1/1 white Soldier creature token.",
        "Create three 1/1 colorless Insect artifact creature tokens with flying.",
        "Whenever this creature enters or attacks, create two 2/2 black Zombie creature tokens.",
        "Create X 1/1 white Warrior creature tokens.",
        "If an effect would create one or more tokens, it creates twice that many of those tokens instead.",
    ],
)
def test_token_generators(text: str) -> None:
    assert t.TOKEN_GENERATOR in categories(text)


@pytest.mark.parametrize("keyword", ["Amass", "Populate", "Fabricate", "Afterlife"])
def test_token_keywords(keyword: str) -> None:
    assert t.TOKEN_GENERATOR in categories("", keywords=(keyword,))


@pytest.mark.parametrize(
    "text",
    [
        "Create a Treasure token.",
        "Create a Clue token.",
        "Create a Food token.",
        "Destroy target permanent. Its controller creates a 3/3 green Beast creature token.",
        "Target opponent creates a 1/1 creature token.",
    ],
)
def test_not_token_generators(text: str) -> None:
    assert t.TOKEN_GENERATOR not in categories(text)


# --- Treasure Generator ----------------------------------------------------------------------------------------------------------


def test_treasure_generators() -> None:
    assert t.TREASURE_GENERATOR in categories(
        "When this creature enters, create X Treasure tokens."
    )
    assert t.TREASURE_GENERATOR in categories("Whenever you attack, create a Treasure token.")


@pytest.mark.parametrize(
    "text", ["Sacrifice a Treasure: Draw a card.", "Create a 1/1 Soldier creature token."]
)
def test_not_treasure_generators(text: str) -> None:
    assert t.TREASURE_GENERATOR not in categories(text)


# --- Sacrifice Outlet ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Sacrifice a creature: Scry 1.",
        "Sacrifice another creature: This creature gains indestructible until end of turn.",
        "{2}{B}, {T}, Sacrifice a creature: Target player mills two cards.",
        "Sacrifice an artifact: Draw a card.",
        "Sacrifice a land: Add {C}{C}.",
    ],
)
def test_sacrifice_outlets(text: str) -> None:
    assert t.SACRIFICE_OUTLET in categories(text)


@pytest.mark.parametrize(
    "text",
    [
        "Sacrifice this creature: Search your library for a basic land card.",
        "{1}, {T}, Sacrifice this artifact: Draw a card.",
        "As an additional cost to cast this spell, sacrifice a creature.",
        "Sacrifice a Treasure: Add one mana of any color.",
        "When this enters, sacrifice it.",
    ],
)
def test_not_sacrifice_outlets(text: str) -> None:
    assert t.SACRIFICE_OUTLET not in categories(text)


def test_the_cards_own_name_counts_as_this() -> None:
    card = make_card(
        "Sakura-Tribe Elder",
        text="Sacrifice Sakura-Tribe Elder: Search your library for a basic land card.",
    )

    assert t.SACRIFICE_OUTLET not in classify_card(card).categories


# --- Interaction (além das implicações) ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Return target creature to its owner's hand.",
        "Return target nonland permanent to its owner's hand.",
        "Gain control of target creature until end of turn.",
        "Enchant creature\nYou control enchanted creature.",
        "Enchanted creature can't attack or block.",
        "{T}: Tap target creature.",
        "Target player discards two cards.",
        "Change the target of target spell or ability with a single target.",
    ],
)
def test_other_interaction(text: str) -> None:
    result = categories(text, types=("Enchantment",))

    assert t.INTERACTION in result
    assert t.REMOVAL not in result


@pytest.mark.parametrize(
    "text",
    [
        "Return target creature you control to its owner's hand.",
        "Untap target creature.",
        "{T}: Untap target land.",
    ],
)
def test_not_interaction(text: str) -> None:
    assert t.INTERACTION not in categories(text)


# --- Estrutura ---------------------------------------------------------------------------------------------------------------------------------


def test_implied_categories_have_no_evidence_of_their_own() -> None:
    result = classify("Destroy target creature.")

    assert set(result.evidence) == {t.REMOVAL}
    assert result.categories == {t.REMOVAL, t.INTERACTION}
    assert result.has(t.INTERACTION)


def test_evidence_explains_the_match() -> None:
    result = classify(
        "Destroy target nonblack creature. It can't be regenerated.", name="Doom Blade"
    )

    (evidence,) = result.evidence[t.REMOVAL]
    assert evidence.category == t.REMOVAL
    assert evidence.rule == "destroy_or_exile"
    assert evidence.face == "Doom Blade"
    assert "destroy target nonblack creature" in evidence.excerpt


def test_reminder_text_is_ignored() -> None:
    text = "Cycling {2} ({2}, Discard this card: Draw a card.)\nFlying"

    assert classify(text).evidence == {}


def test_every_face_is_classified_and_categories_are_merged() -> None:
    card = make_card(
        "Bonecrusher Giant // Stomp",
        layout="adventure",
        faces=[
            make_face("Bonecrusher Giant", types=("Creature",), text="Whenever this creature becomes the target of a spell, this creature deals 2 damage to that spell's controller."),
            make_face("Stomp", types=("Instant",), text="Damage can't be prevented this turn. Stomp deals 2 damage to any target.", position=1),
        ],
    )  # fmt: skip

    result = classify_card(card)

    assert t.REMOVAL in result.categories
    assert result.evidence[t.REMOVAL][0].face == "Stomp"


def test_a_card_without_matches_has_no_categories() -> None:
    result = classify("Flying\nVigilance")

    assert result.categories == frozenset()
    assert result.version == t.CLASSIFIER_VERSION


def test_combo_piece_is_declared_unsupported() -> None:
    assert t.COMBO_PIECE in t.CATEGORIES
    assert t.COMBO_PIECE in t.UNSUPPORTED
    assert t.COMBO_PIECE not in t.SUPPORTED
    assert len(t.CATEGORIES) == 14


# --- Refinamentos achados na amostra aleatória do catálogo ----------------------------------------------


def test_exiling_a_creature_you_own_is_not_removal() -> None:
    text = "Exile target nontoken creature you own and the top two cards of your library in a face-down pile."

    assert t.REMOVAL not in categories(text, types=("Sorcery",))


def test_reducing_only_power_is_not_a_board_wipe() -> None:
    assert t.BOARD_WIPE not in categories(
        "Creatures your opponents control get -2/-0 until end of turn."
    )
    assert t.BOARD_WIPE not in categories("All creatures attacking you get -1/-0.")
    assert t.BOARD_WIPE in categories(
        "Creatures your opponents control get -1/-1 until end of turn."
    )


def test_a_permanent_team_buff_is_not_a_finisher() -> None:
    permanent = "Other creatures you control get +3/+3 and have trample and haste."

    assert t.WIN_CONDITION not in categories(permanent)
    assert t.WIN_CONDITION in categories(permanent.replace(".", " until end of turn."))


@pytest.mark.parametrize(
    "text",
    [
        "Return this card from your graveyard to the battlefield.",
        "Return this card from your graveyard to your hand.",
        "When you cast a Bolas planeswalker spell, exile this card from your graveyard.",
    ],
)
def test_bringing_itself_back_is_not_recursion(text: str) -> None:
    assert t.RECURSION not in categories(text)


def test_permission_to_play_from_the_graveyard_is_recursion() -> None:
    assert t.RECURSION in categories("You may play lands from your graveyard.")


def test_symmetric_life_loss_is_not_a_win_condition() -> None:
    assert t.WIN_CONDITION not in categories("Each player loses half their life, rounded up.")
    assert t.WIN_CONDITION in categories("Target opponent loses half their life, rounded up.")
    assert t.WIN_CONDITION in categories("Target player loses X life and you gain X life.")


@pytest.mark.parametrize(
    ("bonus", "expected"),
    [("+1/+1", False), ("+2/+2", True), ("+3/+3", True), ("+X/+X", True), ("+0/+4", False)],
)
def test_only_a_large_team_bonus_counts_as_a_finisher(bonus: str, expected: bool) -> None:
    text = f"Creatures you control get {bonus} and gain trample until end of turn."

    assert (t.WIN_CONDITION in categories(text)) is expected
