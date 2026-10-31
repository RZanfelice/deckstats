from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from deckstats.api.deps import get_card_repository
from deckstats.catalog.repository import CardRepository
from deckstats.deck.analysis import Analysis, analyze_decklist
from deckstats.deck.stats import StatsOptions

router = APIRouter(tags=["analyses"])

MAX_DECKLIST_CHARS = 20_000
EXAMPLE_DECKLIST = "Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring\n98 Forest"


class AnalysisOptions(BaseModel):
    count_mdfc_lands: bool = Field(
        default=True, description="Conta MDFC com terreno atrás no total de terrenos."
    )


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"decklist": EXAMPLE_DECKLIST}]})

    decklist: str = Field(
        min_length=1,
        max_length=MAX_DECKLIST_CHARS,
        description=(
            "A lista inteira em UMA string. Em JSON, as quebras de linha precisam ser `\\n`. "
            "Para colar uma lista direto, use `POST /analyses/text`."
        ),
    )
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class CardOut(BaseModel):
    oracle_id: str
    name: str
    requested_name: str
    quantity: int
    section: str
    matched_by: str
    alternatives: int
    mana_value: float
    commander_legality: str


class UnresolvedOut(BaseModel):
    requested_name: str
    quantity: int
    section: str
    line_number: int
    suggestions: list[str]


class IssueOut(BaseModel):
    code: str
    severity: str
    cards: list[str]
    details: dict[str, Any]


class LandsOut(BaseModel):
    lands: int
    mdfc_lands: int
    total: int


class StatsOut(BaseModel):
    played_cards: int
    main_cards: int
    nonland_cards: int
    lands: LandsOut
    curve: dict[str, int]
    average_mana_value: float | None
    median_mana_value: float | None
    commander_mana_values: list[float]
    card_colors: dict[str, int]
    multicolor_cards: int
    pips: dict[str, int]
    color_identity: list[str]
    types: dict[str, int]
    permanents: dict[str, int]


class AnalysisResponse(BaseModel):
    format: str
    commander_inferred: bool
    commanders: list[str]
    options: AnalysisOptions
    stats: StatsOut
    cards: list[CardOut]
    unresolved: list[UnresolvedOut]
    issues: list[IssueOut]


def to_response(analysis: Analysis) -> AnalysisResponse:
    return AnalysisResponse(
        format=analysis.format,
        commander_inferred=analysis.commander_inferred,
        commanders=[entry.card.name for entry in analysis.deck.commanders],
        options=AnalysisOptions(count_mdfc_lands=analysis.options.count_mdfc_lands),
        stats=StatsOut.model_validate(asdict(analysis.stats)),
        cards=[
            CardOut(
                oracle_id=item.card.oracle_id,
                name=item.card.name,
                requested_name=item.requested_name,
                quantity=item.quantity,
                section=item.section,
                matched_by=item.matched_by,
                alternatives=item.alternatives,
                mana_value=item.card.mana_value,
                commander_legality=item.card.commander_legality,
            )
            for item in analysis.cards
        ],
        unresolved=[UnresolvedOut.model_validate(asdict(item)) for item in analysis.unresolved],
        issues=[IssueOut.model_validate(asdict(issue)) for issue in analysis.issues],
    )


def _analyze(decklist: str, count_mdfc_lands: bool, repository: CardRepository) -> AnalysisResponse:
    analysis = analyze_decklist(
        decklist, repository, StatsOptions(count_mdfc_lands=count_mdfc_lands)
    )
    return to_response(analysis)


@router.post(
    "/analyses",
    response_model=AnalysisResponse,
    summary="Analisa uma lista de deck (JSON)",
)
def create_analysis(
    request: AnalysisRequest,
    repository: Annotated[CardRepository, Depends(get_card_repository)],
) -> AnalysisResponse:
    return _analyze(request.decklist, request.options.count_mdfc_lands, repository)


@router.post(
    "/analyses/text",
    response_model=AnalysisResponse,
    summary="Analisa uma lista de deck colada como texto puro",
    description=(
        "Igual a `POST /analyses`, mas o corpo é o próprio texto da lista "
        "(`Content-Type: text/plain`), exatamente como exportado do Moxfield, Archidekt, "
        "Arena ou MTGO. Não precisa escapar nada. A opção vai na query string."
    ),
)
def create_analysis_from_text(
    decklist: Annotated[
        str,
        Body(
            media_type="text/plain",
            min_length=1,
            max_length=MAX_DECKLIST_CHARS,
            description="A lista de deck, uma carta por linha.",
            examples=[EXAMPLE_DECKLIST],
        ),
    ],
    repository: Annotated[CardRepository, Depends(get_card_repository)],
    count_mdfc_lands: Annotated[
        bool, Query(description="Conta MDFC com terreno atrás no total de terrenos.")
    ] = True,
) -> AnalysisResponse:
    return _analyze(decklist, count_mdfc_lands, repository)
