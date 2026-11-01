import type { Issue, Unresolved } from '../api/client'
import { issueMessage, t } from '../i18n'

const SEVERITY = {
  error: { icon: '✕', color: 'text-critical', label: 'issues.severity.error' },
  warning: { icon: '!', color: 'text-ink', label: 'issues.severity.warning' },
  info: { icon: 'i', color: 'text-ink-2', label: 'issues.severity.info' },
} as const

interface IssuesListProps {
  issues: Issue[]
  unresolved: Unresolved[]
}

/** Avisos com ícone e rótulo (nunca só cor) e sugestões para nomes não encontrados. */
export function IssuesList({ issues, unresolved }: IssuesListProps) {
  const suggestionsByName = new Map(unresolved.map((item) => [item.requested_name, item.suggestions]))
  return (
    <section aria-label={t('issues.title')} className="rounded-lg border border-ring bg-surface p-4">
      <h3 className="mb-2 text-sm font-semibold text-ink">{t('issues.title')}</h3>
      {issues.length === 0 ? (
        <p className="text-sm text-ink-2">{t('issues.none')}</p>
      ) : (
        <ul className="space-y-2">
          {issues.map((issue, index) => {
            const style = SEVERITY[issue.severity as keyof typeof SEVERITY] ?? SEVERITY.info
            return (
              <li key={`${issue.code}-${index}`} className="flex gap-2 text-sm">
                <span
                  aria-hidden
                  className={`mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold ${style.color}`}
                >
                  {style.icon}
                </span>
                <div>
                  <span className="sr-only">{t(style.label)}: </span>
                  <span className="text-ink">{issueMessage(issue)}</span>
                  {issue.code === 'cards_not_found' &&
                    issue.cards.map((name) => {
                      const suggestions = suggestionsByName.get(name) ?? []
                      if (suggestions.length === 0) return null
                      return (
                        <div key={name} className="text-xs text-ink-2">
                          {name}: {t('issues.didYouMean')} {suggestions.join(', ')}?
                        </div>
                      )
                    })}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
