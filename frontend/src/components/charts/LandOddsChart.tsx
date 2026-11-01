import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { LandOdds } from '../../api/client'
import { t } from '../../i18n'
import { decimal, percent } from '../../lib/format'
import { ChartCard } from '../ChartCard'
import { ChartTooltip } from '../ChartTooltip'
import { DataTable } from '../DataTable'

const TICK = { fill: 'var(--ink-2)', fontSize: 12 }

export function LandOddsChart({ odds }: { odds: LandOdds }) {
  const data = odds.by_turn.map((row) => ({
    turn: row.turn,
    chance: row.p_land_drops * 100,
  }))
  const critical = odds.critical_turn
  const name = t('odds.column.chance')
  return (
    <ChartCard
      title={t('odds.title')}
      subtitle={t('odds.subtitle')}
      footer={t('odds.note')}
      table={
        <DataTable
          caption={t('odds.title')}
          columns={[
            t('odds.column.turn'),
            t('odds.column.seen'),
            t('odds.column.expected'),
            t('odds.column.chance'),
          ]}
          rows={odds.by_turn.map((row) => [
            row.turn,
            row.cards_seen,
            decimal(row.expected_lands),
            percent(row.p_land_drops),
          ])}
        />
      }
    >
      <div className="h-64" role="img" aria-label={t('odds.title')}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="turn" tick={TICK} stroke="var(--axis)" tickLine={false} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(value: number) => `${value}%`}
              tick={TICK}
              stroke="var(--axis)"
              tickLine={false}
            />
            {critical && (
              <ReferenceLine
                x={critical.turn}
                stroke="var(--ink-3)"
                strokeDasharray="4 3"
                label={{
                  value: t('odds.critical', {
                    turn: critical.turn,
                    value: percent(odds.at_critical_turn?.p_land_drops ?? 0),
                  }),
                  position: 'insideBottomRight',
                  fill: 'var(--ink-2)',
                  fontSize: 12,
                }}
              />
            )}
            <Tooltip
              content={(props) => (
                <ChartTooltip
                  {...props}
                  formatLabel={(turn) => `${t('odds.column.turn')} ${turn}`}
                  formatValue={(value) => percent(value / 100)}
                />
              )}
            />
            <Line
              type="monotone"
              dataKey="chance"
              name={name}
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={{ r: 4, fill: 'var(--series-1)', stroke: 'var(--surface)', strokeWidth: 2 }}
              activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
