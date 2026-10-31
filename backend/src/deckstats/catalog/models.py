from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from deckstats.db import Base

# Listas de strings: JSONB no Postgres, JSON no SQLite (usado na demo enxuta).
StringList = JSON().with_variant(JSONB(), "postgresql")


class DataVersion(Base):
    """Versão da fonte de dados que originou o catálogo."""

    __tablename__ = "data_version"
    __table_args__ = (UniqueConstraint("source", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(64))
    source_date: Mapped[date] = mapped_column(Date)
    card_count: Mapped[int] = mapped_column(Integer, default=0)
    face_count: Mapped[int] = mapped_column(Integer, default=0)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OracleCard(Base):
    """Uma carta (oracle id), com os dados da impressão mais recente."""

    __tablename__ = "oracle_card"
    __table_args__ = (
        Index("ix_oracle_card_name_normalized", "name_normalized"),
        Index(
            "ix_oracle_card_name_trgm",
            "name_normalized",
            postgresql_using="gin",
            postgresql_ops={"name_normalized": "gin_trgm_ops"},
        ),
    )

    oracle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    name_normalized: Mapped[str] = mapped_column(String(255))
    layout: Mapped[str] = mapped_column(String(32))
    mana_value: Mapped[float] = mapped_column(Float)
    color_identity: Mapped[list[str]] = mapped_column(StringList)
    commander_legality: Mapped[str] = mapped_column(String(16))
    is_funny: Mapped[bool] = mapped_column(Boolean)
    is_game_changer: Mapped[bool] = mapped_column(Boolean)
    can_be_commander: Mapped[bool] = mapped_column(Boolean)
    edhrec_rank: Mapped[int | None] = mapped_column(Integer)
    printing_uuid: Mapped[str] = mapped_column(String(36))
    scryfall_id: Mapped[str | None] = mapped_column(String(36))
    set_code: Mapped[str] = mapped_column(String(16))
    collector_number: Mapped[str] = mapped_column(String(16))
    released_at: Mapped[date] = mapped_column(Date)
    data_version_id: Mapped[int] = mapped_column(ForeignKey("data_version.id"), index=True)

    faces: Mapped[list["CardFace"]] = relationship(
        back_populates="card", order_by="CardFace.position", cascade="all, delete-orphan"
    )


class CardFace(Base):
    """Uma face de carta. Cartas de uma face têm exatamente uma linha."""

    __tablename__ = "card_face"
    __table_args__ = (
        UniqueConstraint("oracle_id", "position"),
        Index("ix_card_face_name_normalized", "name_normalized"),
        Index(
            "ix_card_face_name_trgm",
            "name_normalized",
            postgresql_using="gin",
            postgresql_ops={"name_normalized": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oracle_id: Mapped[str] = mapped_column(ForeignKey("oracle_card.oracle_id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    side: Mapped[str | None] = mapped_column(String(1))
    name: Mapped[str] = mapped_column(String(255))
    name_normalized: Mapped[str] = mapped_column(String(255))
    mana_cost: Mapped[str | None] = mapped_column(String(64))
    mana_value: Mapped[float] = mapped_column(Float)
    colors: Mapped[list[str]] = mapped_column(StringList)
    type_line: Mapped[str] = mapped_column(String(255))
    supertypes: Mapped[list[str]] = mapped_column(StringList)
    types: Mapped[list[str]] = mapped_column(StringList)
    subtypes: Mapped[list[str]] = mapped_column(StringList)
    text: Mapped[str | None] = mapped_column(Text)
    power: Mapped[str | None] = mapped_column(String(8))
    toughness: Mapped[str | None] = mapped_column(String(8))
    loyalty: Mapped[str | None] = mapped_column(String(8))
    defense: Mapped[str | None] = mapped_column(String(8))
    keywords: Mapped[list[str]] = mapped_column(StringList)
    produced_mana: Mapped[list[str]] = mapped_column(StringList)

    card: Mapped[OracleCard] = relationship(back_populates="faces")


class CardCategory(Base):
    """Evidência de que a carta pertence a uma categoria, produzida por uma versão do classificador.

    Só guarda as categorias ativadas por regras (explicáveis); as implicadas, como
    interação a partir de remoção, são derivadas na leitura.
    """

    __tablename__ = "card_category"
    __table_args__ = (
        UniqueConstraint("oracle_id", "classifier_version", "category", "rule", "face"),
        Index("ix_card_category_version_category", "classifier_version", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oracle_id: Mapped[str] = mapped_column(ForeignKey("oracle_card.oracle_id", ondelete="CASCADE"))
    classifier_version: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32))
    rule: Mapped[str] = mapped_column(String(32))
    face: Mapped[str] = mapped_column(String(255))
    excerpt: Mapped[str] = mapped_column(Text)


class ClassificationRun(Base):
    """Uma execução do classificador sobre o catálogo (uma linha por versão)."""

    __tablename__ = "classification_run"

    classifier_version: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    card_count: Mapped[int] = mapped_column(Integer)
    labeled_count: Mapped[int] = mapped_column(Integer)
