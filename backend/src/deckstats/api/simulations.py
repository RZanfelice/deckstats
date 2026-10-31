from dataclasses import asdict
from typing import Annotated, Self

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from deckstats.api.analyses import EXAMPLE_DECKLIST, MAX_DECKLIST_CHARS, IssueOut
from deckstats.api.deps import get_card_repository
from deckstats.catalog.repository import CardRepository
from deckstats.simulation.engine import SimulationOptions, SimulationResult
from deckstats.simulation.options import KeepPolicy
from deckstats.simulation.service import EmptyLibraryError, simulate_decklist

router = APIRouter(tags=["simulations"])

MAX_ITERATIONS = 30_000  # ~3,5 s com o modelo de mana completo
MIN_ITERATIONS = 100
COST_PATTERN = r"^(\{[^{}]+\})+$"
MAX_COSTS = 10


class SimulationOptionsIn(BaseModel):
    iterations: int = Field(10_000, ge=MIN_ITERATIONS, le=MAX_ITERATIONS)
    seed: int = Field(0, ge=0, description="Mesma semente, mesmo resultado.")
    on_the_play: bool = Field(False, description="Começa sem comprar no turno 1 (2 jogadores).")
    apply_mulligan: bool = Field(
        True, description="Aplica a política de mulligan à mão usada nos turnos."
    )
    free_mulligan: bool = Field(True, description="O primeiro mulligan é grátis (Commander).")
    max_mulligans: int = Field(3, ge=0, le=6)
    keep_min_lands: int = Field(2, ge=0, le=7, description="Mínimo de terrenos numa mão mantível.")
    keep_max_lands: int = Field(5, ge=0, le=7, description="Máximo de terrenos numa mão mantível.")
    keep_max_spell_mv: int = Field(
        3, ge=0, le=20, description="Uma mão mantível precisa de uma magia com MV até este valor."
    )
    keep_policy: KeepPolicy = Field(
        "castable",
        description=(
            "`castable`: só conta o que dá para conjurar com os terrenos da mão; rampa castável "
            "vale como terreno extra e cantrips baratos como fração de terreno. "
            "`simple`: terrenos no intervalo e uma magia de MV baixo, sem olhar a castabilidade."
        ),
    )
    keep_min_effective: float = Field(
        2.5,
        ge=0,
        le=7,
        description="(castable) Mínimo de terrenos efetivos: reais + rampa + fração dos cantrips.",
    )
    ramp_credit_cap: int = Field(
        2, ge=0, le=4, description="(castable) Quantas rampas castáveis contam como terreno."
    )
    cantrip_weight: float = Field(
        0.5, ge=0, le=1, description="(castable) Quanto de terreno vale cada cantrip (até 2)."
    )
    count_mdfc_lands: bool = Field(True, description="Conta MDFC com terreno atrás como terreno.")
    costs: list[Annotated[str, Field(pattern=COST_PATTERN)]] = Field(
        default_factory=list,
        max_length=MAX_COSTS,
        description="Custos extras a avaliar, como `{2}{U}{U}`.",
    )

    @model_validator(mode="after")
    def _keep_range(self) -> Self:
        if self.keep_min_lands > self.keep_max_lands:
            raise ValueError("keep_min_lands não pode ser maior que keep_max_lands")
        return self

    def to_engine(self) -> SimulationOptions:
        return SimulationOptions(
            iterations=self.iterations,
            seed=self.seed,
            on_the_play=self.on_the_play,
            apply_mulligan=self.apply_mulligan,
            free_mulligan=self.free_mulligan,
            max_mulligans=self.max_mulligans,
            keep_min_lands=self.keep_min_lands,
            keep_max_lands=self.keep_max_lands,
            keep_max_spell_mv=self.keep_max_spell_mv,
            keep_policy=self.keep_policy,
            keep_min_effective=self.keep_min_effective,
            ramp_credit_cap=self.ramp_credit_cap,
            cantrip_weight=self.cantrip_weight,
        )


class SimulationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"decklist": EXAMPLE_DECKLIST}]})

    decklist: str = Field(
        min_length=1,
        max_length=MAX_DECKLIST_CHARS,
        description=(
            "A lista inteira em UMA string (quebras de linha como `\\n`). "
            "Para colar direto, use `POST /simulations/text`."
        ),
    )
    options: SimulationOptionsIn = Field(default_factory=SimulationOptionsIn)


class EstimateOut(BaseModel):
    p: float
    ci_low: float = Field(description="Limite inferior do intervalo de Wilson a 95%.")
    ci_high: float
    n: int


class OpeningHandOut(BaseModel):
    keepable: EstimateOut = Field(description="M1: a 1ª mão de 7 cartas é mantível.")
    lands: dict[int, EstimateOut] = Field(description="Distribuição de terrenos na 1ª mão.")


class MulliganOut(BaseModel):
    at_least_one: EstimateOut = Field(description="M2: pelo menos um mulligan.")
    distribution: dict[int, EstimateOut]
    mean_final_hand_size: float


class CostOut(BaseModel):
    label: str
    source: str = Field(description="`commander`, `deck_color:<cor>` ou `custom`.")
    cost: str
    mana_value: int
    on_curve_turn: int | None
    by_turn: dict[int, EstimateOut] = Field(description="P(conseguir pagar o custo no turno).")


class ManaOut(BaseModel):
    plan_turn: int = Field(description="Turno-alvo da política de jogada de terrenos.")
    colors: list[str]
    sources: dict[int, dict[int, EstimateOut]] = Field(
        description="Turno -> X -> P(pelo menos X fontes de mana desviradas)."
    )
    color_sources: dict[str, dict[int, dict[int, EstimateOut]]] = Field(
        description="Cor -> turno -> k -> P(pelo menos k fontes dessa cor)."
    )
    costs: list[CostOut]
    unknown_mana_lands: list[str] = Field(
        description="Terrenos sem mana conhecida (ex.: fetchlands): contam como terreno, sem mana."
    )


class SimulationResponse(BaseModel):
    format: str
    commanders: list[str]
    commander_inferred: bool
    issues: list[IssueOut]
    options: SimulationOptionsIn
    iterations: int
    seed: int
    library_size: int
    lands_in_library: int
    opening_hand: OpeningHandOut
    mulligans: MulliganOut | None
    land_drops: dict[int, EstimateOut] = Field(
        description="M3: P(não perder nenhuma jogada de terreno até o turno)."
    )
    mana: ManaOut | None


def to_response(
    simulation_options: SimulationOptionsIn,
    run: "SimulationResult",
    analysis_info: dict[str, object],
) -> SimulationResponse:
    mana = run.mana
    return SimulationResponse.model_validate(
        {
            **analysis_info,
            "options": simulation_options,
            "iterations": run.iterations,
            "seed": run.seed,
            "library_size": run.library_size,
            "lands_in_library": run.lands_in_library,
            "opening_hand": {
                "keepable": asdict(run.first_hand_keepable),
                "lands": {k: asdict(v) for k, v in run.first_hand_lands.items()},
            },
            "mulligans": asdict(run.mulligans) if run.mulligans else None,
            "land_drops": {k: asdict(v) for k, v in run.land_drops.items()},
            "mana": asdict(mana) if mana else None,
        }
    )


def _run(
    decklist: str, options: SimulationOptionsIn, repository: CardRepository
) -> SimulationResponse:
    try:
        simulation = simulate_decklist(
            decklist,
            repository,
            options.to_engine(),
            count_mdfc_lands=options.count_mdfc_lands,
            extra_costs=options.costs,
        )
    except EmptyLibraryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    analysis = simulation.analysis
    info: dict[str, object] = {
        "format": analysis.format,
        "commanders": [entry.card.name for entry in analysis.deck.commanders],
        "commander_inferred": analysis.commander_inferred,
        "issues": [asdict(issue) for issue in analysis.issues],
    }
    return to_response(options, simulation.result, info)


@router.post(
    "/simulations",
    response_model=SimulationResponse,
    summary="Simula a consistência de mana de um deck (JSON)",
)
def create_simulation(
    request: SimulationRequest,
    repository: Annotated[CardRepository, Depends(get_card_repository)],
) -> SimulationResponse:
    return _run(request.decklist, request.options, repository)


@router.post(
    "/simulations/text",
    response_model=SimulationResponse,
    summary="Simula a consistência de mana de um deck colado como texto puro",
    description=(
        "Igual a `POST /simulations`, mas o corpo é o próprio texto da lista "
        "(`Content-Type: text/plain`). As opções vão na query string; "
        "repita `costs` para avaliar mais de um custo."
    ),
)
def create_simulation_from_text(
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
    iterations: Annotated[int, Query(ge=MIN_ITERATIONS, le=MAX_ITERATIONS)] = 10_000,
    seed: Annotated[int, Query(ge=0)] = 0,
    on_the_play: bool = False,
    apply_mulligan: bool = True,
    free_mulligan: bool = True,
    max_mulligans: Annotated[int, Query(ge=0, le=6)] = 3,
    keep_min_lands: Annotated[int, Query(ge=0, le=7)] = 2,
    keep_max_lands: Annotated[int, Query(ge=0, le=7)] = 5,
    keep_max_spell_mv: Annotated[int, Query(ge=0, le=20)] = 3,
    keep_policy: KeepPolicy = "castable",
    keep_min_effective: Annotated[float, Query(ge=0, le=7)] = 2.5,
    ramp_credit_cap: Annotated[int, Query(ge=0, le=4)] = 2,
    cantrip_weight: Annotated[float, Query(ge=0, le=1)] = 0.5,
    count_mdfc_lands: bool = True,
    costs: Annotated[
        list[str] | None, Query(max_length=MAX_COSTS, description="Custos extras, como {2}{U}{U}.")
    ] = None,
) -> SimulationResponse:
    try:
        options = SimulationOptionsIn(
            iterations=iterations,
            seed=seed,
            on_the_play=on_the_play,
            apply_mulligan=apply_mulligan,
            free_mulligan=free_mulligan,
            max_mulligans=max_mulligans,
            keep_min_lands=keep_min_lands,
            keep_max_lands=keep_max_lands,
            keep_max_spell_mv=keep_max_spell_mv,
            keep_policy=keep_policy,
            keep_min_effective=keep_min_effective,
            ramp_credit_cap=ramp_credit_cap,
            cantrip_weight=cantrip_weight,
            count_mdfc_lands=count_mdfc_lands,
            costs=costs or [],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _run(decklist, options, repository)
