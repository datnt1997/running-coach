// Fails if a literal t('key') used in src/ is missing from any dictionary,
// or if a dictionary is missing keys that vi.js has.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const SRC = new URL('../src/', import.meta.url).pathname
const I18N = join(SRC, 'i18n')

function walk(dir) {
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

const dictFiles = readdirSync(I18N).filter(f => f.endsWith('.js') && f !== 'index.js')
const dicts = {}
for (const f of dictFiles) {
  dicts[f.slice(0, -3)] = (await import(pathToFileURL(join(I18N, f)).href)).default
}

const used = new Set()
for (const file of walk(SRC).filter(f => /\.jsx?$/.test(f))) {
  for (const m of readFileSync(file, 'utf8').matchAll(/\bt\(\s*'([^']+)'/g)) used.add(m[1])
}

let failed = false
for (const [code, dict] of Object.entries(dicts)) {
  const missing = [...used].filter(k => !(k in dict))
  const extra = Object.keys(dicts.vi).filter(k => !(k in dict))
  if (missing.length) { console.error(`${code}: missing used keys: ${missing.join(', ')}`); failed = true }
  if (extra.length) { console.error(`${code}: missing keys present in vi: ${extra.join(', ')}`); failed = true }
}
if (failed) process.exit(1)
console.log(`i18n ok: ${used.size} keys used, languages: ${Object.keys(dicts).join(', ')}`)
