from dataclasses import dataclass, field
from typing import Literal

from deckstats.catalog.records import CardRecord

Section = Literal["commander", "main", "sideboard", "maybeboard", "companion"]

# Seções que contam como parte do deck jogável.
PLAYED_SECTIONS: tuple[Section, ...] = ("commander", "main")


@dataclass(frozen=True, slots=True)
class DeckEntry:
    card: CardRecord
    quantity: int
    section: Section


@dataclass(frozen=True, slots=True)
class Deck:
    entries: list[DeckEntry] = field(default_factory=list)

    def in_section(self, section: Section) -> list[DeckEntry]:
        return [entry for entry in self.entries if entry.section == section]

    @property
    def commanders(self) -> list[DeckEntry]:
        return self.in_section("commander")

    @property
    def main(self) -> list[DeckEntry]:
        return self.in_section("main")

    @property
    def played(self) -> list[DeckEntry]:
        return [entry for entry in self.entries if entry.section in PLAYED_SECTIONS]

    @property
    def played_count(self) -> int:
        return sum(entry.quantity for entry in self.played)
