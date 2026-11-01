import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { AnalysisResponse } from '../../api/client'
import { t } from '../../i18n'
import { decimal } from '../../lib/format'
import { ChartCard } from '../ChartCard'
import { ChartTooltip } from '../ChartTooltip'
import { DataTable } from '../DataTable'

const TICK = { fill: 'var(--ink-2)', fontSize: 12 }

export function ManaCurveChart({ stats }: { stats: AnalysisResponse['stats'] }) {
  const data = Object.entries(stats.curve).map(([mv, count]) => ({ mv, count }))
  const name = t('curve.column.count')
  return (
    <ChartCard
      title={t('curve.title')}
      subtitle={t('curve.subtitle')}
      footer={`${t('summary.averageMv')}: ${decimal(stats.average_mana_value)} · ${t('summary.averageMv.hint', { median: decimal(stats.median_mana_value) })}`}
      table={
        <DataTable
          caption={t('curve.title')}
          columns={[t('curve.column.mv'), t('curve.column.count')]}
          rows={data.map((row) => [row.mv, row.count])}
        />
      }
    >
      <div className="h-64" role="img" aria-label={t('curve.title')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="mv" tick={TICK} stroke="var(--axis)" tickLine={false} />
            <YAxis allowDecimals={false} tick={TICK} stroke="var(--axis)" tickLine={false} />
            <Tooltip
              cursor={{ fill: 'var(--grid)', opacity: 0.5 }}
              content={(props) => (
                <ChartTooltip
                  {...props}
                  formatLabel={(mv) => `${t('curve.column.mv')} ${mv}`}
                  formatValue={String}
                />
              )}
            />
            <Bar
              dataKey="count"
              name={name}
              fill="var(--series-1)"
              maxBarSize={24}
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
