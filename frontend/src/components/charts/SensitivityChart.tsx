import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { LandOdds } from '../../api/client'
import { t } from '../../i18n'
import { percent } from '../../lib/format'
import { ChartCard } from '../ChartCard'
import { ChartTooltip } from '../ChartTooltip'
import { DataTable } from '../DataTable'

type LandCount = NonNullable<LandOdds['land_count']>

const TICK = { fill: 'var(--ink-2)', fontSize: 12 }

function signed(delta: number): string {
  return delta > 0 ? `+${delta}` : String(delta)
}

/** Forma de ênfase: a barra do deck atual leva a cor da série, as demais ficam neutras. */
export function SensitivityChart({ landCount }: { landCount: LandCount }) {
  const data = landCount.sensitivity.map((point) => ({
    lands: point.lands,
    delta: point.delta,
    chance: point.p_land_drops * 100,
    current: point.delta === 0,
  }))
  const name = t('sensitivity.column.chance')
  return (
    <ChartCard
      title={t('sensitivity.title')}
      subtitle={t('sensitivity.subtitle', { turn: landCount.turn })}
      footer={landCount.required
        .map((item) =>
          item.lands === null || item.delta === null
            ? t('sensitivity.required.unreachable', { target: percent(item.target) })
            : t('sensitivity.required.item', {
                target: percent(item.target),
                lands: item.lands,
                diff: item.delta === 0 ? t('sensitivity.current') : signed(item.delta),
              }),
        )
        .join(' · ')}
      table={
        <DataTable
          caption={t('sensitivity.title')}
          columns={[
            t('sensitivity.column.lands'),
            t('sensitivity.column.diff'),
            t('sensitivity.column.chance'),
          ]}
          rows={landCount.sensitivity.map((point) => [
            point.lands,
            signed(point.delta),
            percent(point.p_land_drops),
          ])}
        />
      }
    >
      <div className="h-64" role="img" aria-label={t('sensitivity.title')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="lands" tick={TICK} stroke="var(--axis)" tickLine={false} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(value: number) => `${value}%`}
              tick={TICK}
              stroke="var(--axis)"
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: 'var(--grid)', opacity: 0.5 }}
              content={(props) => (
                <ChartTooltip
                  {...props}
                  formatLabel={(lands) => `${lands} ${t('sensitivity.column.lands').toLowerCase()}`}
                  formatValue={(value) => percent(value / 100)}
                />
              )}
            />
            <Bar dataKey="chance" name={name} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {data.map((point) => (
                <Cell key={point.lands} fill={point.current ? 'var(--series-1)' : 'var(--mark-muted)'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
