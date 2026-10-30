"""Gera um mini dataset no formato do MTGJSON (só as colunas que o parser lê)."""

import csv
import itertools
from pathlib import Path
from typing import Any

CARD_COLUMNS = [
    "uuid", "name", "faceName", "side", "language", "layout", "manaCost", "manaValue",
    "faceManaValue", "colors", "colorIdentity", "type", "supertypes", "types", "subtypes",
    "text", "power", "toughness", "loyalty", "defense", "keywords", "producedMana",
    "setCode", "number", "isPromo", "isFunny", "isGameChanger", "edhrecRank",
    "leadershipSkills", "otherFaceIds",
]  # fmt: skip

_counter = itertools.count(1)


def new_uuid() -> str:
    return f"00000000-0000-0000-0000-{next(_counter):012d}"


class Dataset:
    def __init__(self) -> None:
        self.cards: list[dict[str, str]] = []
        self.identifiers: list[dict[str, str]] = []
        self.legalities: list[dict[str, str]] = []
        self.sets: dict[str, str] = {}
        self.meta = {"date": "2026-05-10", "version": "5.3.0+20260510"}

    def add_set(self, code: str, release_date: str) -> None:
        self.sets[code] = release_date

    def add_printing(
        self, oracle_id: str, commander: str = "Legal", language: str = "English", **fields: Any
    ) -> str:
        row = dict.fromkeys(CARD_COLUMNS, "")
        row.update(
            {
                "uuid": new_uuid(),
                "name": "Sol Ring",
                "language": language,
                "layout": "normal",
                "manaCost": "{1}",
                "manaValue": "1.0",
                "type": "Artifact",
                "types": "Artifact",
                "setCode": "AAA",
                "number": "1",
            }
        )
        row.update({key: str(value) for key, value in fields.items()})
        self.cards.append(row)
        self.identifiers.append(
            {
                "uuid": row["uuid"],
                "scryfallOracleId": oracle_id,
                "scryfallId": f"scry-{row['uuid'][-4:]}",
            }
        )
        self.legalities.append({"uuid": row["uuid"], "commander": commander})
        self.sets.setdefault(row["setCode"], "2000-01-01")
        return row["uuid"]

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        self._write(directory / "cards.csv", CARD_COLUMNS, self.cards)
        self._write(
            directory / "cardIdentifiers.csv",
            ["uuid", "scryfallOracleId", "scryfallId"],
            self.identifiers,
        )
        self._write(directory / "cardLegalities.csv", ["uuid", "commander"], self.legalities)
        self._write(
            directory / "sets.csv",
            ["code", "releaseDate"],
            [{"code": code, "releaseDate": date} for code, date in self.sets.items()],
        )
        self._write(directory / "meta.csv", ["date", "version"], [self.meta])
        return directory

    @staticmethod
    def _write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
