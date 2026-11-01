import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { AnalysisResponse } from '../../api/client'
import { colorName, t } from '../../i18n'
import { ChartCard } from '../ChartCard'
import { ChartTooltip } from '../ChartTooltip'
import { DataTable } from '../DataTable'

const TICK = { fill: 'var(--ink-2)', fontSize: 12 }
const COLOR_ORDER = ['W', 'U', 'B', 'R', 'G', 'colorless']

export function ColorsChart({ stats }: { stats: AnalysisResponse['stats'] }) {
  const data = COLOR_ORDER.map((id) => ({
    id,
    label: colorName(id),
    cards: stats.card_colors[id] ?? 0,
    pips: stats.pips[id] ?? 0,
  }))
  const cardsName = t('colors.series.cards')
  const pipsName = t('colors.series.pips')
  return (
    <ChartCard
      title={t('colors.title')}
      subtitle={t('colors.subtitle')}
      footer={t('colors.multicolor', { count: stats.multicolor_cards })}
      table={
        <DataTable
          caption={t('colors.title')}
          columns={[t('colors.title'), cardsName, pipsName]}
          rows={data.map((row) => [row.label, row.cards, row.pips])}
        />
      }
    >
      <div className="h-64" role="img" aria-label={t('colors.title')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="label" tick={TICK} stroke="var(--axis)" tickLine={false} />
            <YAxis allowDecimals={false} tick={TICK} stroke="var(--axis)" tickLine={false} />
            <Legend
              iconType="square"
              iconSize={10}
              formatter={(value: string) => <span className="text-xs text-ink-2">{value}</span>}
            />
            <Tooltip
              cursor={{ fill: 'var(--grid)', opacity: 0.5 }}
              content={(props) => <ChartTooltip {...props} formatValue={String} />}
            />
            <Bar
              dataKey="cards"
              name={cardsName}
              fill="var(--series-1)"
              maxBarSize={24}
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
            <Bar
              dataKey="pips"
              name={pipsName}
              fill="var(--series-2)"
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
