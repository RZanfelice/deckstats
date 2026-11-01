import { useMemo, useState } from 'react'
import type { CardOut } from '../api/client'
import { categoryName, legalityName, sectionName, t } from '../i18n'
import { decimal } from '../lib/format'

interface CardsTableProps {
  cards: CardOut[]
}

export function CardsTable({ cards }: CardsTableProps) {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')

  const categories = useMemo(
    () => [...new Set(cards.flatMap((card) => card.categories))].sort(),
    [cards],
  )
  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return cards.filter(
      (card) =>
        (!needle || card.name.toLowerCase().includes(needle)) &&
        (!category || card.categories.includes(category)),
    )
  }, [cards, search, category])

  return (
    <section aria-label={t('cards.title')} className="rounded-lg border border-ring bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="mr-auto text-sm font-semibold text-ink">{t('cards.title')}</h3>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('cards.search')}
          aria-label={t('cards.search')}
          className="rounded border border-ring bg-page px-2 py-1 text-sm text-ink"
        />
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          aria-label={t('cards.filterCategory')}
          className="rounded border border-ring bg-page px-2 py-1 text-sm text-ink"
        >
          <option value="">{t('cards.allCategories')}</option>
          {categories.map((id) => (
            <option key={id} value={id}>
              {categoryName(id)}
            </option>
          ))}
        </select>
        <span className="text-xs text-ink-2">
          {t('cards.count', { shown: shown.length, total: cards.length })}
        </span>
      </div>
      <div className="max-h-96 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr className="border-b border-grid text-left text-xs text-ink-2">
              <th scope="col" className="py-1 font-medium">{t('cards.column.qty')}</th>
              <th scope="col" className="py-1 font-medium">{t('cards.column.name')}</th>
              <th scope="col" className="py-1 font-medium">{t('cards.column.section')}</th>
              <th scope="col" className="py-1 text-right font-medium">{t('cards.column.mv')}</th>
              <th scope="col" className="py-1 font-medium">{t('cards.column.legality')}</th>
              <th scope="col" className="py-1 font-medium">{t('cards.column.categories')}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((card) => (
              <tr key={`${card.oracle_id}-${card.section}`} className="border-b border-grid last:border-0">
                <td className="py-1 tabular-nums">{card.quantity}</td>
                <td className="py-1 text-ink">{card.name}</td>
                <td className="py-1 text-ink-2">{sectionName(card.section)}</td>
                <td className="py-1 text-right tabular-nums">{decimal(card.mana_value)}</td>
                <td className="py-1 text-ink-2">
                  {card.commander_legality === 'legal' ? '' : legalityName(card.commander_legality)}
                </td>
                <td className="py-1 text-ink-2">{card.categories.map(categoryName).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 && <p className="py-4 text-center text-sm text-ink-2">{t('cards.empty')}</p>}
      </div>
    </section>
  )
}
