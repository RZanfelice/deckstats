"""Construtores de registros do catálogo para os testes."""

from datetime import date

from deckstats.catalog.records import CardRecord, FaceRecord


def face(name: str, position: int = 0, text: str | None = None) -> FaceRecord:
    return FaceRecord(
        position=position, side=None, name=name, mana_cost="{1}", mana_value=1.0, colors=[],
        type_line="Artifact", supertypes=[], types=["Artifact"], subtypes=[], text=text,
        power=None, toughness=None, loyalty=None, defense=None, keywords=[], produced_mana=["C"],
    )  # fmt: skip


def card(
    oracle_id: str, name: str, faces: list[FaceRecord] | None = None, **overrides: object
) -> CardRecord:
    values: dict[str, object] = {
        "oracle_id": oracle_id, "name": name, "layout": "normal", "mana_value": 1.0,
        "color_identity": [], "commander_legality": "legal", "is_funny": False,
        "is_game_changer": False, "can_be_commander": False, "edhrec_rank": None,
        "printing_uuid": f"uuid-{oracle_id}", "scryfall_id": None, "set_code": "AAA",
        "collector_number": "1", "released_at": date(2024, 1, 1), "faces": faces or [face(name)],
    }  # fmt: skip
    values.update(overrides)
    return CardRecord(**values)  # type: ignore[arg-type]
