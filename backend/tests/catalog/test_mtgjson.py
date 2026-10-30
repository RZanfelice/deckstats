from datetime import date
from pathlib import Path

from deckstats.catalog.mtgjson import read_cards, read_source_version
from deckstats.catalog.records import CardRecord
from tests.catalog.builders import Dataset

SOL = "sol-ring-oracle"


def cards_by_name(dataset: Dataset, tmp_path: Path) -> dict[str, CardRecord]:
    directory = dataset.write(tmp_path)
    return {card.name: card for card in read_cards(directory)}


def test_reads_source_version(tmp_path: Path) -> None:
    version = read_source_version(Dataset().write(tmp_path))

    assert version.version == "5.3.0+20260510"
    assert version.date == date(2026, 5, 10)


def test_most_recent_printing_wins_including_its_oracle_text(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_set("OLD", "2010-01-01")
    dataset.add_set("NEW", "2024-06-01")
    dataset.add_printing(SOL, setCode="OLD", text="texto antigo")
    dataset.add_printing(SOL, setCode="NEW", text="texto esclarecido")

    card = cards_by_name(dataset, tmp_path)["Sol Ring"]

    assert card.set_code == "NEW"
    assert card.released_at == date(2024, 6, 1)
    assert card.faces[0].text == "texto esclarecido"


def test_same_date_prefers_non_promo_then_lowest_collector_number(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_set("TDM", "2025-04-11")
    dataset.add_printing(SOL, setCode="TDM", number="378", text="showcase errado")
    dataset.add_printing(SOL, setCode="TDM", number="51p", isPromo="True", text="promo")
    dataset.add_printing(SOL, setCode="TDM", number="51", text="correto")

    card = cards_by_name(dataset, tmp_path)["Sol Ring"]

    assert card.collector_number == "51"
    assert card.faces[0].text == "correto"


def test_collector_number_orders_numerically_not_alphabetically(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_printing(SOL, number="100")
    dataset.add_printing(SOL, number="9")

    assert cards_by_name(dataset, tmp_path)["Sol Ring"].collector_number == "9"


def test_non_numeric_collector_numbers_sort_after_numeric_ones(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_printing(SOL, number="★12")
    dataset.add_printing(SOL, number="300")

    assert cards_by_name(dataset, tmp_path)["Sol Ring"].collector_number == "300"


def test_non_english_rows_are_ignored(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_set("OLD", "2010-01-01")
    dataset.add_set("JPN", "2025-01-01")
    dataset.add_printing(SOL, setCode="OLD", text="english")
    dataset.add_printing(SOL, setCode="JPN", language="Japanese", text="日本語")
    dataset.add_printing("jp-only", name="Camato Scout", language="Japanese")

    cards = cards_by_name(dataset, tmp_path)

    assert set(cards) == {"Sol Ring"}
    assert cards["Sol Ring"].faces[0].text == "english"


def test_commander_legality_aggregates_all_printings(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_printing("legal-mixed", name="Hill Giant", commander="")
    dataset.add_printing("legal-mixed", name="Hill Giant", commander="Legal")
    dataset.add_printing("banned", name="Time Walk", commander="Banned")
    dataset.add_printing("banned-mixed", name="Mox Ruby", commander="")
    dataset.add_printing("banned-mixed", name="Mox Ruby", commander="Banned")
    dataset.add_printing("never", name="Shrine of Funnies", commander="")

    cards = cards_by_name(dataset, tmp_path)

    assert cards["Hill Giant"].commander_legality == "legal"
    assert cards["Time Walk"].commander_legality == "banned"
    assert cards["Mox Ruby"].commander_legality == "banned"
    assert cards["Shrine of Funnies"].commander_legality == "not_legal"


def test_transform_card_has_both_faces_in_order(tmp_path: Path) -> None:
    dataset = Dataset()
    front = dataset.add_printing(
        "delver",
        name="Delver of Secrets // Insectile Aberration",
        faceName="Delver of Secrets",
        side="a",
        layout="transform",
        manaCost="{U}",
        manaValue="1.0",
        faceManaValue="1.0",
        number="51a",
    )
    back = dataset.add_printing(
        "delver",
        name="Delver of Secrets // Insectile Aberration",
        faceName="Insectile Aberration",
        side="b",
        layout="transform",
        manaCost="",
        manaValue="1.0",
        faceManaValue="0.0",
        number="51b",
        power="3",
        otherFaceIds=front,
    )
    dataset.cards[0]["otherFaceIds"] = back

    card = cards_by_name(dataset, tmp_path)["Delver of Secrets // Insectile Aberration"]

    assert [(f.side, f.name) for f in card.faces] == [
        ("a", "Delver of Secrets"),
        ("b", "Insectile Aberration"),
    ]
    assert card.mana_value == 1.0
    assert [f.mana_value for f in card.faces] == [1.0, 0.0]
    assert card.faces[1].mana_cost is None
    assert card.faces[1].power == "3"


def test_split_card_keeps_combined_mana_value_and_face_values(tmp_path: Path) -> None:
    dataset = Dataset()
    fire = dataset.add_printing(
        "fire-ice",
        name="Fire // Ice",
        faceName="Fire",
        side="a",
        layout="split",
        manaCost="{1}{R}",
        manaValue="4.0",
        faceManaValue="2.0",
    )
    ice = dataset.add_printing(
        "fire-ice",
        name="Fire // Ice",
        faceName="Ice",
        side="b",
        layout="split",
        manaCost="{1}{U}",
        manaValue="4.0",
        faceManaValue="2.0",
        otherFaceIds=fire,
    )
    dataset.cards[0]["otherFaceIds"] = ice

    card = cards_by_name(dataset, tmp_path)["Fire // Ice"]

    assert card.mana_value == 4.0
    assert [f.mana_value for f in card.faces] == [2.0, 2.0]


def test_reversible_card_collapses_to_a_single_face(tmp_path: Path) -> None:
    dataset = Dataset()
    a = dataset.add_printing(
        "rev", name="Sol Ring // Sol Ring", faceName="Sol Ring", side="a", layout="reversible_card"
    )
    b = dataset.add_printing(
        "rev",
        name="Sol Ring // Sol Ring",
        faceName="Sol Ring",
        side="b",
        layout="reversible_card",
        otherFaceIds=a,
    )
    dataset.cards[0]["otherFaceIds"] = b

    card = cards_by_name(dataset, tmp_path)["Sol Ring"]

    assert len(card.faces) == 1


def test_meld_pieces_do_not_borrow_each_others_faces(tmp_path: Path) -> None:
    dataset = Dataset()
    bruna = dataset.add_printing("bruna", name="Bruna", faceName="Bruna", side="a", layout="meld")
    gisela = dataset.add_printing(
        "gisela", name="Gisela", faceName="Gisela", side="a", layout="meld"
    )
    result = dataset.add_printing(
        "brisela", name="Brisela", faceName="Brisela", side="b", layout="meld"
    )
    dataset.cards[0]["otherFaceIds"] = f"{gisela}, {result}"
    dataset.cards[1]["otherFaceIds"] = f"{bruna}, {result}"

    cards = cards_by_name(dataset, tmp_path)

    assert set(cards) == {"Bruna", "Gisela", "Brisela"}
    assert [f.name for f in cards["Bruna"].faces] == ["Bruna"]
    assert [f.name for f in cards["Brisela"].faces] == ["Brisela"]


def test_card_level_flags_and_lists(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_printing(
        "atraxa",
        name="Atraxa, Praetors' Voice",
        manaCost="{G}{W}{U}{B}",
        manaValue="4.0",
        colors="G, W, U, B",
        colorIdentity="G, W, U, B",
        supertypes="Legendary",
        types="Creature",
        subtypes="Phyrexian, Angel",
        keywords="Flying, Vigilance",
        isGameChanger="True",
        edhrecRank="12",
        leadershipSkills='{"brawl":true,"commander":true,"oathbreaker":false}',
    )
    dataset.add_printing("fun", name="Garbage Elemental", isFunny="True", commander="")

    cards = cards_by_name(dataset, tmp_path)
    atraxa = cards["Atraxa, Praetors' Voice"]

    assert atraxa.color_identity == ["G", "W", "U", "B"]
    assert atraxa.faces[0].subtypes == ["Phyrexian", "Angel"]
    assert atraxa.faces[0].keywords == ["Flying", "Vigilance"]
    assert atraxa.is_game_changer is True
    assert atraxa.can_be_commander is True
    assert atraxa.edhrec_rank == 12
    assert cards["Garbage Elemental"].is_funny is True
    assert cards["Garbage Elemental"].can_be_commander is False
    assert cards["Garbage Elemental"].edhrec_rank is None


def test_empty_fields_become_none_or_empty_lists(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_printing(
        "island", name="Island", manaCost="", manaValue="0.0", types="Land", supertypes="Basic"
    )

    face = cards_by_name(dataset, tmp_path)["Island"].faces[0]

    assert face.mana_cost is None
    assert face.text is None
    assert face.colors == []
    assert face.produced_mana == []
