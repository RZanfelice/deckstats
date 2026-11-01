import type { Issue } from '../api/client'
import { messages, type MessageKey } from './pt-BR'

export type { MessageKey }

type Params = Record<string, string | number>

const listFormat = new Intl.ListFormat('pt-BR', { style: 'long', type: 'conjunction' })

export function list(items: readonly string[]): string {
  return listFormat.format(items)
}

export function t(key: MessageKey, params: Params = {}): string {
  return messages[key].replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`))
}

/** Nome traduzido de uma chave dinâmica (categoria, cor, tipo...), ou o próprio id se faltar. */
function lookup(prefix: string, id: string): string {
  const key = `${prefix}.${id}` as MessageKey
  return key in messages ? t(key) : id
}

export const categoryName = (id: string): string => lookup('category', id)
export const typeName = (id: string): string => lookup('type', id)
export const colorName = (id: string): string => lookup('color', id)
export const sectionName = (id: string): string => lookup('section', id)
export const legalityName = (id: string): string => lookup('legality', id)

function detailList(issue: Issue, field: string): string[] {
  const value = issue.details[field]
  return Array.isArray(value) ? value.map(String) : []
}

/** Texto em português de um aviso da API. A API devolve só código e dados. */
export function issueMessage(issue: Issue): string {
  const cards = list(issue.cards)
  switch (issue.code) {
    case 'cards_not_found':
      return t('issue.cards_not_found', { count: issue.cards.length, cards })
    case 'unparsed_lines': {
      const lines = Array.isArray(issue.details.lines) ? issue.details.lines : []
      const numbers = lines.map((item) => String((item as { line?: number }).line ?? '?'))
      return t('issue.unparsed_lines', { count: numbers.length, lines: list(numbers) })
    }
    case 'deck_size':
      return t('issue.deck_size', {
        actual: Number(issue.details.actual ?? 0),
        expected: Number(issue.details.expected ?? 100),
      })
    case 'color_identity_violation':
      return t('issue.color_identity_violation', {
        allowed: list(detailList(issue, 'allowed').map(colorName)) || t('summary.identity.none'),
        cards,
      })
    case 'ambiguous_names': {
      const resolved = (issue.details.resolved_to ?? {}) as Record<string, string>
      const pairs = Object.entries(resolved).map(([requested, name]) => `${requested} → ${name}`)
      return t('issue.ambiguous_names', { pairs: list(pairs) })
    }
    case 'commander_missing':
    case 'commander_not_eligible':
    case 'commander_pair_invalid':
    case 'too_many_commanders':
    case 'singleton_violation':
    case 'banned_cards':
    case 'not_legal_cards':
    case 'commander_inferred':
      return t(`issue.${issue.code}` as MessageKey, { cards })
    default:
      return t('issue.unknown', { code: issue.code })
  }
}
