interface Entry {
  name?: string | number
  value?: string | number | readonly (string | number)[]
  color?: string
}

interface ChartTooltipProps {
  active?: boolean
  payload?: readonly Entry[]
  label?: string | number
  formatLabel?: (label: string | number) => string
  formatValue: (value: number) => string
}

/** Tooltip de gráfico: reforça o que já está no gráfico e na tabela, nunca é a única fonte. */
export function ChartTooltip({ active, payload, label, formatLabel, formatValue }: ChartTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-ring bg-surface px-2.5 py-1.5 text-xs shadow-sm">
      {label !== undefined && (
        <div className="mb-1 font-medium text-ink">{formatLabel ? formatLabel(label) : label}</div>
      )}
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-1.5 text-ink-2">
          <span
            aria-hidden
            className="inline-block size-2 rounded-sm"
            style={{ background: entry.color }}
          />
          <span>{entry.name}</span>
          <span className="ml-auto pl-3 tabular-nums text-ink">{formatValue(Number(entry.value))}</span>
        </div>
      ))}
    </div>
  )
}
