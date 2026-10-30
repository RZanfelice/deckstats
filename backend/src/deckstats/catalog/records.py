from dataclasses import dataclass
from datetime import date
from typing import Literal

CommanderLegality = Literal["legal", "banned", "not_legal"]


@dataclass(frozen=True, slots=True)
class FaceRecord:
    position: int
    side: str | None
    name: str
    mana_cost: str | None
    mana_value: float
    colors: list[str]
    type_line: str
    supertypes: list[str]
    types: list[str]
    subtypes: list[str]
    text: str | None
    power: str | None
    toughness: str | None
    loyalty: str | None
    defense: str | None
    keywords: list[str]
    produced_mana: list[str]


@dataclass(frozen=True, slots=True)
class CardRecord:
    oracle_id: str
    name: str
    layout: str
    mana_value: float
    color_identity: list[str]
    commander_legality: CommanderLegality
    is_funny: bool
    is_game_changer: bool
    can_be_commander: bool
    edhrec_rank: int | None
    printing_uuid: str
    scryfall_id: str | None
    set_code: str
    collector_number: str
    released_at: date
    faces: list[FaceRecord]


@dataclass(frozen=True, slots=True)
class SourceVersion:
    version: str
    date: date
