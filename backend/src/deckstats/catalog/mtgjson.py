"""Leitura dos CSVs do MTGJSON e deduplicação por carta (oracle id).

Cada linha de ``cards.csv`` é uma impressão (e uma face). Aqui elas viram uma
``CardRecord`` por oracle id, com as faces da impressão escolhida.

Regras (ver docs/DATA_NOTES.md):

* só impressões em inglês entram;
* a impressão canônica é a de lançamento mais recente; empates resolvem por
  não-promo, depois menor número de coleção, depois uuid;
* a legalidade em Commander agrega todas as impressões: qualquer ``Legal``
  vence, senão qualquer ``Banned``, senão ``not_legal``;
* faces vêm de ``otherFaceIds`` e só valem se tiverem o mesmo oracle id
  (peças de meld não viram faces umas das outras).
"""

import csv
import json
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from deckstats.catalog.records import CardRecord, CommanderLegality, FaceRecord, SourceVersion

ENGLISH = "English"
_SORT_KEY = tuple[int, int, tuple[int, int, str], str]
_NUMBER = re.compile(r"(\d+)(.*)")


def _rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _flag(value: str) -> bool:
    return value.strip().lower() == "true"


def _or_none(value: str) -> str | None:
    return value or None


def _number_key(number: str) -> tuple[int, int, str]:
    match = _NUMBER.match(number)
    if match:
        return (0, int(match.group(1)), match.group(2))
    return (1, 0, number)


def _sort_key(row: dict[str, str], released: date) -> _SORT_KEY:
    """Menor chave = melhor impressão canônica."""
    return (
        -released.toordinal(),
        int(_flag(row["isPromo"])),
        _number_key(row["number"]),
        row["uuid"],
    )


def read_source_version(data_dir: Path) -> SourceVersion:
    row = next(_rows(data_dir / "meta.csv"))
    return SourceVersion(version=row["version"], date=date.fromisoformat(row["date"]))


def _read_release_dates(path: Path) -> dict[str, date]:
    return {
        row["code"]: date.fromisoformat(row["releaseDate"])
        for row in _rows(path)
        if row["releaseDate"]
    }


def _read_identifiers(path: Path) -> dict[str, tuple[str, str]]:
    return {
        row["uuid"]: (row["scryfallOracleId"], row["scryfallId"])
        for row in _rows(path)
        if row["scryfallOracleId"]
    }


def _read_commander_legality(path: Path) -> dict[str, str]:
    return {row["uuid"]: row["commander"] for row in _rows(path)}


def _aggregate_legality(values: set[str]) -> CommanderLegality:
    if "Legal" in values:
        return "legal"
    if "Banned" in values:
        return "banned"
    return "not_legal"


def _face(row: dict[str, str], position: int) -> FaceRecord:
    face_value = row["faceManaValue"] or row["manaValue"]
    return FaceRecord(
        position=position,
        side=_or_none(row["side"]),
        name=row["faceName"] or row["name"],
        mana_cost=_or_none(row["manaCost"]),
        mana_value=float(face_value),
        colors=_split(row["colors"]),
        type_line=row["type"],
        supertypes=_split(row["supertypes"]),
        types=_split(row["types"]),
        subtypes=_split(row["subtypes"]),
        text=_or_none(row["text"]),
        power=_or_none(row["power"]),
        toughness=_or_none(row["toughness"]),
        loyalty=_or_none(row["loyalty"]),
        defense=_or_none(row["defense"]),
        keywords=_split(row["keywords"]),
        produced_mana=_split(row["producedMana"]),
    )


def _can_be_commander(rows: list[dict[str, str]]) -> bool:
    for row in rows:
        if row["leadershipSkills"] and json.loads(row["leadershipSkills"]).get("commander"):
            return True
    return False


def read_cards(data_dir: Path) -> Iterator[CardRecord]:
    """Devolve uma ``CardRecord`` por oracle id presente em inglês."""
    release_dates = _read_release_dates(data_dir / "sets.csv")
    identifiers = _read_identifiers(data_dir / "cardIdentifiers.csv")
    legalities = _read_commander_legality(data_dir / "cardLegalities.csv")
    cards_path = data_dir / "cards.csv"

    legality_by_oracle: dict[str, set[str]] = {}
    best_front: dict[str, tuple[_SORT_KEY, str]] = {}
    best_any: dict[str, tuple[_SORT_KEY, str]] = {}
    other_faces: dict[str, list[str]] = {}

    for row in _rows(cards_path):
        if row["language"] != ENGLISH or row["uuid"] not in identifiers:
            continue
        oracle_id = identifiers[row["uuid"]][0]
        legality_by_oracle.setdefault(oracle_id, set()).add(legalities.get(row["uuid"], ""))

        key = _sort_key(row, release_dates.get(row["setCode"], date.min))
        if oracle_id not in best_any or key < best_any[oracle_id][0]:
            best_any[oracle_id] = (key, row["uuid"])
        if row["side"] in ("", "a") and (
            oracle_id not in best_front or key < best_front[oracle_id][0]
        ):
            best_front[oracle_id] = (key, row["uuid"])
        other_faces[row["uuid"]] = _split(row["otherFaceIds"])

    canonical = {oid: best_front.get(oid, best_any[oid])[1] for oid in best_any}
    wanted: set[str] = set()
    for uuid in canonical.values():
        wanted.add(uuid)
        wanted.update(other_faces[uuid])
    rows_by_uuid = {row["uuid"]: row for row in _rows(cards_path) if row["uuid"] in wanted}

    for oracle_id, uuid in canonical.items():
        main = rows_by_uuid[uuid]
        face_rows = [main]
        if main["layout"] != "reversible_card":
            face_rows += [
                rows_by_uuid[other]
                for other in other_faces[uuid]
                if other in rows_by_uuid and identifiers[other][0] == oracle_id
            ]
        face_rows.sort(key=lambda r: r["side"])
        faces = [_face(row, position) for position, row in enumerate(face_rows)]

        edhrec = main["edhrecRank"] or next(
            (r["edhrecRank"] for r in face_rows if r["edhrecRank"]), ""
        )
        yield CardRecord(
            oracle_id=oracle_id,
            name=faces[0].name if main["layout"] == "reversible_card" else main["name"],
            layout=main["layout"],
            mana_value=float(main["manaValue"]),
            color_identity=_split(main["colorIdentity"]),
            commander_legality=_aggregate_legality(legality_by_oracle[oracle_id]),
            is_funny=_flag(main["isFunny"]),
            is_game_changer=any(_flag(r["isGameChanger"]) for r in face_rows),
            can_be_commander=_can_be_commander(face_rows),
            edhrec_rank=int(edhrec) if edhrec else None,
            printing_uuid=uuid,
            scryfall_id=identifiers[uuid][1] or None,
            set_code=main["setCode"],
            collector_number=main["number"],
            released_at=release_dates.get(main["setCode"], date.min),
            faces=faces,
        )
