import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { analyzeText, DEFAULT_OPTIONS, type AnalysisResponse, type AnalyzeOptions } from '../api/client'
import { CardsTable } from '../components/CardsTable'
import { CategoriesChart } from '../components/charts/CategoriesChart'
import { ColorsChart } from '../components/charts/ColorsChart'
import { LandOddsChart } from '../components/charts/LandOddsChart'
import { ManaCurveChart } from '../components/charts/ManaCurveChart'
import { SensitivityChart } from '../components/charts/SensitivityChart'
import { TypesChart } from '../components/charts/TypesChart'
import { DeckForm } from '../components/DeckForm'
import { IssuesList } from '../components/IssuesList'
import { SimulationPanel } from '../components/SimulationPanel'
import { StatTile } from '../components/StatTile'
import { colorName, list, t } from '../i18n'
import { decimal } from '../lib/format'

interface Submission {
  text: string
  options: AnalyzeOptions
}

function Summary({ analysis }: { analysis: AnalysisResponse }) {
  const { stats, land_odds: odds } = analysis
  const identity = stats.color_identity.map(colorName)
  return (
    <section aria-label={t('summary.title')} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile
        label={analysis.commanders.length > 1 ? t('summary.commanders') : t('summary.commander')}
        value={<span className="text-base">{analysis.commanders.join(' / ') || t('summary.noCommander')}</span>}
        hint={`${t('summary.identity')}: ${identity.length ? list(identity) : t('summary.identity.none')}`}
      />
      <StatTile label={t('summary.cards')} value={stats.played_cards} />
      <StatTile
        label={t('summary.lands')}
        value={stats.lands.total}
        hint={stats.lands.mdfc_lands ? t('summary.lands.mdfc', { count: stats.lands.mdfc_lands }) : undefined}
      />
      <StatTile
        label={odds?.critical_turn ? t('summary.criticalTurn') : t('summary.averageMv')}
        value={odds?.critical_turn ? odds.critical_turn.turn : decimal(stats.average_mana_value)}
        hint={odds?.critical_turn ? t('summary.criticalTurn.hint', { raw: decimal(odds.critical_turn.raw) }) : undefined}
      />
    </section>
  )
}

export function AnalyzePage() {
  const [submission, setSubmission] = useState<Submission | null>(null)

  const query = useQuery({
    queryKey: ['analysis', submission],
    queryFn: ({ signal }) => analyzeText(submission!.text, submission!.options, signal),
    enabled: submission !== null,
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: Infinity,
  })
  const analysis = query.data
  const refreshing = query.isFetching && analysis !== undefined

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[22rem_1fr]">
      <aside>
        <DeckForm
          initialText=""
          initialOptions={DEFAULT_OPTIONS}
          busy={query.isFetching}
          onSubmit={(text, options) => setSubmission({ text, options })}
        />
      </aside>

      <div aria-busy={query.isFetching} className="space-y-4">
        {query.isError && (
          <div role="alert" className="rounded-lg border border-critical bg-surface p-4 text-sm text-ink">
            <strong>{t('state.error')}</strong>
            <div className="text-ink-2">{query.error.message}</div>
          </div>
        )}
        {!analysis && !query.isError && !query.isFetching && (
          <p className="rounded-lg border border-dashed border-ring p-8 text-center text-sm text-ink-2">
            {t('state.empty')}
          </p>
        )}
        {analysis && (
          <div className={`space-y-4 transition-opacity ${refreshing ? 'opacity-50' : ''}`}>
            {refreshing && <p className="text-xs text-ink-2">{t('state.refreshing')}</p>}
            <Summary analysis={analysis} />
            <IssuesList issues={analysis.issues} unresolved={analysis.unresolved} />
            <div className="grid gap-4 xl:grid-cols-2">
              <ManaCurveChart stats={analysis.stats} />
              {analysis.land_odds ? (
                <LandOddsChart odds={analysis.land_odds} />
              ) : (
                <p className="rounded-lg border border-ring bg-surface p-4 text-sm text-ink-2">
                  {t('odds.unavailable')}
                </p>
              )}
              {analysis.land_odds?.land_count && <SensitivityChart landCount={analysis.land_odds.land_count} />}
              <ColorsChart stats={analysis.stats} />
              <TypesChart stats={analysis.stats} />
              <CategoriesChart categories={analysis.categories} />
            </div>
            {submission && (
              <SimulationPanel
                key={`${submission.text}|${JSON.stringify(submission.options)}`}
                text={submission.text}
                analysis={submission.options}
              />
            )}
            <CardsTable cards={analysis.cards} />
          </div>
        )}
      </div>
    </div>
  )
}
