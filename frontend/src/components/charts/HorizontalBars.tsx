import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartTooltip } from '../ChartTooltip'

const TICK = { fill: 'var(--ink-2)', fontSize: 12 }
const ROW = 28
const AXIS_BAND = 28

export interface BarDatum {
  label: string
  value: number
}

interface HorizontalBarsProps {
  data: BarDatum[]
  seriesName: string
  ariaLabel: string
  formatValue?: (value: number) => string
}

/** Barras horizontais de série única: categorias nominais, uma só cor. */
export function HorizontalBars({ data, seriesName, ariaLabel, formatValue = String }: HorizontalBarsProps) {
  // A altura inclui a faixa do eixo x para as barras não encolherem.
  const height = data.length * ROW + AXIS_BAND
  return (
    <div style={{ height }} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke="var(--grid)" />
          <XAxis type="number" allowDecimals={false} tick={TICK} stroke="var(--axis)" tickLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={130}
            tick={TICK}
            stroke="var(--axis)"
            tickLine={false}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: 'var(--grid)', opacity: 0.5 }}
            content={(props) => <ChartTooltip {...props} formatValue={formatValue} />}
          />
          <Bar
            dataKey="value"
            name={seriesName}
            fill="var(--series-1)"
            maxBarSize={20}
            radius={[0, 4, 4, 0]}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
