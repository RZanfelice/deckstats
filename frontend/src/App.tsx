import { Route, Routes } from 'react-router-dom'
import { t } from './i18n'
import { AnalyzePage } from './pages/AnalyzePage'

export default function App() {
  return (
    <>
      <header className="border-b border-ring bg-surface">
        <div className="mx-auto flex max-w-6xl items-baseline gap-3 px-4 py-3">
          <h1 className="text-lg font-semibold text-ink">{t('app.name')}</h1>
          <p className="text-sm text-ink-2">{t('app.tagline')}</p>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<AnalyzePage />} />
        </Routes>
      </main>
    </>
  )
}
