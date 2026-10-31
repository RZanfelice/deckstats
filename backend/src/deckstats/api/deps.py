from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.repository import CardRepository, SqlCardRepository
from deckstats.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_card_repository() -> Iterator[CardRepository]:
    with Session(get_engine()) as session:
        yield SqlCardRepository(session)
