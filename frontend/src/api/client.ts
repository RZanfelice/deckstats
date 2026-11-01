import type { components } from './schema'

export type AnalysisResponse = components['schemas']['AnalysisResponse']
export type Issue = components['schemas']['IssueOut']
export type CardOut = components['schemas']['CardOut']
export type CategoryCount = components['schemas']['CategoryCountOut']
export type LandOdds = components['schemas']['LandOddsOut']
export type TurnOdds = components['schemas']['TurnOddsOut']
export type Unresolved = components['schemas']['UnresolvedOut']

export interface AnalyzeOptions {
  countMdfcLands: boolean
  commanderWeight: number
  onThePlay: boolean
}

export const DEFAULT_OPTIONS: AnalyzeOptions = {
  countMdfcLands: true,
  commanderWeight: 0.6,
  onThePlay: false,
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** FastAPI devolve `detail` como texto ou como lista de erros de validação. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    const detail = (body as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item as { msg?: string }).msg)
        .filter(Boolean)
        .join('; ')
    }
  } catch {
    // corpo que não é JSON: cai na mensagem genérica
  }
  return `Erro ${response.status}`
}

export type SimulationResponse = components['schemas']['SimulationResponse']
export type Estimate = components['schemas']['EstimateOut']
export type CostResult = components['schemas']['CostOut']

export type KeepPolicy = 'castable' | 'simple'

export interface SimulateOptions {
  iterations: number
  keepPolicy: KeepPolicy
  castRamp: boolean
  /** Custo extra a avaliar, como `{2}{U}{U}`; vazio = nenhum. */
  extraCost: string
}

export const DEFAULT_SIMULATE_OPTIONS: SimulateOptions = {
  iterations: 5000,
  keepPolicy: 'castable',
  castRamp: true,
  extraCost: '',
}

export const COST_PATTERN = /^(\{[^{}]+\})+$/

export async function simulateText(
  text: string,
  analysis: AnalyzeOptions,
  options: SimulateOptions,
  signal?: AbortSignal,
): Promise<SimulationResponse> {
  const query = new URLSearchParams({
    iterations: String(options.iterations),
    keep_policy: options.keepPolicy,
    cast_ramp: String(options.castRamp),
    count_mdfc_lands: String(analysis.countMdfcLands),
    on_the_play: String(analysis.onThePlay),
  })
  const cost = options.extraCost.trim()
  if (cost) query.append('costs', cost)
  const response = await fetch(`/api/simulations/text?${query}`, {
    method: 'POST',
    headers: { 'content-type': 'text/plain; charset=utf-8' },
    body: text,
    signal,
  })
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return (await response.json()) as SimulationResponse
}

export async function analyzeText(
  text: string,
  options: AnalyzeOptions,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  const query = new URLSearchParams({
    count_mdfc_lands: String(options.countMdfcLands),
    commander_weight: String(options.commanderWeight),
    on_the_play: String(options.onThePlay),
  })
  const response = await fetch(`/api/analyses/text?${query}`, {
    method: 'POST',
    headers: { 'content-type': 'text/plain; charset=utf-8' },
    body: text,
    signal,
  })
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return (await response.json()) as AnalysisResponse
}
