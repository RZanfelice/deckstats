"""Consulta ao catálogo: resolução de nomes de deck para cartas.

``CardRepository`` é a fronteira usada pelo domínio. ``SqlCardRepository`` a
implementa sobre SQLAlchemy e roda igual em Postgres (desenvolvimento e
produção) e em SQLite (demo enxuta); só a sugestão de nomes difere por dialeto.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Literal, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from deckstats.catalog.models import CardFace, OracleCard
from deckstats.catalog.normalize import normalize_name
from deckstats.catalog.records import CardRecord, CommanderLegality, FaceRecord

MatchedBy = Literal["name", "face", "none"]

_LEGALITY_ORDER: dict[str, int] = {"legal": 0, "banned": 1, "not_legal": 2}
_NO_RANK = 10**9
_DIFFLIB_CUTOFF = 0.6


@dataclass(frozen=True, slots=True)
class NameResolution:
    """Resultado de resolver um nome digitado pelo usuário."""

    query: str
    card: CardRecord | None
    matched_by: MatchedBy
    alternatives: int
    suggestions: list[str]


class CardRepository(Protocol):
    def get(self, oracle_id: str) -> CardRecord | None: ...

    def resolve(self, names: Sequence[str]) -> list[NameResolution]: ...

    def suggest(self, name: str, limit: int = 5) -> list[str]: ...


def to_record(card: OracleCard) -> CardRecord:
    return CardRecord(
        oracle_id=card.oracle_id,
        name=card.name,
        layout=card.layout,
        mana_value=card.mana_value,
        color_identity=list(card.color_identity),
        commander_legality=_legality(card.commander_legality),
        is_funny=card.is_funny,
        is_game_changer=card.is_game_changer,
        can_be_commander=card.can_be_commander,
        edhrec_rank=card.edhrec_rank,
        printing_uuid=card.printing_uuid,
        scryfall_id=card.scryfall_id,
        set_code=card.set_code,
        collector_number=card.collector_number,
        released_at=card.released_at,
        faces=[_face_record(face) for face in card.faces],
    )


def _legality(value: str) -> CommanderLegality:
    if value == "legal":
        return "legal"
    if value == "banned":
        return "banned"
    return "not_legal"


def _face_record(face: CardFace) -> FaceRecord:
    return FaceRecord(
        position=face.position,
        side=face.side,
        name=face.name,
        mana_cost=face.mana_cost,
        mana_value=face.mana_value,
        colors=list(face.colors),
        type_line=face.type_line,
        supertypes=list(face.supertypes),
        types=list(face.types),
        subtypes=list(face.subtypes),
        text=face.text,
        power=face.power,
        toughness=face.toughness,
        loyalty=face.loyalty,
        defense=face.defense,
        keywords=list(face.keywords),
        produced_mana=list(face.produced_mana),
    )


def _preference(card: OracleCard) -> tuple[int, bool, int, str]:
    """Ordem de preferência entre cartas com o mesmo nome: legal, não funny, popular."""
    return (
        _LEGALITY_ORDER.get(card.commander_legality, len(_LEGALITY_ORDER)),
        card.is_funny,
        card.edhrec_rank if card.edhrec_rank is not None else _NO_RANK,
        card.oracle_id,
    )


class SqlCardRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._difflib_names: list[tuple[str, str]] | None = None

    def get(self, oracle_id: str) -> CardRecord | None:
        card = self._session.scalar(
            select(OracleCard)
            .where(OracleCard.oracle_id == oracle_id)
            .options(selectinload(OracleCard.faces))
        )
        return to_record(card) if card else None

    def resolve(self, names: Sequence[str]) -> list[NameResolution]:
        """Resolve nomes de deck. Nome completo vence nome de face (ex.: ``Bind``)."""
        keys = {raw: normalize_name(raw) for raw in names}
        wanted = set(keys.values())

        by_name = self._candidates_by_name(wanted)
        by_face = self._candidates_by_face(wanted - by_name.keys())

        results: list[NameResolution] = []
        for raw in names:
            key = keys[raw]
            if key in by_name:
                results.append(self._found(raw, by_name[key], "name"))
            elif key in by_face:
                results.append(self._found(raw, by_face[key], "face"))
            else:
                results.append(NameResolution(raw, None, "none", 0, self.suggest(raw)))
        return results

    def suggest(self, name: str, limit: int = 5) -> list[str]:
        query = normalize_name(name)
        if not query:
            return []
        if self._session.get_bind().dialect.name == "postgresql":
            return self._suggest_trigram(query, limit)
        return self._suggest_difflib(query, limit)

    @staticmethod
    def _found(raw: str, cards: list[OracleCard], matched_by: MatchedBy) -> NameResolution:
        best = sorted(cards, key=_preference)
        return NameResolution(raw, to_record(best[0]), matched_by, len(best) - 1, [])

    def _candidates_by_name(self, keys: set[str]) -> dict[str, list[OracleCard]]:
        grouped: dict[str, list[OracleCard]] = {}
        if not keys:
            return grouped
        statement = (
            select(OracleCard)
            .where(OracleCard.name_normalized.in_(keys))
            .options(selectinload(OracleCard.faces))
        )
        for card in self._session.scalars(statement):
            grouped.setdefault(card.name_normalized, []).append(card)
        return grouped

    def _candidates_by_face(self, keys: set[str]) -> dict[str, list[OracleCard]]:
        grouped: dict[str, list[OracleCard]] = {}
        if not keys:
            return grouped
        statement = (
            select(CardFace.name_normalized, OracleCard)
            .join(OracleCard, OracleCard.oracle_id == CardFace.oracle_id)
            .where(CardFace.name_normalized.in_(keys))
            .options(selectinload(OracleCard.faces))
        )
        for key, card in self._session.execute(statement):
            cards = grouped.setdefault(key, [])
            if card not in cards:
                cards.append(card)
        return grouped

    def _suggest_trigram(self, query: str, limit: int) -> list[str]:
        scores: dict[str, float] = {}
        card_score = func.similarity(OracleCard.name_normalized, query)
        face_score = func.similarity(CardFace.name_normalized, query)
        statements = (
            select(OracleCard.name, card_score).where(
                OracleCard.name_normalized.op("%")(query), OracleCard.is_funny.is_(False)
            ),
            select(OracleCard.name, face_score)
            .join(CardFace, CardFace.oracle_id == OracleCard.oracle_id)
            .where(CardFace.name_normalized.op("%")(query), OracleCard.is_funny.is_(False)),
        )
        for statement in statements:
            for name, score in self._session.execute(statement.limit(limit * 3)):
                scores[name] = max(scores.get(name, 0.0), float(score))
        ranked = sorted(scores, key=lambda name: (-scores[name], name))
        return ranked[:limit]

    def _suggest_difflib(self, query: str, limit: int) -> list[str]:
        if self._difflib_names is None:
            cards = self._session.execute(
                select(OracleCard.name_normalized, OracleCard.name).where(
                    OracleCard.is_funny.is_(False)
                )
            ).all()
            faces = self._session.execute(
                select(CardFace.name_normalized, OracleCard.name)
                .join(OracleCard, OracleCard.oracle_id == CardFace.oracle_id)
                .where(OracleCard.is_funny.is_(False))
            ).all()
            self._difflib_names = [(key, name) for key, name in (*cards, *faces)]
        display = dict(self._difflib_names)
        close = get_close_matches(query, list(display), n=limit * 3, cutoff=_DIFFLIB_CUTOFF)
        suggestions: list[str] = []
        for key in close:
            if display[key] not in suggestions:
                suggestions.append(display[key])
        return suggestions[:limit]
