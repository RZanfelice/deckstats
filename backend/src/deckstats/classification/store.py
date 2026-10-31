"""Persistência das classificações (item 4.6): grava as evidências de cada carta por versão."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import islice
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, selectinload

from deckstats.catalog.models import CardCategory, ClassificationRun, OracleCard
from deckstats.catalog.records import CardRecord
from deckstats.catalog.repository import to_record
from deckstats.classification.classifier import classify_card
from deckstats.classification.taxonomy import CLASSIFIER_VERSION

BATCH_SIZE = 1000


@dataclass(frozen=True, slots=True)
class StoreResult:
    version: str
    cards: int
    labeled_cards: int
    evidence_rows: int


def iter_catalog(session: Session, batch_size: int = BATCH_SIZE) -> Iterator[CardRecord]:
    """Percorre o catálogo inteiro em lotes, paginando pela chave primária."""
    last = ""
    while True:
        cards = session.scalars(
            select(OracleCard)
            .where(OracleCard.oracle_id > last)
            .order_by(OracleCard.oracle_id)
            .limit(batch_size)
            .options(selectinload(OracleCard.faces))
        ).all()
        if not cards:
            return
        yield from (to_record(card) for card in cards)
        last = cards[-1].oracle_id
        session.expunge_all()  # não acumula 34 mil objetos na sessão


def _batches(items: Iterable[CardRecord], size: int) -> Iterator[list[CardRecord]]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def store_classifications(
    session: Session, cards: Iterable[CardRecord], batch_size: int = BATCH_SIZE
) -> StoreResult:
    """Substitui as classificações da versão atual do classificador. O chamador faz o commit."""
    session.execute(
        delete(CardCategory).where(CardCategory.classifier_version == CLASSIFIER_VERSION)
    )

    total = labeled = rows = 0
    for batch in _batches(cards, batch_size):
        records: list[dict[str, Any]] = []
        for card in batch:
            result = classify_card(card)
            total += 1
            labeled += bool(result.evidence)
            for evidence_list in result.evidence.values():
                for evidence in evidence_list:
                    records.append(
                        {
                            "oracle_id": card.oracle_id,
                            "classifier_version": result.version,
                            "category": evidence.category,
                            "rule": evidence.rule,
                            "face": evidence.face,
                            "excerpt": evidence.excerpt,
                        }
                    )
        if records:
            session.execute(insert(CardCategory).values(records))
            rows += len(records)

    run = session.get(ClassificationRun, CLASSIFIER_VERSION)
    if run is None:
        run = ClassificationRun(
            classifier_version=CLASSIFIER_VERSION,
            run_at=datetime.now(UTC),
            card_count=0,
            labeled_count=0,
        )
        session.add(run)
    run.run_at = datetime.now(UTC)
    run.card_count = total
    run.labeled_count = labeled
    return StoreResult(CLASSIFIER_VERSION, total, labeled, rows)
