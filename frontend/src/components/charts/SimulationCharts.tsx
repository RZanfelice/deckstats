import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Estimate, SimulationResponse } from '../../api/client'
import { colorName, t } from '../../i18n'
import { percent } from '../../lib/format'
import { ChartCard } from '../ChartCard'
import { ChartTooltip } from '../ChartTooltip'
import { DataTable } from '../DataTable'

const TICK = { fill: 'var(--ink-2)', fontSize: 12 }
const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']
const MAX_LINES = SERIES.length

const byNumber = ([a]: [string, unknown], [b]: [string, unknown]) => Number(a) - Number(b)
const entries = (record: Record<string, Estimate>) => Object.entries(record).sort(byNumber)
const pct = (estimate: Estimate) => estimate.p * 100

const yAxis = (
  <YAxis
    domain={[0, 100]}
    tickFormatter={(value: number) => `${value}%`}
    tick={TICK}
    stroke="var(--axis)"
    tickLine={false}
  />
)

function ciText(estimate: Estimate): string {
  return `${percent(estimate.p)} (${percent(estimate.ci_low)}–${percent(estimate.ci_high)})`
}

function costLabel(cost: SimulationResponse['mana'] & object, index: number): string {
  const item = cost.costs[index]!
  return item.source === 'commander' ? `${t('sim.costs.commander')} ${item.cost}` : item.cost
}

export function CostsChart({ mana }: { mana: NonNullable<SimulationResponse['mana']> }) {
  const shown = mana.costs.slice(0, MAX_LINES)
  const turns = entries(mana.costs[0]?.by_turn ?? {}).map(([turn]) => turn)
  const data = turns.map((turn) => ({
    turn: Number(turn),
    ...Object.fromEntries(shown.map((cost, i) => [`c${i}`, pct(cost.by_turn[turn]!)])),
  }))
  const labels = shown.map((_, i) => costLabel(mana, i))
  return (
    <ChartCard
      title={t('sim.costs.title')}
      subtitle={t('sim.costs.subtitle')}
      footer={mana.costs.length > MAX_LINES ? t('sim.costs.limit') : undefined}
      table={
        <DataTable
          caption={t('sim.costs.title')}
          columns={[t('odds.column.turn'), ...mana.costs.map((_, i) => costLabel(mana, i))]}
          rows={turns.map((turn) => [turn, ...mana.costs.map((cost) => ciText(cost.by_turn[turn]!))])}
        />
      }
    >
      <div className="h-72" role="img" aria-label={t('sim.costs.title')}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="turn" tick={TICK} stroke="var(--axis)" tickLine={false} />
            {yAxis}
            <Legend
              iconType="plainline"
              formatter={(value: string) => <span className="text-xs text-ink-2">{value}</span>}
            />
            <Tooltip
              content={(props) => (
                <ChartTooltip
                  {...props}
                  formatLabel={(turn) => `${t('odds.column.turn')} ${turn}`}
                  formatValue={(value) => percent(value / 100)}
                />
              )}
            />
            {shown.map((_, i) => (
              <Line
                key={i}
                type="monotone"
                dataKey={`c${i}`}
                name={labels[i]}
                stroke={SERIES[i]}
                strokeWidth={2}
                dot={{ r: 4, fill: SERIES[i], stroke: 'var(--surface)', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

export function LandDropsChart({ drops }: { drops: SimulationResponse['land_drops'] }) {
  const rows = entries(drops)
  const data = rows.map(([turn, estimate]) => ({ turn: Number(turn), chance: pct(estimate) }))
  const name = t('odds.column.chance')
  return (
    <ChartCard
      title={t('sim.drops.title')}
      subtitle={t('sim.drops.subtitle')}
      table={
        <DataTable
          caption={t('sim.drops.title')}
          columns={[t('odds.column.turn'), name]}
          rows={rows.map(([turn, estimate]) => [turn, ciText(estimate)])}
        />
      }
    >
      <div className="h-64" role="img" aria-label={t('sim.drops.title')}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="turn" tick={TICK} stroke="var(--axis)" tickLine={false} />
            {yAxis}
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
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

export function OpeningLandsChart({ lands }: { lands: SimulationResponse['opening_hand']['lands'] }) {
  const rows = entries(lands)
  const data = rows.map(([count, estimate]) => ({ lands: count, chance: pct(estimate) }))
  const name = t('sim.hand.column.chance')
  return (
    <ChartCard
      title={t('sim.hand.title')}
      subtitle={t('sim.hand.subtitle')}
      table={
        <DataTable
          caption={t('sim.hand.title')}
          columns={[t('sim.hand.column.lands'), name]}
          rows={rows.map(([count, estimate]) => [count, ciText(estimate)])}
        />
      }
    >
      <div className="h-64" role="img" aria-label={t('sim.hand.title')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="lands" tick={TICK} stroke="var(--axis)" tickLine={false} />
            {yAxis}
            <Tooltip
              cursor={{ fill: 'var(--grid)', opacity: 0.5 }}
              content={(props) => (
                <ChartTooltip
                  {...props}
                  formatLabel={(count) => `${count} ${t('sim.hand.column.lands').toLowerCase()}`}
                  formatValue={(value) => percent(value / 100)}
                />
              )}
            />
            <Bar
              dataKey="chance"
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

/** Fontes por cor: tabela direta (cor x turno), já que são dezenas de valores. */
export function ColorSourcesTable({ mana }: { mana: NonNullable<SimulationResponse['mana']> }) {
  const turns = ['2', '3', '4', '6']
  const colors = mana.colors.filter((id) => id !== 'C')
  const levels = ['1', '2']
  return (
    <section
      aria-label={t('sim.colors.title')}
      className="rounded-lg border border-ring bg-surface p-4"
    >
      <h3 className="text-sm font-semibold text-ink">{t('sim.colors.title')}</h3>
      <p className="mb-3 mt-0.5 text-xs text-ink-2">{t('sim.colors.subtitle')}</p>
      <div className="overflow-auto">
        <DataTable
          columns={[
            t('sim.colors.column.color'),
            ...turns.flatMap((turn) =>
              levels.map((count) => t('sim.colors.atLeast', { count, turn })),
            ),
          ]}
          rows={colors.map((id) => [
            colorName(id),
            ...turns.flatMap((turn) =>
              levels.map((count) => {
                const estimate = mana.color_sources[id]?.[turn]?.[count]
                return estimate ? percent(estimate.p) : '–'
              }),
            ),
          ])}
        />
      </div>
    </section>
  )
}
