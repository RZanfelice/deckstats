import { useId, useState, type ReactNode } from 'react'
import { t } from '../i18n'

interface ChartCardProps {
  title: string
  subtitle?: string
  /** Gráfico; a visão em tabela (`table`) é sempre equivalente a ele. */
  children: ReactNode
  table: ReactNode
  footer?: ReactNode
}

export function ChartCard({ title, subtitle, children, table, footer }: ChartCardProps) {
  const [asTable, setAsTable] = useState(false)
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="rounded-lg border border-ring bg-surface p-4">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 id={headingId} className="text-sm font-semibold text-ink">
            {title}
          </h3>
          {subtitle && <p className="mt-0.5 text-xs text-ink-2">{subtitle}</p>}
        </div>
        <button
          type="button"
          onClick={() => setAsTable((value) => !value)}
          className="shrink-0 rounded border border-ring px-2 py-1 text-xs text-ink-2 hover:text-ink"
        >
          {asTable ? t('chart.viewAsChart') : t('chart.viewAsTable')}
        </button>
      </header>
      {asTable ? <div className="max-h-72 overflow-auto">{table}</div> : children}
      {footer && <p className="mt-3 text-xs text-ink-3">{footer}</p>}
    </section>
  )
}
