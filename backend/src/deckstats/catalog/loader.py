from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from itertools import islice
from typing import Any, cast

from sqlalchemy import CursorResult, delete, insert, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from deckstats.catalog.models import CardFace, DataVersion, OracleCard
from deckstats.catalog.normalize import normalize_name
from deckstats.catalog.records import CardRecord, SourceVersion

SOURCE = "mtgjson"
BATCH_SIZE = 1000


@dataclass(frozen=True, slots=True)
class LoadResult:
    cards: int
    faces: int
    removed: int


def _batches(items: Iterable[CardRecord], size: int) -> Iterator[list[CardRecord]]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def _upsert_cards(session: Session, rows: list[dict[str, Any]]) -> None:
    dialect = session.get_bind().dialect.name
    statement: postgresql.Insert | sqlite.Insert
    if dialect == "postgresql":
        statement = postgresql.insert(OracleCard)
    elif dialect == "sqlite":
        statement = sqlite.insert(OracleCard)
    else:
        raise NotImplementedError(f"upsert não suportado para o dialeto {dialect!r}")
    updatable = {column: statement.excluded[column] for column in rows[0] if column != "oracle_id"}
    # Um INSERT com várias linhas por lote: uma ida e volta ao banco, não uma por linha.
    session.execute(
        statement.values(rows).on_conflict_do_update(index_elements=["oracle_id"], set_=updatable)
    )


def _card_row(card: CardRecord, version_id: int) -> dict[str, Any]:
    row = asdict(card)
    del row["faces"]
    row["name_normalized"] = normalize_name(card.name)
    row["data_version_id"] = version_id
    return row


def _face_row(oracle_id: str, face: Any) -> dict[str, Any]:
    row = asdict(face)
    row["oracle_id"] = oracle_id
    row["name_normalized"] = normalize_name(face.name)
    return row


def _get_or_create_version(session: Session, version: SourceVersion) -> DataVersion:
    existing = session.scalar(
        select(DataVersion).where(
            DataVersion.source == SOURCE, DataVersion.version == version.version
        )
    )
    if existing:
        return existing
    created = DataVersion(
        source=SOURCE,
        version=version.version,
        source_date=version.date,
        loaded_at=datetime.now(UTC),
    )
    session.add(created)
    session.flush()
    return created


def load_catalog(
    session: Session,
    cards: Iterable[CardRecord],
    version: SourceVersion,
    batch_size: int = BATCH_SIZE,
) -> LoadResult:
    """Grava o catálogo de forma idempotente, em uma única transação.

    Cartas são upsert por oracle id (ids estáveis para quem referenciar). As faces
    de cada lote são recriadas. Cartas que não vieram nesta carga são removidas.
    O chamador faz o commit.
    """
    data_version = _get_or_create_version(session, version)
    total_cards = total_faces = 0

    for batch in _batches(cards, batch_size):
        ids = [card.oracle_id for card in batch]
        _upsert_cards(session, [_card_row(card, data_version.id) for card in batch])
        session.execute(delete(CardFace).where(CardFace.oracle_id.in_(ids)))
        face_rows = [_face_row(card.oracle_id, face) for card in batch for face in card.faces]
        session.execute(insert(CardFace).values(face_rows))
        total_cards += len(batch)
        total_faces += len(face_rows)

    stale = select(OracleCard.oracle_id).where(OracleCard.data_version_id != data_version.id)
    session.execute(delete(CardFace).where(CardFace.oracle_id.in_(stale)))
    deleted = cast(
        CursorResult[Any],
        session.execute(delete(OracleCard).where(OracleCard.data_version_id != data_version.id)),
    )
    removed = deleted.rowcount

    data_version.card_count = total_cards
    data_version.face_count = total_faces
    data_version.loaded_at = datetime.now(UTC)
    return LoadResult(cards=total_cards, faces=total_faces, removed=removed)
