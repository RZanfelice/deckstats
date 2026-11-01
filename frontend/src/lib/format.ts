const percentFormat = new Intl.NumberFormat('pt-BR', {
  style: 'percent',
  maximumFractionDigits: 1,
})
const decimalFormat = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })

/** 0,6213 -> "62,1%" */
export function percent(fraction: number): string {
  return percentFormat.format(fraction)
}

/** 3.17 -> "3,17"; null -> "–" */
export function decimal(value: number | null | undefined): string {
  return value == null ? '–' : decimalFormat.format(value)
}

/** Valor percentual (0-100) já escalado, para eixos: 62 -> "62%". */
export function axisPercent(value: number): string {
  return `${value}%`
}
