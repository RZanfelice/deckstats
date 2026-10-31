"""Construtores de cartas e decks para os testes de domínio."""

from collections.abc import Sequence
from datetime import date

from deckstats.catalog.records import CardRecord, CommanderLegality, FaceRecord
from deckstats.deck.model import Deck, DeckEntry, Section


def make_face(
    name: str,
    *,
    mana_cost: str | None = None,
    mana_value: float = 0.0,
    colors: Sequence[str] = (),
    types: Sequence[str] = ("Creature",),
    supertypes: Sequence[str] = (),
    subtypes: Sequence[str] = (),
    keywords: Sequence[str] = (),
    text: str | None = None,
    position: int = 0,
    produced_mana: Sequence[str] = (),
) -> FaceRecord:
    return FaceRecord(
        position=position, side=None, name=name, mana_cost=mana_cost, mana_value=mana_value,
        colors=list(colors), type_line=" ".join(types), supertypes=list(supertypes),
        types=list(types), subtypes=list(subtypes), text=text, power=None, toughness=None,
        loyalty=None, defense=None, keywords=list(keywords), produced_mana=list(produced_mana),
    )  # fmt: skip


def make_card(
    name: str,
    *,
    mana_value: float = 0.0,
    mana_cost: str | None = None,
    colors: Sequence[str] = (),
    identity: Sequence[str] | None = None,
    types: Sequence[str] = ("Creature",),
    supertypes: Sequence[str] = (),
    subtypes: Sequence[str] = (),
    keywords: Sequence[str] = (),
    text: str | None = None,
    layout: str = "normal",
    faces: list[FaceRecord] | None = None,
    legality: CommanderLegality = "legal",
    can_be_commander: bool = False,
    oracle_id: str | None = None,
    is_funny: bool = False,
    edhrec_rank: int | None = None,
    produced_mana: Sequence[str] = (),
) -> CardRecord:
    if faces is None:
        faces = [
            make_face(
                name, mana_cost=mana_cost, mana_value=mana_value, colors=colors, types=types,
                supertypes=supertypes, subtypes=subtypes, keywords=keywords, text=text, produced_mana=produced_mana,
            )
        ]  # fmt: skip
    return CardRecord(
        oracle_id=oracle_id or f"oracle-{name}", name=name, layout=layout, mana_value=mana_value,
        color_identity=list(colors if identity is None else identity), commander_legality=legality,
        is_funny=is_funny, is_game_changer=False, can_be_commander=can_be_commander,
        edhrec_rank=edhrec_rank, printing_uuid=f"uuid-{name}", scryfall_id=None, set_code="TST",
        collector_number="1", released_at=date(2024, 1, 1), faces=faces,
    )  # fmt: skip


def land(
    name: str = "Forest",
    *,
    identity: Sequence[str] = (),
    basic: bool = True,
    produces: Sequence[str] = (),
    text: str | None = None,
) -> CardRecord:
    return make_card(
        name, types=("Land",), supertypes=("Basic",) if basic else (), identity=identity,
        produced_mana=produces, text=text,
    )  # fmt: skip


def entry(card: CardRecord, quantity: int = 1, section: Section = "main") -> DeckEntry:
    return DeckEntry(card, quantity, section)


def deck(*entries: DeckEntry) -> Deck:
    return Deck(list(entries))
