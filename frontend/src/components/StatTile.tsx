import type { ReactNode } from 'react'

interface StatTileProps {
  label: string
  value: ReactNode
  hint?: string
}

export function StatTile({ label, value, hint }: StatTileProps) {
  return (
    <div className="rounded-lg border border-ring bg-surface p-4">
      <div className="text-xs text-ink-2">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-3">{hint}</div>}
    </div>
  )
}
