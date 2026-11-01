import { afterEach, describe, expect, it, vi } from 'vitest'
import { analyzeText, ApiError, DEFAULT_OPTIONS } from './client'

function mockFetch(response: Response) {
  const fn = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('analyzeText', () => {
  it('envia o texto cru e as opções na query', async () => {
    const fn = mockFetch(Response.json({ ok: true }))
    await analyzeText('1 Sol Ring\n', { countMdfcLands: false, commanderWeight: 0.4, onThePlay: true })

    const [url, init] = fn.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(
      '/api/analyses/text?count_mdfc_lands=false&commander_weight=0.4&on_the_play=true',
    )
    expect(init.method).toBe('POST')
    expect(init.body).toBe('1 Sol Ring\n')
    expect(init.headers).toEqual({ 'content-type': 'text/plain; charset=utf-8' })
  })

  it('usa as opções padrão do domínio', () => {
    expect(DEFAULT_OPTIONS).toEqual({ countMdfcLands: true, commanderWeight: 0.6, onThePlay: false })
  })

  it('lê o detail em texto', async () => {
    mockFetch(Response.json({ detail: 'Lista vazia' }, { status: 400 }))
    await expect(analyzeText('', DEFAULT_OPTIONS)).rejects.toMatchObject({
      status: 400,
      message: 'Lista vazia',
    })
  })

  it('junta as mensagens de validação do FastAPI', async () => {
    mockFetch(Response.json({ detail: [{ msg: 'a' }, { msg: 'b' }] }, { status: 422 }))
    await expect(analyzeText('x', DEFAULT_OPTIONS)).rejects.toThrow('a; b')
  })

  it('cai na mensagem genérica quando o corpo não é JSON', async () => {
    mockFetch(new Response('Bad Gateway', { status: 502 }))
    const error = await analyzeText('x', DEFAULT_OPTIONS).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe('Erro 502')
  })
})
