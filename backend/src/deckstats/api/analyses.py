from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from deckstats.api.deps import get_card_repository
from deckstats.catalog.repository import CardRepository
from deckstats.deck.analysis import Analysis, analyze_decklist
from deckstats.deck.odds import DEFAULT_COMMANDER_WEIGHT
from deckstats.deck.stats import StatsOptions

router = APIRouter(tags=["analyses"])

MAX_DECKLIST_CHARS = 20_000
EXAMPLE_DECKLIST = "Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring\n98 Forest"


class AnalysisOptions(BaseModel):
    count_mdfc_lands: bool = Field(
        default=True, description="Conta MDFC com terreno atrás no total de terrenos."
    )
    commander_weight: float = Field(
        default=DEFAULT_COMMANDER_WEIGHT,
        ge=0,
        le=1,
        description=(
            "Peso do custo do comandante no turno crítico; o restante vai para o MV médio "
            "das demais cartas."
        ),
    )
    on_the_play: bool = Field(
        default=False,
        description=(
            "Começa sem comprar no turno 1 (jogo de 2 jogadores). "
            "Em Commander com mais de 2 jogadores todos compram, que é o padrão."
        ),
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
    categories: list[str] = Field(
        description="Categorias da carta (ramp, card_draw...), incluindo as implicadas."
    )


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


class CategoryCountOut(BaseModel):
    category: str
    supported: bool = Field(description="Falso para categorias que as regras não decidem.")
    count: int = Field(description="Cópias no deck principal.")
    percent: float = Field(description="Fração do deck principal, de 0 a 1.")
    cards: list[str]


class CategoriesOut(BaseModel):
    classifier_version: str
    main_cards: int
    categories: list[CategoryCountOut]
    commander_categories: dict[str, list[str]]


class CriticalTurnOut(BaseModel):
    raw: float = Field(description="Valor antes de arredondar.")
    turn: int
    commander_mana_value: float | None
    average_mana_value: float | None
    commander_weight: float = Field(
        description="Peso efetivamente usado (0 ou 1 se faltou um insumo)."
    )


class TurnOddsOut(BaseModel):
    turn: int
    cards_seen: int
    expected_lands: float
    p_land_drops: float = Field(
        description="Chance de ter pelo menos `turn` terrenos entre as cartas vistas."
    )
    p_at_least: dict[int, float] = Field(
        description="Chance de ter pelo menos k terrenos, k de 1 a 10."
    )


class LandCountPointOut(BaseModel):
    lands: int
    delta: int = Field(description="Diferença para os terrenos atuais do deck.")
    p_land_drops: float


class LandRequirementOut(BaseModel):
    target: float
    lands: int | None = Field(
        description="Menor número de terrenos que atinge a meta; nulo se nem a biblioteca basta."
    )
    delta: int | None = Field(
        description="Terrenos a adicionar (positivo) ou sobrando (negativo) em relação ao deck."
    )


class LandCountAnalysisOut(BaseModel):
    turn: int = Field(description="Turno crítico usado.")
    cards_seen: int
    current_lands: int
    current_probability: float = Field(
        description="Chance de não perder nenhum terreno até o turno crítico (terrenos atuais)."
    )
    sensitivity: list[LandCountPointOut] = Field(
        description="A mesma chance com 5 terrenos a menos até 5 a mais que o deck atual."
    )
    required: list[LandRequirementOut] = Field(
        description="Terrenos necessários para atingir 70%, 80% e 90%."
    )


class LandOddsOut(BaseModel):
    library_size: int
    lands_in_library: int
    on_the_play: bool
    critical_turn: CriticalTurnOut | None
    by_turn: list[TurnOddsOut]
    at_critical_turn: TurnOddsOut | None
    land_count: LandCountAnalysisOut | None


class AnalysisResponse(BaseModel):
    format: str
    commander_inferred: bool
    commanders: list[str]
    options: AnalysisOptions
    stats: StatsOut
    land_odds: LandOddsOut | None
    categories: CategoriesOut
    cards: list[CardOut]
    unresolved: list[UnresolvedOut]
    issues: list[IssueOut]


def to_response(analysis: Analysis) -> AnalysisResponse:
    return AnalysisResponse(
        format=analysis.format,
        commander_inferred=analysis.commander_inferred,
        commanders=[entry.card.name for entry in analysis.deck.commanders],
        options=AnalysisOptions(**asdict(analysis.options)),
        stats=StatsOut.model_validate(asdict(analysis.stats)),
        land_odds=(
            LandOddsOut.model_validate(asdict(analysis.land_odds)) if analysis.land_odds else None
        ),
        categories=CategoriesOut.model_validate(asdict(analysis.categories)),
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
                categories=sorted(item.categories),
            )
            for item in analysis.cards
        ],
        unresolved=[UnresolvedOut.model_validate(asdict(item)) for item in analysis.unresolved],
        issues=[IssueOut.model_validate(asdict(issue)) for issue in analysis.issues],
    )


def _analyze(
    decklist: str, options: AnalysisOptions, repository: CardRepository
) -> AnalysisResponse:
    analysis = analyze_decklist(decklist, repository, StatsOptions(**options.model_dump()))
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
    return _analyze(request.decklist, request.options, repository)


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
    commander_weight: Annotated[
        float,
        Query(ge=0, le=1, description="Peso do custo do comandante no turno crítico."),
    ] = DEFAULT_COMMANDER_WEIGHT,
    on_the_play: Annotated[
        bool, Query(description="Começa sem comprar no turno 1 (jogo de 2 jogadores).")
    ] = False,
) -> AnalysisResponse:
    options = AnalysisOptions(
        count_mdfc_lands=count_mdfc_lands,
        commander_weight=commander_weight,
        on_the_play=on_the_play,
    )
    return _analyze(decklist, options, repository)
