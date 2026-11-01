import type { AnalysisResponse } from '../../api/client'
import { t, typeName } from '../../i18n'
import { ChartCard } from '../ChartCard'
import { DataTable } from '../DataTable'
import { HorizontalBars } from './HorizontalBars'

export function TypesChart({ stats }: { stats: AnalysisResponse['stats'] }) {
  const data = Object.entries(stats.types)
    .map(([id, value]) => ({ label: typeName(id), value }))
    .sort((a, b) => b.value - a.value)
  return (
    <ChartCard
      title={t('types.title')}
      subtitle={t('types.subtitle')}
      footer={t('types.permanents', {
        permanent: stats.permanents.permanent ?? 0,
        nonPermanent: stats.permanents.non_permanent ?? 0,
      })}
      table={
        <DataTable
          caption={t('types.title')}
          columns={[t('types.title'), t('curve.column.count')]}
          rows={data.map((row) => [row.label, row.value])}
        />
      }
    >
      <HorizontalBars data={data} seriesName={t('curve.column.count')} ariaLabel={t('types.title')} />
    </ChartCard>
  )
}
