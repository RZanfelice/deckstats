import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import broken from '../test/fixtures/analysis-broken.json'
import kalamax from '../test/fixtures/analysis-kalamax.json'
import { AnalyzePage } from './AnalyzePage'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AnalyzePage />
    </QueryClientProvider>,
  )
}

function stubApi(response: Response) {
  const fn = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fn)
  return fn
}

async function submit(text = '1 Sol Ring') {
  const user = userEvent.setup()
  await user.click(screen.getByLabelText('Sua lista'))
  await user.paste(text)
  await user.click(screen.getByRole('button', { name: 'Analisar' }))
  return user
}

afterEach(() => vi.unstubAllGlobals())

describe('AnalyzePage', () => {
  it('começa vazia e orienta o usuário', () => {
    renderPage()
    expect(screen.getByText(/Cole uma lista/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analisar' })).toBeDisabled()
  })

  it('mostra o resumo, os avisos e as cartas de uma análise', async () => {
    const fn = stubApi(Response.json(kalamax))
    renderPage()
    await submit()

    expect(await screen.findByRole('region', { name: 'Resumo' })).toBeInTheDocument()
    expect(fn).toHaveBeenCalledTimes(1)

    const summary = screen.getByRole('region', { name: 'Resumo' })
    expect(within(summary).getByText('36')).toBeInTheDocument()
    expect(within(summary).getByText('4')).toBeInTheDocument()

    const issues = screen.getByRole('region', { name: 'Avisos' })
    expect(within(issues).getByText(/Identificamos Kalamax, the Stormsire como comandante/)).toBeInTheDocument()

    expect(screen.getByRole('region', { name: 'Cartas' })).toBeInTheDocument()
    expect(screen.getByText('83 de 83 cartas')).toBeInTheDocument()
  })

  it('filtra as cartas por categoria e por nome', async () => {
    stubApi(Response.json(kalamax))
    renderPage()
    const user = await submit()
    await screen.findByText('83 de 83 cartas')

    await user.type(screen.getByLabelText('Buscar carta'), 'anticipate')
    expect(screen.getByText('1 de 83 cartas')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Buscar carta'))
    await user.selectOptions(screen.getByLabelText('Filtrar por categoria'), 'ramp')
    expect(screen.getByText('21 de 83 cartas')).toBeInTheDocument()
  })

  it('alterna um gráfico para a visão em tabela', async () => {
    stubApi(Response.json(kalamax))
    renderPage()
    const user = await submit()
    const curve = (await screen.findByRole('heading', { name: 'Curva de mana' })).closest('section')!

    await user.click(within(curve).getByRole('button', { name: 'Ver como tabela' }))
    expect(within(curve).getByRole('table')).toBeInTheDocument()
    expect(within(curve).getByRole('columnheader', { name: 'Valor de mana' })).toBeInTheDocument()
  })

  it('lida com lista quebrada: sem dados de terrenos, avisos e sugestões', async () => {
    stubApi(Response.json(broken))
    renderPage()
    await submit('1 Solring')

    expect(await screen.findByText(/Não encontramos 1 carta/)).toBeInTheDocument()
    expect(screen.getByText(/Você quis dizer Sol Ring/)).toBeInTheDocument()
    expect(screen.getByText(/Sem dados de terrenos/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Quantos terrenos usar?' })).not.toBeInTheDocument()
  })

  it('mostra o erro devolvido pela API', async () => {
    stubApi(Response.json({ detail: 'Lista vazia' }, { status: 400 }))
    renderPage()
    await submit()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Não foi possível analisar a lista')
    expect(alert).toHaveTextContent('Lista vazia')
  })

  it('envia as opções escolhidas', async () => {
    const fn = stubApi(Response.json(kalamax))
    renderPage()
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Sua lista'))
    await user.paste('1 Sol Ring')
    await user.click(screen.getByLabelText(/Começo jogando primeiro/))
    await user.click(screen.getByLabelText(/Contar MDFC/))
    await user.click(screen.getByRole('button', { name: 'Analisar' }))

    await screen.findByRole('region', { name: 'Resumo' })
    expect(fn.mock.calls[0]?.[0]).toBe(
      '/api/analyses/text?count_mdfc_lands=false&commander_weight=0.6&on_the_play=true',
    )
  })
})
