// Gera src/api/schema.d.ts a partir do OpenAPI do backend, sem precisar subir o servidor:
// o spec sai direto da aplicação FastAPI. Rode com `npm run gen:api` depois de mudar a API.
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const backend = resolve(root, '..', 'backend')
const specPath = resolve(root, 'src', 'api', 'openapi.json')
const typesPath = resolve(root, 'src', 'api', 'schema.d.ts')

const python = 'import json; from deckstats.main import create_app; print(json.dumps(create_app().openapi()))'
const spec = execFileSync('uv', ['run', 'python', '-c', python], { cwd: backend, encoding: 'utf8' })

mkdirSync(dirname(specPath), { recursive: true })
writeFileSync(specPath, JSON.stringify(JSON.parse(spec), null, 2) + '\n')
const cli = resolve(root, 'node_modules', 'openapi-typescript', 'bin', 'cli.js')
execFileSync(process.execPath, [cli, specPath, '-o', typesPath], { cwd: root, stdio: 'inherit' })
console.log(`Tipos gerados em ${typesPath}`)
