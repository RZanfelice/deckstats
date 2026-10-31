from dataclasses import dataclass
from math import sqrt

Z_95 = 1.959964


@dataclass(frozen=True, slots=True)
class Estimate:
    """Proporção estimada por simulação, com intervalo de confiança de Wilson a 95%."""

    p: float
    ci_low: float
    ci_high: float
    n: int


def estimate(successes: int, n: int) -> Estimate:
    """Estima ``successes / n`` com o intervalo de Wilson.

    Wilson se comporta bem perto de 0 e de 1 (onde o intervalo normal simples
    sai do intervalo [0, 1]), que é onde caem muitas das probabilidades de mana.
    """
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError(f"contagem inválida: {successes} sucessos em {n} tentativas")
    p = successes / n
    z2 = Z_95**2
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    half = Z_95 * sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    # Nos extremos (0 ou n sucessos) o limite de Wilson é exatamente 0 ou 1, mas o ponto
    # flutuante pode errar por 1 ulp e deixar p fora do próprio intervalo.
    low = min(p, max(0.0, center - half))
    high = max(p, min(1.0, center + half))
    return Estimate(p=p, ci_low=low, ci_high=high, n=n)
