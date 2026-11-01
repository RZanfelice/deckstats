import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_OPTIONS, DEFAULT_SIMULATE_OPTIONS, simulateText } from '../api/client'
import simulation from '../test/fixtures/simulation-lorehold.json'
import { SimulationPanel } from './SimulationPanel'

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SimulationPanel text="1 Sol Ring" analysis={DEFAULT_OPTIONS} />
    </QueryClientProvider>,
  )
}

function stubApi(response: Response) {
  const fn = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('simulateText', () => {
  it('monta a query com as opções, incluindo o custo extra', async () => {
    const fn = stubApi(Response.json(simulation))
    await simulateText(
      'x',
      { ...DEFAULT_OPTIONS, onThePlay: true },
      { ...DEFAULT_SIMULATE_OPTIONS, extraCost: '{2}{U}{U}', castRamp: false },
    )
    const url = new URL(fn.mock.calls[0]?.[0] as string, 'http://x')
    expect(url.pathname).toBe('/api/simulations/text')
    expect(url.searchParams.get('iterations')).toBe('5000')
    expect(url.searchParams.get('keep_policy')).toBe('castable')
    expect(url.searchParams.get('cast_ramp')).toBe('false')
    expect(url.searchParams.get('on_the_play')).toBe('true')
    expect(url.searchParams.get('costs')).toBe('{2}{U}{U}')
  })

  it('omite costs quando não há custo extra', async () => {
    const fn = stubApi(Response.json(simulation))
    await simulateText('x', DEFAULT_OPTIONS, DEFAULT_SIMULATE_OPTIONS)
    expect(new URL(fn.mock.calls[0]?.[0] as string, 'http://x').searchParams.has('costs')).toBe(false)
  })
})

describe('SimulationPanel', () => {
  it('não simula até o usuário pedir', () => {
    const fn = stubApi(Response.json(simulation))
    renderPanel()
    expect(fn).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Simular' })).toBeEnabled()
  })

  it('mostra mão mantível, mulligan e gráficos depois de simular', async () => {
    stubApi(Response.json(simulation))
    renderPanel()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Simular' }))

    expect(await screen.findByText('Primeira mão mantível')).toBeInTheDocument()
    expect(screen.getByText('60,1%')).toBeInTheDocument()
    expect(screen.getByText('Pelo menos um mulligan')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Chance de conjurar por turno' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Jogadas de terreno' })).toBeInTheDocument()
    expect(screen.getByText(/Terrenos sem mana conhecida.*Fabled Passage e Terramorphic Expanse/)).toBeInTheDocument()

    const colors = screen.getByRole('region', { name: 'Fontes de cada cor' })
    expect(within(colors).getByText('Vermelho')).toBeInTheDocument()
    expect(within(colors).queryByText('Incolor')).not.toBeInTheDocument()
  })

  it('bloqueia um custo extra inválido', async () => {
    const fn = stubApi(Response.json(simulation))
    renderPanel()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Custo extra'), '2UU')

    expect(screen.getByRole('alert')).toHaveTextContent('Use o formato')
    expect(screen.getByRole('button', { name: 'Simular' })).toBeDisabled()
    expect(fn).not.toHaveBeenCalled()
  })

  it('mostra o erro devolvido pela API', async () => {
    stubApi(Response.json({ detail: 'Biblioteca vazia' }, { status: 422 }))
    renderPanel()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Simular' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Não foi possível simular')
    expect(alert).toHaveTextContent('Biblioteca vazia')
  })
})
