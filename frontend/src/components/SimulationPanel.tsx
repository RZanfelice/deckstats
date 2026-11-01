import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  COST_PATTERN,
  DEFAULT_SIMULATE_OPTIONS,
  simulateText,
  type AnalyzeOptions,
  type Estimate,
  type KeepPolicy,
  type SimulateOptions,
} from '../api/client'
import { list, t } from '../i18n'
import { decimal, percent } from '../lib/format'
import {
  ColorSourcesTable,
  CostsChart,
  LandDropsChart,
  OpeningLandsChart,
} from './charts/SimulationCharts'
import { StatTile } from './StatTile'

interface SimulationPanelProps {
  text: string
  analysis: AnalyzeOptions
}

const ITERATIONS = [2000, 5000, 10000]

function ciHint(estimate: Estimate): string {
  return t('sim.ci', { low: percent(estimate.ci_low), high: percent(estimate.ci_high) })
}

/** Roda sob demanda (leva alguns segundos); o pai troca a `key` quando a lista muda. */
export function SimulationPanel({ text, analysis }: SimulationPanelProps) {
  const [draft, setDraft] = useState<SimulateOptions>(DEFAULT_SIMULATE_OPTIONS)
  const [submitted, setSubmitted] = useState<SimulateOptions | null>(null)

  const costInvalid = draft.extraCost.trim() !== '' && !COST_PATTERN.test(draft.extraCost.trim())

  const query = useQuery({
    queryKey: ['simulation', text, analysis, submitted],
    queryFn: ({ signal }) => simulateText(text, analysis, submitted!, signal),
    enabled: submitted !== null,
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: Infinity,
  })
  const result = query.data
  const refreshing = query.isFetching && result !== undefined

  return (
    <section aria-label={t('sim.title')} className="space-y-4">
      <div className="rounded-lg border border-ring bg-surface p-4">
        <h2 className="text-base font-semibold text-ink">{t('sim.title')}</h2>
        <p className="mb-3 text-xs text-ink-2">{t('sim.subtitle')}</p>
        <form
          className="flex flex-wrap items-end gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (!costInvalid) setSubmitted({ ...draft, extraCost: draft.extraCost.trim() })
          }}
        >
          <label className="text-sm text-ink">
            <span className="mb-1 block text-xs text-ink-2">{t('sim.iterations')}</span>
            <select
              value={draft.iterations}
              onChange={(event) => setDraft({ ...draft, iterations: Number(event.target.value) })}
              className="rounded border border-ring bg-page px-2 py-1"
            >
              {ITERATIONS.map((value) => (
                <option key={value} value={value}>
                  {value.toLocaleString('pt-BR')}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-ink">
            <span className="mb-1 block text-xs text-ink-2">{t('sim.keepPolicy')}</span>
            <select
              value={draft.keepPolicy}
              onChange={(event) => setDraft({ ...draft, keepPolicy: event.target.value as KeepPolicy })}
              className="rounded border border-ring bg-page px-2 py-1"
            >
              <option value="castable">{t('sim.keepPolicy.castable')}</option>
              <option value="simple">{t('sim.keepPolicy.simple')}</option>
            </select>
          </label>
          <label className="text-sm text-ink">
            <span className="mb-1 block text-xs text-ink-2">{t('sim.extraCost')}</span>
            <input
              value={draft.extraCost}
              onChange={(event) => setDraft({ ...draft, extraCost: event.target.value })}
              placeholder="{2}{U}{U}"
              aria-label={t('sim.extraCost')}
              aria-invalid={costInvalid}
              className="w-32 rounded border border-ring bg-page px-2 py-1 font-mono"
            />
          </label>
          <label className="flex items-center gap-2 pb-1 text-sm text-ink">
            <input
              type="checkbox"
              checked={draft.castRamp}
              onChange={(event) => setDraft({ ...draft, castRamp: event.target.checked })}
            />
            {t('sim.castRamp')}
          </label>
          <button
            type="submit"
            disabled={query.isFetching || costInvalid}
            className="rounded bg-series-1 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {query.isFetching ? t('sim.running') : result ? t('sim.rerun') : t('sim.run')}
          </button>
        </form>
        {costInvalid && (
          <p role="alert" className="mt-2 text-xs text-critical">
            {t('sim.extraCost.invalid')}
          </p>
        )}
      </div>

      {query.isError && (
        <div role="alert" className="rounded-lg border border-critical bg-surface p-4 text-sm text-ink">
          <strong>{t('sim.error')}</strong>
          <div className="text-ink-2">{query.error.message}</div>
        </div>
      )}

      {result && (
        <div className={`space-y-4 transition-opacity ${refreshing ? 'opacity-50' : ''}`} aria-busy={refreshing}>
          <p className="text-xs text-ink-2">{t('sim.noteSample', { iterations: result.iterations.toLocaleString('pt-BR') })}</p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <StatTile
              label={t('sim.keepable')}
              value={percent(result.opening_hand.keepable.p)}
              hint={ciHint(result.opening_hand.keepable)}
            />
            {result.mulligans && (
              <>
                <StatTile
                  label={t('sim.mulligan')}
                  value={percent(result.mulligans.at_least_one.p)}
                  hint={ciHint(result.mulligans.at_least_one)}
                />
                <StatTile
                  label={t('sim.handSize')}
                  value={decimal(result.mulligans.mean_final_hand_size)}
                  hint={t('sim.handSize.hint')}
                />
              </>
            )}
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            {result.mana && <CostsChart mana={result.mana} />}
            <LandDropsChart drops={result.land_drops} />
            <OpeningLandsChart lands={result.opening_hand.lands} />
            {result.mana && <ColorSourcesTable mana={result.mana} />}
          </div>
          {result.mana && result.mana.unknown_mana_lands.length > 0 && (
            <p className="text-xs text-ink-3">
              {t('sim.unknownLands', { cards: list(result.mana.unknown_mana_lands) })}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
