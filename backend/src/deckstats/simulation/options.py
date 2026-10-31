from dataclasses import dataclass
from typing import Literal

from deckstats.deck.odds import MAX_TURN, OPENING_HAND

KeepPolicy = Literal["simple", "castable"]


@dataclass(frozen=True, slots=True)
class SimulationOptions:
    iterations: int = 10_000
    seed: int = 0
    on_the_play: bool = False
    # Aplica a política de mulligan à mão usada nos turnos. Sem isso, vale a 1ª mão de 7.
    apply_mulligan: bool = True
    free_mulligan: bool = True
    max_mulligans: int = 3
    keep_min_lands: int = 2
    keep_max_lands: int = 5
    keep_max_spell_mv: int = 3
    max_turn: int = MAX_TURN

    # Regra de mão mantível. "simple": terrenos no intervalo e uma magia de MV baixo.
    # "castable": só vale a magia que dá para conjurar com os terrenos da mão; rampa
    # castável conta como terreno extra e cantrips baratos como fração de terreno.
    keep_policy: KeepPolicy = "simple"
    keep_min_effective: float = 2.5
    ramp_credit_cap: int = 2
    cantrip_weight: float = 0.5

    # Cada partida usa a própria semente (seed e índice), então duas execuções com
    # políticas diferentes veem os mesmos embaralhamentos e podem ser comparadas par a par.
    paired_seeds: bool = False

    def __post_init__(self) -> None:
        if self.iterations < 1:
            raise ValueError("iterations deve ser pelo menos 1")
        if not 0 <= self.max_mulligans <= OPENING_HAND - 1:
            raise ValueError(f"max_mulligans deve estar entre 0 e {OPENING_HAND - 1}")
        if not 0 <= self.keep_min_lands <= self.keep_max_lands <= OPENING_HAND:
            raise ValueError("limites de terrenos inválidos para uma mão mantível")
        if not 1 <= self.max_turn <= MAX_TURN:
            raise ValueError(f"max_turn deve estar entre 1 e {MAX_TURN}")
        if self.keep_min_effective < 0:
            raise ValueError("keep_min_effective não pode ser negativo")
        if not 0 <= self.ramp_credit_cap <= 4:
            raise ValueError("ramp_credit_cap deve estar entre 0 e 4")
        if not 0 <= self.cantrip_weight <= 1:
            raise ValueError("cantrip_weight deve estar entre 0 e 1")
