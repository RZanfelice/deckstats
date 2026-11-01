import { describe, expect, it } from 'vitest'
import type { Issue } from '../api/client'
import broken from '../test/fixtures/analysis-broken.json'
import kalamax from '../test/fixtures/analysis-kalamax.json'
import { categoryName, issueMessage, t } from './index'

const issue = (code: string, extra: Partial<Issue> = {}): Issue => ({
  code,
  severity: 'warning',
  cards: [],
  details: {},
  ...extra,
})

describe('issueMessage', () => {
  // Todo código que o backend emite precisa de texto próprio, não do genérico.
  const codes = [
    'cards_not_found',
    'unparsed_lines',
    'commander_missing',
    'commander_not_eligible',
    'commander_pair_invalid',
    'too_many_commanders',
    'deck_size',
    'singleton_violation',
    'color_identity_violation',
    'banned_cards',
    'not_legal_cards',
    'commander_inferred',
    'ambiguous_names',
  ]

  it.each(codes)('traduz %s', (code) => {
    const text = issueMessage(issue(code, { cards: ['Sol Ring'] }))
    expect(text).not.toBe(t('issue.unknown', { code }))
    expect(text).not.toMatch(/\{\w+\}/)
  })

  it('cai no texto genérico para código desconhecido', () => {
    expect(issueMessage(issue('novo_codigo'))).toBe('Aviso: novo_codigo')
  })

  it('formata tamanho do deck e linhas ilegíveis', () => {
    expect(issueMessage(issue('deck_size', { details: { expected: 100, actual: 97 } }))).toContain('97')
    expect(
      issueMessage(issue('unparsed_lines', { details: { lines: [{ line: 3 }, { line: 9 }] } })),
    ).toContain('3 e 9')
  })

  it('traduz as cores permitidas na violação de identidade', () => {
    const text = issueMessage(
      issue('color_identity_violation', { cards: ['Counterspell'], details: { allowed: ['R', 'G'] } }),
    )
    expect(text).toContain('Vermelho e Verde')
  })

  it('traduz todos os avisos reais das fixtures', () => {
    for (const fixture of [kalamax, broken]) {
      for (const item of fixture.issues) {
        expect(issueMessage(item as Issue)).not.toContain('Aviso:')
      }
    }
  })
})

describe('categoryName', () => {
  it('traduz todas as categorias devolvidas pela API', () => {
    for (const item of kalamax.categories.categories) {
      expect(categoryName(item.category)).not.toBe(item.category)
    }
  })

  it('devolve o id quando não há tradução', () => {
    expect(categoryName('inexistente')).toBe('inexistente')
  })
})
