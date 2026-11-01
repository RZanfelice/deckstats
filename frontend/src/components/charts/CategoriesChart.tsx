import type { AnalysisResponse } from '../../api/client'
import { categoryName, t } from '../../i18n'
import { percent } from '../../lib/format'
import { ChartCard } from '../ChartCard'
import { DataTable } from '../DataTable'
import { HorizontalBars } from './HorizontalBars'

export function CategoriesChart({ categories }: { categories: AnalysisResponse['categories'] }) {
  const supported = categories.categories.filter((item) => item.supported)
  const unsupported = categories.categories.filter((item) => !item.supported)
  const data = supported
    .map((item) => ({ label: categoryName(item.category), value: item.count }))
    .sort((a, b) => b.value - a.value)
  return (
    <ChartCard
      title={t('categories.title')}
      subtitle={t('categories.subtitle')}
      footer={unsupported
        .map((item) => t('categories.unsupported', { name: categoryName(item.category) }))
        .join(' · ')}
      table={
        <DataTable
          caption={t('categories.title')}
          columns={[
            t('categories.column.category'),
            t('categories.column.count'),
            t('categories.column.percent'),
          ]}
          rows={supported.map((item) => [categoryName(item.category), item.count, percent(item.percent)])}
        />
      }
    >
      <HorizontalBars
        data={data}
        seriesName={t('categories.column.count')}
        ariaLabel={t('categories.title')}
      />
    </ChartCard>
  )
}
