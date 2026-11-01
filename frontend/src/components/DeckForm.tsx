import { useState, type FormEvent } from 'react'
import type { AnalyzeOptions } from '../api/client'
import { t } from '../i18n'
import { EXAMPLE_DECK } from '../lib/exampleDeck'

interface DeckFormProps {
  initialText: string
  initialOptions: AnalyzeOptions
  busy: boolean
  onSubmit: (text: string, options: AnalyzeOptions) => void
}

export function DeckForm({ initialText, initialOptions, busy, onSubmit }: DeckFormProps) {
  const [text, setText] = useState(initialText)
  const [options, setOptions] = useState(initialOptions)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (text.trim()) onSubmit(text, options)
  }

  return (
    <form onSubmit={submit} className="rounded-lg border border-ring bg-surface p-4">
      <label htmlFor="deck-text" className="mb-1 block text-sm font-semibold text-ink">
        {t('form.title')}
      </label>
      <p className="mb-2 text-xs text-ink-2">{t('form.help')}</p>
      <textarea
        id="deck-text"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={t('form.placeholder')}
        rows={14}
        spellCheck={false}
        className="w-full resize-y rounded border border-ring bg-page p-2 font-mono text-xs text-ink"
      />

      <fieldset className="mt-3 space-y-2">
        <legend className="mb-1 text-xs font-medium text-ink-2">{t('form.options')}</legend>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={options.countMdfcLands}
            onChange={(event) => setOptions({ ...options, countMdfcLands: event.target.checked })}
          />
          {t('form.option.mdfc')}
        </label>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={options.onThePlay}
            onChange={(event) => setOptions({ ...options, onThePlay: event.target.checked })}
          />
          {t('form.option.play')}
        </label>
        <div>
          <label htmlFor="commander-weight" className="flex items-center justify-between text-sm text-ink">
            {t('form.option.weight')}
            <output className="tabular-nums text-ink-2">{options.commanderWeight.toFixed(1)}</output>
          </label>
          <input
            id="commander-weight"
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={options.commanderWeight}
            onChange={(event) => setOptions({ ...options, commanderWeight: Number(event.target.value) })}
            className="w-full"
          />
          <p className="text-xs text-ink-3">{t('form.option.weight.help')}</p>
        </div>
      </fieldset>

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="rounded bg-series-1 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? t('form.analyzing') : t('form.analyze')}
        </button>
        <button
          type="button"
          onClick={() => setText(EXAMPLE_DECK)}
          className="rounded border border-ring px-3 py-1.5 text-sm text-ink-2 hover:text-ink"
        >
          {t('form.example')}
        </button>
      </div>
    </form>
  )
}
